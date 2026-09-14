from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response, JSONResponse

app = FastAPI(title="무대인사 알림")

FIREBASE_CONFIG = {
    "apiKey": "AIzaSyCXvA9n9doSv3OZIzbFc7Xr1EqUeYteTk4",
    "authDomain": "stage-greeting-alert.firebaseapp.com",
    "projectId": "stage-greeting-alert",
    "storageBucket": "stage-greeting-alert.firebasestorage.app",
    "messagingSenderId": "192680261195",
    "appId": "1:192680261195:web:7d5f65afcaf248d77fbfce",
}
VAPID_KEY = "BPgkBtTm3c0ZTNU33gEj5AmkcIBcekGM5GXsT7rxgPCgire7KBizpImFLpOAJm3iRzcltBHW5CDfn0W1ek8vUvw"

PAGE = f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#111111">
<link rel="manifest" href="/manifest.webmanifest">
<title>무대인사 알림</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f4f5f7;font-family:system-ui,-apple-system,"Noto Sans KR",sans-serif;color:#151515}}
main{{max-width:430px;min-height:100vh;margin:auto;background:#fff;padding:28px 20px}}
h1{{font-size:28px;margin:4px 0}}.sub{{color:#777;margin:7px 0 28px}}
.card{{border:1px solid #e8e8ea;border-radius:20px;padding:20px;margin:14px 0}}
.live{{font-size:18px;font-weight:900}}.dot{{display:inline-block;width:10px;height:10px;border-radius:50%;background:#18a558;margin-right:7px}}
.small{{font-size:13px;color:#707070;line-height:1.6}}.btn{{width:100%;padding:15px;border:0;border-radius:14px;background:#111;color:#fff;font-size:16px;font-weight:900;cursor:pointer}}
.btn:disabled{{opacity:.55;cursor:default}}.demo{{padding:14px;border-radius:14px;background:#f6f6f7;margin-top:12px}}
.ok{{color:#138a4b;font-weight:800}}.warn{{color:#b45a00;font-weight:800}}.err{{color:#b00020;font-weight:800}}
.tokenbox{{display:none;margin-top:12px;padding:12px;background:#f6f6f7;border-radius:12px;word-break:break-all;font-size:11px;color:#555}}
.copy{{display:none;margin-top:8px;width:100%;padding:11px;border:1px solid #ddd;border-radius:11px;background:#fff;font-weight:800;cursor:pointer}}
</style>
</head>
<body><main>
<h1>🎬 무대인사 알림</h1><div class="sub">뜨면 무조건 알려드립니다.</div>
<div class="card">
  <div class="live"><span class="dot"></span>전체 무대인사 감시 ON</div>
  <p class="small">영화·배우·극장을 따로 고르지 않는 전체 알림 방식입니다.</p>
  <button class="btn" id="allow">🔔 알림 허용</button>
  <p class="small" id="status">아직 이 기기의 푸시 알림이 연결되지 않았습니다.</p>
  <div class="tokenbox" id="token"></div>
  <button class="copy" id="copy">테스트용 토큰 복사</button>
</div>
<div class="card"><b>알림 예시</b><div class="demo">🔔 <b>무대인사 떴어!</b><br><span class="small">영화명 · 극장 · 날짜/시간<br>알림을 누르면 예매 페이지로 이동</span></div></div>
<div class="card"><b>서비스 상태</b><p class="small" id="service">웹 푸시 연결 준비 완료. 알림을 허용하면 이 기기의 FCM 푸시 토큰을 발급합니다.</p></div>

<script src="https://www.gstatic.com/firebasejs/10.12.5/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.12.5/firebase-messaging-compat.js"></script>
<script>
const firebaseConfig = {FIREBASE_CONFIG};
const vapidKey = "{VAPID_KEY}";
firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();
const allowBtn = document.getElementById('allow');
const statusEl = document.getElementById('status');
const tokenEl = document.getElementById('token');
const copyBtn = document.getElementById('copy');

function setStatus(text, cls='') {{
  statusEl.className = 'small ' + cls;
  statusEl.textContent = text;
}}

async function registerPush() {{
  allowBtn.disabled = true;
  try {{
    if (!('serviceWorker' in navigator)) throw new Error('이 브라우저는 서비스워커를 지원하지 않습니다.');
    if (!('Notification' in window)) throw new Error('이 브라우저는 알림을 지원하지 않습니다.');
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {{
      setStatus('알림 권한이 허용되지 않았습니다. 브라우저 설정에서 알림을 허용해주세요.', 'warn');
      return;
    }}
    setStatus('푸시 알림을 연결하는 중…');
    const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
    await navigator.serviceWorker.ready;
    const token = await messaging.getToken({{vapidKey, serviceWorkerRegistration: registration}});
    if (!token) throw new Error('FCM 토큰을 발급받지 못했습니다.');
    localStorage.setItem('fcm_token', token);
    tokenEl.textContent = token;
    tokenEl.style.display = 'block';
    copyBtn.style.display = 'block';
    allowBtn.textContent = '✅ 알림 연결 완료';
    setStatus('이 기기의 푸시 알림 연결 완료 🔔', 'ok');
  }} catch (e) {{
    console.error(e);
    setStatus('연결 실패: ' + (e.message || e), 'err');
  }} finally {{
    allowBtn.disabled = false;
  }}
}}

allowBtn.addEventListener('click', registerPush);
copyBtn.addEventListener('click', async () => {{
  const token = tokenEl.textContent;
  try {{
    await navigator.clipboard.writeText(token);
    copyBtn.textContent = '✅ 복사됨';
    setTimeout(() => copyBtn.textContent = '테스트용 토큰 복사', 1500);
  }} catch {{
    alert('토큰을 길게 눌러 직접 복사해주세요.');
  }}
}});

messaging.onMessage((payload) => {{
  console.log('Foreground FCM:', payload);
  const title = payload?.notification?.title || '🔔 무대인사 떴어!';
  const body = payload?.notification?.body || '새 무대인사 일정이 등록됐습니다.';
  if (Notification.permission === 'granted') {{
    new Notification(title, {{body, data: payload?.data || {{}}}});
  }}
}});

window.addEventListener('load', async () => {{
  const saved = localStorage.getItem('fcm_token');
  if (Notification.permission === 'granted' && saved) {{
    tokenEl.textContent = saved;
    tokenEl.style.display = 'block';
    copyBtn.style.display = 'block';
    allowBtn.textContent = '✅ 알림 연결 완료';
    setStatus('이 기기의 푸시 알림이 연결되어 있습니다. 🔔', 'ok');
  }}
}});
</script>
</main></body></html>'''

SERVICE_WORKER = f'''importScripts("https://www.gstatic.com/firebasejs/10.12.5/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.12.5/firebase-messaging-compat.js");

firebase.initializeApp({FIREBASE_CONFIG});
const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {{
  const title = (payload.notification && payload.notification.title) || "🔔 무대인사 떴어!";
  const options = {{
    body: (payload.notification && payload.notification.body) || "새 무대인사 일정이 등록됐습니다.",
    data: payload.data || {{}}
  }};
  self.registration.showNotification(title, options);
}});

self.addEventListener("notificationclick", (event) => {{
  event.notification.close();
  const url = (event.notification.data && (event.notification.data.url || event.notification.data.link)) || "/";
  event.waitUntil(clients.matchAll({{type:"window", includeUncontrolled:true}}).then((list) => {{
    for (const client of list) {{
      if (client.url === url && "focus" in client) return client.focus();
    }}
    if (clients.openWindow) return clients.openWindow(url);
  }}));
}});
'''

MANIFEST = '''{
  "name": "무대인사 알림",
  "short_name": "무대인사알림",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#111111",
  "description": "CGV·롯데시네마·메가박스 무대인사 알림"
}'''

@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE

@app.get("/firebase-messaging-sw.js")
def firebase_messaging_sw():
    return Response(SERVICE_WORKER, media_type="application/javascript", headers={"Cache-Control": "no-cache"})

@app.get("/manifest.webmanifest")
def manifest():
    return Response(MANIFEST, media_type="application/manifest+json")

@app.get("/health")
def health():
    return JSONResponse({"ok": True, "push_client": "fcm-ready"})
