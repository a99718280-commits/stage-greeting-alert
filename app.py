from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from pathlib import Path
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone, timedelta
import hashlib, json, os, re, sqlite3, threading

import requests
from bs4 import BeautifulSoup

app = FastAPI(title='무대인사 알림')
KST = timezone(timedelta(hours=9))
DB_PATH = os.getenv('DB_PATH', 'stage_alert.db')
LOCK = threading.Lock()

FIREBASE_CONFIG = {
    'apiKey': 'AIzaSyCXvA9n9doSv3OZIzbFc7XrlEqUeYteTk4',
    'authDomain': 'stage-greeting-alert.firebaseapp.com',
    'projectId': 'stage-greeting-alert',
    'storageBucket': 'stage-greeting-alert.firebasestorage.app',
    'messagingSenderId': '192680261195',
    'appId': '1:192680261195:web:7d5f65afcaf248d77fbfce'
}
VAPID_KEY = 'BPgkBtTm3c0ZTNU33gEj5AmkcIBcekGM5GXsT7rxgPCgire7KBizpImFLpOAJm3iRzcltBHW5CDfn0W1ek8vUvw'

SOURCES = [
    {
        'chain': 'CGV',
        'url': 'https://cgv.co.kr/cnm/movieBook/movie',
        'booking_url': 'https://cgv.co.kr/cnm/movieBook/movie',
    },
    {
        'chain': '롯데시네마',
        'url': 'https://www.lottecinema.co.kr/NLCHS/Event/DetailList?code=50',
        'booking_url': 'https://www.lottecinema.co.kr/NLCHS/Ticketing',
    },
    {
        'chain': '메가박스',
        'url': 'https://www.megabox.co.kr/event',
        'booking_url': 'https://www.megabox.co.kr/booking',
    },
]

KEYWORDS = ('무대인사', 'GV', '관객과의 대화', 'stage greeting')
EXACT_NOISE = {'무대인사', 'GV', '시사회/무대인사', '시사회 · 무대인사'}
UA = {'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/140 Safari/537.36'}


def now_iso():
    return datetime.now(KST).isoformat(timespec='seconds')


