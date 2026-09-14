from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response, JSONResponse

app = FastAPI()

FIREBASE_CONFIG = {
    "apiKey": "AIzaSyCXvA9n9doSv3OZIzbFc7Xr1EqUeYteTk4",
    "authDomain": "stage-greeting-alert.firebaseapp.com",
    "projectId": "stage-greeting-alert",
    "storageBucket": "stage-greeting-alert.firebasestorage.app",
    "messagingSenderId": "192680261195",
    "appId": "1:192680261195:web:7d5f65afcaf248d77fbfce",
}
VAPID_KEY = "BPgkBtTm3c0ZTNU33gEj5AmkcIBcekGM5GXsT7rxgPCgire7KBizpImFLpOAJm3iRzcltBHW5CDfn0W1ek8vUvw"

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/firebase-messaging-sw.js")
def firebase_sw():
    # Compat SDK is used deliberately: it is safe to load directly in a classic service worker.
    js = f"""
importScripts('https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging-compat.js');

firebase.initializeApp({{
  apiKey: "{FIREBASE_CONFIG['apiKey']}",
  authDomain: "{FIREBASE_CONFIG['authDomain']}",
  projectId: "{FIREBASE_CONFIG['projectId']}",
  storageBucket: "{FIREBASE_CONFIG['storageBucket']}",
  messagingSenderId: "{FIREBASE_CONFIG['messagingSenderId']}",
  appId: "{FIREBASE_CONFIG['appId']}"
}});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {{
  const title = (payload.notification && payload.notification.title) || '🎬 무대인사 떴어!';
  const options = {{
    body: (payload.notification && payload.notification.body) || '새 무대인사 일정이 등록됐습니다.',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    data: payload.data || {{}}
  }};
  self.registration.showNotification(title, options);
}});

self.addEventListener('notificationclick', (event) => {{
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(clients.openWindow(url));
}});
"""
    return Response(js, media_type="application/javascript", headers={"Cache-Control": "no-store"})

@app.get("/manifest.webmanifest")
def manifest():
    return JSONResponse({
        "name": "무대인사 알림",
        "short_name": "무대인사알림",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#111111",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}
        ]
    }, media_type="application/manifest+json")

@app.get("/")
def home():
    cfg = FIREBASE_CONFIG
    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#111111">
<link rel="manifest" href="/manifest.webmanifest">
<title>무대인사 알림</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;font-family:system-ui,-apple-system,"Noto Sans KR",sans-serif;background:#fff;color:#111}}
.wrap{{max-width:620px;margin:auto;padding:38px 32px 80px}} h1{{font-size:38px;margin:0 0 6px}} .sub{{font-size:21px;color:#777;margin-bottom:48px}}
.card{{border:1px solid #ddd;border-radius:30px;padding:30px;margin-bottom:22px}} h2{{font-size:25px;margin:0 0 24px}}
.desc{{color:#777;font-size:17px;line-height:1.6}} button{{width:100%;border:0;border-radius:22px;padding:22px;font-size:22px;font-weight:800;margin-top:18px}}
.primary{{background:#111;color:white}} .install{{background:white;border:1px solid #ddd;color:#111}} #status{{font-weight:700;line-height:1.6;margin-top:18px}}
.ok{{color:#16883f}} .bad{{color:#b21f35}} .example{{background:#f5f5f5;border-radius:20px;padding:22px}}
</style>
</head>
<body><main class="wrap">
<h1>🎬 무대인사 알림</h1><div class="sub">뜨면 무조건 알려드립니다.</div>
<section class="card">
<h2>🟢 전체 무대인사 감시 ON</h2>
<p class="desc">영화·배우·극장을 따로 고르지 않는 전체 알림 방식입니다.</p>
<button class="primary" id="allow">🔔 알림 허용</button>
<button class="install" id="install" hidden>📲 앱 설치</button>
<div id="status">아직 이 기기의 푸시 알림이 연결되지 않았습니다.</div>
</section>
<section class="card"><h2>알림 예시</h2><div class="example"><b>🔔 무대인사 떴어!</b><br><span class="desc">영화명 · 극장 · 날짜/시간<br>알림을 누르면 예매 페이지로 이동</span></div></section>
<section class="card"><h2>서비스 상태</h2><p class="desc">FCM 서비스워커 수정 버전입니다. 알림 허용 후 이 기기의 FCM 토큰 발급 여부를 확인합니다.</p></section>
</main>
<script type="module">
import {{ initializeApp }} from "https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js";
import {{ getMessaging, getToken, onMessage, isSupported }} from "https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging.js";

const firebaseConfig = {cfg};
const vapidKey = "{VAPID_KEY}";
const status = document.getElementById("status");
const allow = document.getElementById("allow");
let deferredPrompt = null;

window.addEventListener("beforeinstallprompt", e => {{
  e.preventDefault(); deferredPrompt = e;
  document.getElementById("install").hidden = false;
}});
document.getElementById("install").onclick = async () => {{
  if (!deferredPrompt) return;
  deferredPrompt.prompt(); await deferredPrompt.userChoice; deferredPrompt = null;
}};

allow.onclick = async () => {{
  try {{
    if (!("serviceWorker" in navigator)) throw new Error("이 브라우저는 서비스워커를 지원하지 않습니다.");
    if (!(await isSupported())) throw new Error("이 브라우저에서는 Firebase 웹 푸시를 사용할 수 없습니다.");

    status.className = ""; status.textContent = "연결 중…";
    const permission = await Notification.requestPermission();
    if (permission !== "granted") throw new Error("알림 권한이 허용되지 않았습니다.");

    // Remove an older broken registration, then register the corrected worker.
    const old = await navigator.serviceWorker.getRegistration("/");
    if (old) await old.unregister();
    const reg = await navigator.serviceWorker.register("/firebase-messaging-sw.js?v=4", {{scope:"/"}});
    await navigator.serviceWorker.ready;

    const app = initializeApp(firebaseConfig);
    const messaging = getMessaging(app);
    const token = await getToken(messaging, {{vapidKey, serviceWorkerRegistration: reg}});
    if (!token) throw new Error("FCM 토큰을 발급받지 못했습니다.");

    status.className = "ok";
    status.innerHTML = "✅ 알림 연결 성공!<br>이 기기의 FCM 토큰이 정상 발급됐습니다.";
    console.log("FCM_TOKEN", token);
    onMessage(messaging, payload => console.log("FCM foreground message", payload));
  }} catch (e) {{
    console.error(e);
    status.className = "bad";
    status.textContent = "연결 실패: " + (e && e.message ? e.message : String(e));
  }}
}};
</script></body></html>"""
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})

@app.get("/icon-192.png")
def icon192():
    return Response(Path("/dev/null").read_bytes() if False else ICON192, media_type="image/png")

@app.get("/icon-512.png")
def icon512():
    return Response(ICON512, media_type="image/png")

# Tiny valid PNGs are replaced by uploaded icon files in normal deployment.
from pathlib import Path
def _load(name):
    p = Path(__file__).with_name(name)
    return p.read_bytes() if p.exists() else b""
ICON192 = _load("icon-192.png")
ICON512 = _load("icon-512.png")
