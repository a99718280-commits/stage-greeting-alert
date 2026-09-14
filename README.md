# 무대인사 알림 — 자동감지 버전

- CGV / 롯데시네마 / 메가박스 공식 페이지에서 무대인사 관련 신규 항목 감지
- 새 항목 중복 방지 저장
- 참석자 / 상영 전·후 / 날짜·시간을 공식 텍스트에서 추출 가능한 범위로 표시
- FCM 푸시 알림 클릭 시 확보된 가장 직접적인 공식 링크로 이동
- GitHub Actions가 5분 간격으로 `/api/scan` 호출

## 중요
자동 푸시 전송에는 Firebase 서비스 계정이 필요합니다. JSON 내용을 GitHub에 올리거나 채팅에 붙여넣지 마세요.
Render의 **Secret File** 로 `firebase-service-account.json`을 등록해 `/etc/secrets/firebase-service-account.json` 경로로만 사용하세요.

공식 사이트에 공개 API가 없는 영역은 페이지 구조 변경/접근정책에 따라 감지가 늦거나 누락될 수 있습니다. 우회·차단회피는 하지 않습니다.