def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS tokens(
          token TEXT PRIMARY KEY,
          created_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS items(
          id TEXT PRIMARY KEY,
          chain TEXT NOT NULL,
          title TEXT NOT NULL,
          source_url TEXT NOT NULL,
          booking_url TEXT NOT NULL,
          date_text TEXT,
          time_text TEXT,
          timing TEXT,
          participants TEXT,
          raw_text TEXT,
          first_seen_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS meta(
          key TEXT PRIMARY KEY,
          value TEXT
        );
        ''')

init_db()


def set_meta(key, value):
    with db() as c:
        c.execute('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))


def get_meta(key, default=''):
    with db() as c:
        row = c.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
    return row['value'] if row else default


def clean_text(s):
    return re.sub(r'\s+', ' ', s or '').strip()


def abs_url(base, href):
    if not href or href.startswith('javascript:') or href == '#':
        return base
    return urljoin(base, href)


def extract_detail(text):
    text = clean_text(text)
    timing = '공식 안내 없음'
    if re.search(r'상영\s*전|영화\s*시작\s*전|시작\s*전', text):
        timing = '상영 전'
    if re.search(r'상영\s*후|영화\s*종료\s*후|종영\s*후|종료\s*후', text):
        timing = '상영 후' if timing == '공식 안내 없음' else '상영 전/후'

    date_match = re.search(r'(20\d{2}[.\-/년 ]\s*\d{1,2}[.\-/월 ]\s*\d{1,2}일?|\d{1,2}[.\-/월 ]\s*\d{1,2}일?)', text)
    time_match = re.search(r'(?<!\d)([01]?\d|2[0-3])[:시]\s*([0-5]\d)?', text)

    participants = '공식 안내 없음'
    patterns = [
        r'(?:참석자|참석|참여자|참여|게스트|무대인사\s*참석)\s*[:：-]?\s*([^\n|]{2,120})',
        r'(?:감독|배우)\s*[:：-]?\s*([^\n|]{2,120})',
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            candidate = clean_text(m.group(1))
            candidate = re.split(r'(?:일시|장소|극장|상영|예매|티켓|※)', candidate)[0].strip(' ,·/')
            if candidate:
                participants = candidate[:100]
                break

    return {
        'date_text': clean_text(date_match.group(1)) if date_match else '공식 안내 없음',
        'time_text': (time_match.group(0).replace('시', ':').strip(': ') if time_match else '공식 안내 없음'),
        'timing': timing,
        'participants': participants,
    }


def fetch(url, timeout=20):
    r = requests.get(url, timeout=timeout, headers=UA)
    r.raise_for_status()
    return r.text


def candidate_links(source, html):
    soup = BeautifulSoup(html, 'html.parser')
    found = []
    seen = set()

    # 일반적인 링크 기반 감지
    for a in soup.find_all('a'):
        txt = clean_text(a.get_text(' ', strip=True))
        href = abs_url(source['url'], a.get('href'))
        if not txt or txt in EXACT_NOISE or len(txt) < 4:
            continue
        keyword_hit = any(k.lower() in txt.lower() for k in KEYWORDS)
        # 롯데의 무대인사 전용 카테고리는 상세 이벤트 링크 자체도 후보로 본다.
        lotte_detail = source['chain'] == '롯데시네마' and ('Event' in href or '/event/' in href.lower()) and len(txt) <= 160
        if keyword_hit or lotte_detail:
            key = (txt[:160], href)
            if key not in seen:
                seen.add(key)
                found.append((txt[:160], href))

    # CGV 예약 화면은 '(무대인사)'가 텍스트 노드로만 잡힐 때가 있어 주변 블록을 후보로 추가
    if source['chain'] == 'CGV':
        for node in soup.find_all(string=re.compile('무대인사')):
            parent = node.parent
            for _ in range(4):
                if parent and parent.name not in ('body', 'html'):
                    txt = clean_text(parent.get_text(' ', strip=True))
                    if 8 <= len(txt) <= 240 and '무대인사' in txt and txt not in EXACT_NOISE:
                        a = parent.find('a') if hasattr(parent, 'find') else None
                        href = abs_url(source['url'], a.get('href')) if a else source['booking_url']
                        key = (txt[:160], href)
                        if key not in seen:
                            seen.add(key)
                            found.append((txt[:160], href))
                        break
                    parent = parent.parent if parent else None

    return found[:80]


def build_item(source, title, url):
    detail_text = title
    if url and url != source['url']:
        try:
            detail_html = fetch(url, 12)
            detail_soup = BeautifulSoup(detail_html, 'html.parser')
            detail_text = clean_text(detail_soup.get_text(' ', strip=True))[:7000]
        except Exception:
            pass

    info = extract_detail(detail_text)
    normalized = f"{source['chain']}|{clean_text(title).lower()}|{url}"
    item_id = hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:24]
    return {
        'id': item_id,
        'chain': source['chain'],
        'title': clean_text(title)[:160],
        'source_url': url or source['url'],
        'booking_url': url or source['booking_url'],
        'raw_text': detail_text[:4000],
        **info,
    }


def firebase_ready():
    path = os.getenv('FIREBASE_SERVICE_ACCOUNT', '/etc/secrets/firebase-service-account.json')
    return Path(path).exists()


def send_push(item):
    if not firebase_ready():
        return {'sent': 0, 'reason': 'firebase-service-account-not-configured'}
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
        if not firebase_admin._apps:
            path = os.getenv('FIREBASE_SERVICE_ACCOUNT', '/etc/secrets/firebase-service-account.json')
            firebase_admin.initialize_app(credentials.Certificate(path))
        with db() as c:
            tokens = [r['token'] for r in c.execute('SELECT token FROM tokens').fetchall()]
        if not tokens:
            return {'sent': 0, 'reason': 'no-token'}

        title = '🔥 무대인사 예매/공지 감지'
        body_parts = [item['chain'], item['title']]
        if item.get('timing') and item['timing'] != '공식 안내 없음':
            body_parts.append(item['timing'])
        body = ' · '.join(body_parts)[:180]
        sent = 0
        invalid = []
        for token in tokens:
            try:
                # data-only: 서비스워커에서 한 번만 표시하고 클릭 URL을 직접 제어
                msg = messaging.Message(
                    token=token,
                    data={
                        'title': title,
                        'body': body,
                        'url': item['booking_url'],
                        'item_id': item['id'],
                    },
                    webpush=messaging.WebpushConfig(headers={'Urgency': 'high'}),
                )
                messaging.send(msg)
                sent += 1
            except Exception as e:
                if 'registration-token-not-registered' in str(e).lower() or 'not found' in str(e).lower():
                    invalid.append(token)
        if invalid:
            with db() as c:
                c.executemany('DELETE FROM tokens WHERE token=?', [(t,) for t in invalid])
        return {'sent': sent, 'reason': 'ok'}
    except Exception as e:
        return {'sent': 0, 'reason': str(e)[:180]}


def scan_all():
    results = []
    errors = []
    new_items = []
    with LOCK:
        for source in SOURCES:
            try:
                html = fetch(source['url'])
                links = candidate_links(source, html)
                source_count = 0
                for title, url in links:
                    item = build_item(source, title, url)
                    with db() as c:
                        exists = c.execute('SELECT 1 FROM items WHERE id=?', (item['id'],)).fetchone()
                        if exists:
                            continue
                        c.execute('''INSERT INTO items(id,chain,title,source_url,booking_url,date_text,time_text,timing,participants,raw_text,first_seen_at)
                                     VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                                  (item['id'], item['chain'], item['title'], item['source_url'], item['booking_url'],
                                   item['date_text'], item['time_text'], item['timing'], item['participants'], item['raw_text'], now_iso()))
                    source_count += 1
                    item['push'] = send_push(item)
                    new_items.append(item)
                results.append({'chain': source['chain'], 'new': source_count, 'candidates': len(links)})
            except Exception as e:
                errors.append({'chain': source['chain'], 'error': str(e)[:180]})
        set_meta('last_scan_at', now_iso())
        set_meta('last_scan_errors', json.dumps(errors, ensure_ascii=False))
    return {'ok': True, 'scanned_at': now_iso(), 'sources': results, 'new_items': new_items, 'errors': errors}


@app.get('/health')
def health():
    return {'ok': True, 'last_scan_at': get_meta('last_scan_at')}

@app.post('/api/register-token')
async def register_token(request: Request):
    data = await request.json()
    token = clean_text(data.get('token', ''))
    if len(token) < 40:
        return JSONResponse({'ok': False, 'error': 'invalid token'}, status_code=400)
    t = now_iso()
    with db() as c:
        c.execute('INSERT INTO tokens(token,created_at,last_seen_at) VALUES(?,?,?) ON CONFLICT(token) DO UPDATE SET last_seen_at=excluded.last_seen_at', (token, t, t))
    return {'ok': True}

@app.get('/api/items')
def api_items(limit: int = 30):
    limit = min(max(limit, 1), 100)
    with db() as c:
        rows = c.execute('SELECT * FROM items ORDER BY first_seen_at DESC LIMIT ?', (limit,)).fetchall()
    return {'ok': True, 'items': [dict(r) for r in rows]}

@app.get('/api/status')
def api_status():
    with db() as c:
        token_count = c.execute('SELECT COUNT(*) n FROM tokens').fetchone()['n']
        item_count = c.execute('SELECT COUNT(*) n FROM items').fetchone()['n']
    return {
        'ok': True,
        'token_count': token_count,
        'item_count': item_count,
        'firebase_sender_ready': firebase_ready(),
        'last_scan_at': get_meta('last_scan_at'),
        'errors': json.loads(get_meta('last_scan_errors', '[]') or '[]'),
    }

@app.api_route('/api/scan', methods=['GET','POST'])
def api_scan(request: Request):
    scan_key = os.getenv('SCAN_KEY', '')
    if scan_key and request.headers.get('x-scan-key') != scan_key and request.query_params.get('key') != scan_key:
        return JSONResponse({'ok': False, 'error': 'unauthorized'}, status_code=401)
    return scan_all()

@app.get('/firebase-messaging-sw.js')
def firebase_messaging_sw():
    cfg = json.dumps(FIREBASE_CONFIG)
    js = """
importScripts('https://www.gstatic.com/firebasejs/10.13.2/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.13.2/firebase-messaging-compat.js');
firebase.initializeApp(%s);
const messaging = firebase.messaging();
messaging.onBackgroundMessage((payload) => {
  const n = payload.notification || {};
  const d = payload.data || {};
  self.registration.showNotification(n.title || d.title || '🎬 무대인사 알림', {
    body: n.body || d.body || '새 무대인사 소식이 있습니다.',
    icon: '/icon-192.png', badge: '/icon-192.png',
    data: { url: d.url || '/', item_id: d.item_id || '' },
    tag: d.item_id || undefined,
    renotify: true
  });
});
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(clients.openWindow(url));
});
""" % cfg
    return Response(js, media_type='application/javascript', headers={'Cache-Control':'no-store, no-cache, must-revalidate','Service-Worker-Allowed':'/'})

@app.get('/manifest.webmanifest')
def manifest():
    return JSONResponse({
        'name':'무대인사 알림','short_name':'무대인사알림','start_url':'/','scope':'/','display':'standalone',
        'background_color':'#ffffff','theme_color':'#111111',
        'icons':[{'src':'/icon-192.png','sizes':'192x192','type':'image/png'},{'src':'/icon-512.png','sizes':'512x512','type':'image/png'}]
    })

@app.get('/icon-192.png')
def icon_192(): return Response(Path('icon-192.png').read_bytes(), media_type='image/png')
@app.get('/icon-512.png')
def icon_512(): return Response(Path('icon-512.png').read_bytes(), media_type='image/png')

@app.get('/', response_class=HTMLResponse)
def home():
    cfg = json.dumps(FIREBASE_CONFIG)
    vapid = json.dumps(VAPID_KEY)
    return r'''<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#111111"><link rel="manifest" href="/manifest.webmanifest"><title>무대인사 알림</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,"Noto Sans KR",sans-serif;background:#f6f6f6;color:#111}main{max-width:680px;margin:0 auto;padding:28px 18px 90px}h1{font-size:38px;margin:0 0 4px}.sub{font-size:18px;color:#666;margin-bottom:24px}.card{background:#fff;border:1px solid #e6e6e6;border-radius:24px;padding:22px;margin-bottom:16px;box-shadow:0 2px 12px rgba(0,0,0,.03)}h2{margin:0 0 14px;font-size:23px}p{color:#666;font-size:16px;line-height:1.55}button,.btn{width:100%%;border-radius:18px;padding:17px;font-size:18px;font-weight:800;margin-top:12px;text-decoration:none;text-align:center;display:block}.primary{border:0;background:#111;color:#fff}.secondary{background:#fff;color:#111;border:1px solid #ddd}#install{display:none}.ok{color:#15803d}.bad{color:#b4233a}.warn{color:#a16207}.status{font-weight:800;line-height:1.5;margin-top:14px}.item{border-top:1px solid #eee;padding:18px 0}.item:first-child{border-top:0}.badge{display:inline-block;padding:4px 9px;border-radius:999px;background:#111;color:#fff;font-size:12px;font-weight:800;margin-right:6px}.new{background:#ef4444}.meta{font-size:14px;color:#666;line-height:1.65;margin-top:8px}.title{font-size:18px;font-weight:900;line-height:1.35;margin-top:7px}.mini{font-size:12px;color:#888;margin-top:8px}.row{display:grid;grid-template-columns:1fr 1fr;gap:8px}.row .btn{font-size:15px;padding:12px;margin-top:10px}
</style></head><body><main>
<h1>🎬 무대인사 알림</h1><div class="sub">새 무대인사 발견 → 즉시 알림 → 예매로 바로 연결</div>
<section class="card"><h2>🔔 내 휴대폰 연결</h2><p>영화·배우·극장 필터 없이 전체 무대인사를 받습니다.</p>
<button id="allow" class="primary">🔔 알림 연결/갱신</button><button id="install" class="secondary">📲 앱 설치</button><button id="copyToken" class="secondary" style="display:none">📋 FCM 토큰 복사</button>
<div id="status" class="status">연결 상태 확인 중…</div><div id="serverStatus" class="mini"></div></section>
<section class="card"><h2>⚡ 알림 방식</h2><p><b>공식 공지/예매 화면에서 새 무대인사를 감지</b>하면 알림을 보냅니다. 알림을 누르면 확보된 가장 직접적인 공식 링크로 이동합니다.</p><p class="mini">공식 사이트가 특정 회차 딥링크를 제공하지 않으면 해당 영화관의 가장 가까운 공식 예매/공지 화면으로 연결됩니다.</p></section>
<section class="card"><h2>🆕 최근 감지</h2><div id="items"><p>아직 감지 기록이 없습니다.</p></div></section>
<script type="module">
import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.13.2/firebase-app.js';
import { getMessaging, getToken, isSupported } from 'https://www.gstatic.com/firebasejs/10.13.2/firebase-messaging.js';
const firebaseConfig=%s; const vapidKey=%s;
const statusEl=document.getElementById('status'), serverStatus=document.getElementById('serverStatus'), allowBtn=document.getElementById('allow'), installBtn=document.getElementById('install'), copyTokenBtn=document.getElementById('copyToken'), itemsEl=document.getElementById('items');
let deferredPrompt=null;
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();deferredPrompt=e;installBtn.style.display='block'});
installBtn.onclick=async()=>{if(!deferredPrompt)return;deferredPrompt.prompt();await deferredPrompt.userChoice;deferredPrompt=null;installBtn.style.display='none'};
async function registerToken(t){try{await fetch('/api/register-token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:t})})}catch(e){}}
const oldToken=localStorage.getItem('fcm_token'); if(oldToken){copyTokenBtn.style.display='block';registerToken(oldToken)}
copyTokenBtn.onclick=async()=>{const t=localStorage.getItem('fcm_token');if(!t)return;await navigator.clipboard.writeText(t);statusEl.className='status ok';statusEl.textContent='✅ FCM 토큰 복사 완료'};
allowBtn.onclick=async()=>{try{statusEl.className='status';statusEl.textContent='연결 중…';if(!('serviceWorker'in navigator))throw new Error('서비스워커 미지원');if(!(await isSupported()))throw new Error('이 브라우저는 Firebase 웹 푸시 미지원');const p=await Notification.requestPermission();if(p!=='granted')throw new Error('알림 권한이 허용되지 않음');const oldReg=await navigator.serviceWorker.getRegistration('/');if(oldReg)await oldReg.unregister();const reg=await navigator.serviceWorker.register('/firebase-messaging-sw.js?v=7',{scope:'/'});await navigator.serviceWorker.ready;const fb=initializeApp(firebaseConfig);const msg=getMessaging(fb);const token=await getToken(msg,{vapidKey,serviceWorkerRegistration:reg});if(!token)throw new Error('FCM 토큰 발급 실패');localStorage.setItem('fcm_token',token);await registerToken(token);copyTokenBtn.style.display='block';statusEl.className='status ok';statusEl.textContent='✅ 휴대폰 푸시 연결 완료'}catch(err){statusEl.className='status bad';statusEl.textContent='연결 실패: '+(err?.message||String(err))}};
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
async function refresh(){try{const st=await (await fetch('/api/status')).json();serverStatus.textContent=`자동감지 최근 실행: ${st.last_scan_at||'아직 없음'} · 등록 기기 ${st.token_count}대 · 자동 푸시 ${st.firebase_sender_ready?'준비됨':'서버 인증 필요'}`;if(st.firebase_sender_ready)serverStatus.className='mini ok';else serverStatus.className='mini warn';const data=await (await fetch('/api/items?limit=20')).json();if(!data.items?.length){itemsEl.innerHTML='<p>아직 감지 기록이 없습니다.</p>';return}itemsEl.innerHTML=data.items.map((x,i)=>`<div class="item"><div><span class="badge ${i<3?'new':''}">${i<3?'NEW':'감지'}</span><span class="badge">${esc(x.chain)}</span></div><div class="title">${esc(x.title)}</div><div class="meta">📅 ${esc(x.date_text)} · ⏰ ${esc(x.time_text)}<br>🎤 ${esc(x.timing)}<br>👥 ${esc(x.participants)}</div><div class="row"><a class="btn primary" href="${esc(x.booking_url)}" target="_blank" rel="noopener">🎟️ 바로가기</a><a class="btn secondary" href="${esc(x.source_url)}" target="_blank" rel="noopener">📢 원문</a></div><div class="mini">최초 감지 ${esc(x.first_seen_at)}</div></div>`).join('')}catch(e){serverStatus.textContent='상태 확인 실패: '+e.message}}
refresh(); setInterval(refresh,30000);
</script></main></body></html>''' % (cfg, vapid)

@app.get("/api/test-push")
def test_push():
    item = {
        "id": "server-test-1",
        "chain": "TEST",
        "title": "🎬 서버 자동 푸시 성공!",
        "booking_url": "https://stage-greeting-alert.onrender.com",
        "timing": "테스트 알림"
    }
    return send_push(item)
