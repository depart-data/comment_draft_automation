# comment_draft_automation

디파트 주간 광고 성과 코멘트 초안을 작성해주는 파이썬 파이프라인 코드입니다.

## 실행 전 필요한 파일 (git에 포함되지 않음)

아래 3개 파일은 `.gitignore`에 등록되어 있어 저장소에 올라가지 않습니다.
로컬에 없다면 **김성원**에게 요청주세요.

| 파일 | 용도 |
|---|---|
| `.env` | DB 접속 정보(`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`), `GEMINI_API_KEY`, `META_ACCESS_TOKEN` |
| `client_secret.json` | Google OAuth 클라이언트 시크릿 |
| `token.json` | Google OAuth 액세스/리프레시 토큰 (만료 시 `client_secret.json`으로 재인증하여 재발급) |

세 파일 모두 저장소 루트(`comment_draft_automation/`)에 위치해야 합니다.
