
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response, JSONResponse
from pathlib import Path
import json

app = FastAPI()

FIREBASE_CONFIG = {'apiKey': 'AIzaSyCXvA9n9doSv3OZIzbFc7XrlEqUeYteTk4', 'authDomain': 'stage-greeting-alert.firebaseapp.com', 'projectId': 'stage-greeting-alert', 'storageBucket': 'stage-greeting-alert.firebasestorage.app', 'messagingSenderId': '192680261195', 'appId': '1:192680261195:web:7d5f65afcaf248d77fbfce'}
VAPID_KEY = 'BPgkBtTm3c0ZTNU33gEj5AmkcIBcekGM5GXsT7rxgPCgire7KBizpImFLpOAJm3iRzcltBHW5CDfn0W1ek8vUvw'

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/firebase-messaging-sw.js")
def firebase_messaging_sw():
    cfg = json.dumps(FIREBASE_CONFIG)
    js = """
importScripts('https://www.gstatic.com/firebasejs/10.13.2/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.13.2/firebase-messaging-compat.js');

firebase.initializeApp(%s);

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  const n = payload.notification || {};
  self.registration.showNotification(
    n.title || '🎬 무대인사 알림',
    {
      body: n.body || '새 무대인사 소식이 있습니다.',
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      data: payload.data || {}
    }
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url =
    (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(clients.openWindow(url));
});
""" % cfg
    return Response(
        js,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Service-Worker-Allowed": "/",
        },
    )

@app.get("/manifest.webmanifest")
def manifest():
    return JSONResponse({
        "name": "무대인사 알림",
        "short_name": "무대인사알림",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#111111",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    })

@app.get("/icon-192.png")
def icon_192():
    return Response(Path("icon-192.png").read_bytes(), media_type="image/png")

@app.get("/icon-512.png")
def icon_512():
    return Response(Path("icon-512.png").read_bytes(), media_type="image/png")

@app.get("/", response_class=HTMLResponse)
def home():
    cfg = json.dumps(FIREBASE_CONFIG)
    vapid = json.dumps(VAPID_KEY)
    return """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="theme-color" content="#111111">
  <link rel="manifest" href="/manifest.webmanifest">
  <title>무대인사 알림</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, "Noto Sans KR", sans-serif;
      background: #fff;
      color: #111;
    }
    main {
      max-width: 620px;
      margin: 0 auto;
      padding: 38px 30px 90px;
    }
    h1 { font-size: 42px; margin: 0 0 8px; }
    .sub { font-size: 22px; color: #777; margin-bottom: 42px; }
    .card {
      border: 1px solid #ddd;
      border-radius: 28px;
      padding: 30px;
      margin-bottom: 24px;
    }
    h2 { margin: 0 0 22px; font-size: 27px; }
    p { color: #707070; font-size: 18px; line-height: 1.65; }
    button {
      width: 100%%;
      border-radius: 23px;
      padding: 22px;
      font-size: 23px;
      font-weight: 800;
      margin-top: 18px;
    }
    #allow {
      border: 0;
      background: #111;
      color: #fff;
    }
    #install {
      background: #fff;
      color: #111;
      border: 1px solid #ddd;
      display: none;
    }
    #status {
      margin-top: 20px;
      font-weight: 800;
      line-height: 1.6;
      word-break: break-word;
    }
    .ok { color: #15803d; }
    .bad { color: #b4233a; }
  </style>
</head>
<body>
<main>
  <h1>🎬 무대인사 알림</h1>
  <div class="sub">뜨면 무조건 알려드립니다.</div>

  <section class="card">
    <h2>🟢 전체 무대인사 감시 ON</h2>
    <p>영화·배우·극장을 따로 고르지 않는 전체 알림 방식입니다.</p>
    <button id="allow">🔔 알림 허용</button>
    <button id="install">📲 앱 설치</button>
    <div id="status">아직 이 기기의 푸시 알림이 연결되지 않았습니다.</div>
  </section>

  <section class="card">
    <h2>알림 예시</h2>
    <p><b>🔔 무대인사 떴어!</b><br>영화명 · 극장 · 날짜/시간<br>알림을 누르면 예매 페이지로 이동</p>
  </section>

  <script type="module">
    import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.13.2/firebase-app.js';
    import { getMessaging, getToken, isSupported } from 'https://www.gstatic.com/firebasejs/10.13.2/firebase-messaging.js';

    const firebaseConfig = %s;
    const vapidKey = %s;
    const statusEl = document.getElementById('status');
    const allowBtn = document.getElementById('allow');
    const installBtn = document.getElementById('install');

    let deferredPrompt = null;

    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      deferredPrompt = e;
      installBtn.style.display = 'block';
    });

    installBtn.addEventListener('click', async () => {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      installBtn.style.display = 'none';
    });

    allowBtn.addEventListener('click', async () => {
      try {
        statusEl.className = '';
        statusEl.textContent = '연결 중…';

        if (!('serviceWorker' in navigator)) {
          throw new Error('이 브라우저는 서비스워커를 지원하지 않습니다.');
        }

        if (!(await isSupported())) {
          throw new Error('이 브라우저에서는 Firebase 웹 푸시를 사용할 수 없습니다.');
        }

        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
          throw new Error('알림 권한이 허용되지 않았습니다.');
        }

        const oldReg = await navigator.serviceWorker.getRegistration('/');
        if (oldReg) {
          await oldReg.unregister();
        }

        const reg = await navigator.serviceWorker.register(
          '/firebase-messaging-sw.js?v=6',
          { scope: '/' }
        );
        await navigator.serviceWorker.ready;

        const firebaseApp = initializeApp(firebaseConfig);
        const messaging = getMessaging(firebaseApp);

        const token = await getToken(messaging, {
          vapidKey,
          serviceWorkerRegistration: reg
        });

        if (!token) {
          throw new Error('FCM 토큰을 발급받지 못했습니다.');
        }

        localStorage.setItem('fcm_token', token);
        statusEl.className = 'ok';
        statusEl.textContent = '✅ 알림 연결 성공! 이 기기의 FCM 푸시 토큰이 정상 발급됐습니다.';
        console.log('FCM token:', token);
      } catch (err) {
        console.error(err);
        statusEl.className = 'bad';
        statusEl.textContent = '연결 실패: ' + (err?.message || String(err));
      }
    });
  </script>
</main>
</body>
</html>""" % (cfg, vapid)
