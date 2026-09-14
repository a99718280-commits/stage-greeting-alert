from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app=FastAPI(title="무대인사 알림")

PAGE="""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#111111"><title>무대인사 알림</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f5f7;font-family:system-ui,-apple-system,"Noto Sans KR",sans-serif;color:#151515}
main{max-width:430px;min-height:100vh;margin:auto;background:#fff;padding:28px 20px}
h1{font-size:28px;margin:4px 0}.sub{color:#777;margin:7px 0 28px}
.card{border:1px solid #e8e8ea;border-radius:20px;padding:20px;margin:14px 0}
.live{font-size:18px;font-weight:900}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;background:#18a558;margin-right:7px}
.small{font-size:13px;color:#707070;line-height:1.6}.btn{width:100%;padding:15px;border:0;border-radius:14px;background:#111;color:#fff;font-size:16px;font-weight:900}
.demo{padding:14px;border-radius:14px;background:#f6f6f7;margin-top:12px}
</style></head><body><main>
<h1>🎬 무대인사 알림</h1><div class="sub">뜨면 무조건 알려드립니다.</div>
<div class="card"><div class="live"><span class="dot"></span>전체 무대인사 감시 ON</div>
<p class="small">영화·배우·극장을 따로 고르지 않는 전체 알림 방식입니다.</p>
<button class="btn" id="allow">🔔 알림 허용</button></div>
<div class="card"><b>알림 예시</b><div class="demo">🔔 <b>무대인사 떴어!</b><br><span class="small">영화명 · 극장 · 날짜/시간<br>알림을 누르면 예매 페이지로 이동</span></div></div>
<div class="card"><b>서비스 상태</b><p class="small">웹앱 배포 준비 완료. 실제 영화관 감지/원격 푸시는 다음 연결 단계에서 활성화합니다.</p></div>
<script>
document.getElementById("allow").onclick=async()=>{
 if(!("Notification" in window)){alert("이 브라우저에서는 알림을 지원하지 않습니다.");return}
 let p=await Notification.requestPermission();
 if(p==="granted") new Notification("무대인사 알림",{body:"알림 허용 완료 🔔"});
 else alert("알림 권한이 허용되지 않았습니다.");
};
</script></main></body></html>"""

@app.get("/",response_class=HTMLResponse)
def home(): return PAGE
@app.get("/health")
def health(): return {"ok":True}
