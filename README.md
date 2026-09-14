# 무대인사 알림 - 서비스워커 수정 버전

Firebase Messaging 서비스워커를 classic worker + compat SDK 방식으로 수정했습니다.

## 테스트
배포 완료 후 Android Chrome에서 페이지를 새로 열고 `알림 허용`을 누릅니다.
`✅ 알림 연결 성공!`이 표시되면 서비스워커 등록과 FCM 토큰 발급까지 성공한 것입니다.
