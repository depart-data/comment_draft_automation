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

## 프로젝트 구조

```
comment_draft_automation/
├── run_weekly_reports.py        # 최상위 진입점 — 전체 계정 순회하며 주간 리포트 생성·저장
│
├── config/
│   ├── accounts.py              # 처리할 ad_account_id 목록, 계정별 핵심 타겟층
│   ├── settings.py              # Gemini 모델명, 분당 요청 제한(RATE_LIMIT_PER_MINUTE) 등
│   └── week_utils.py            # 리포트 대상 "지난 주" 범위(week_start/week_end) 계산
│
├── extract/                     # DB에서 원본 데이터를 뽑아 가공(집계·계산)하는 계층
│   ├── db_connect.py            # PostgreSQL 접속 및 쿼리 실행
│   ├── db_extract_daily.py      # 요일별 원재료 데이터 추출
│   ├── build_campaign_report.py # 캠페인·광고 단위 트래픽 성과 + 섹션3 조립 (메인)
│   ├── build_section1_highlights.py  # 섹션1(주간 전체 요약) 데이터 계산
│   ├── build_section2_highlights.py  # 섹션2(콘텐츠별 상세 브리핑) 데이터 계산
│   ├── build_section3_comparisons.py # 섹션3(계정 성장지표) WoW/MoM/초기대비 계산
│   ├── build_section4_context.py     # 섹션4 참고자료용 — 아직 미구현
│   └── client_utils.py          # client_id, 스프린트 번호 등 조회 유틸
│
├── ai/
│   ├── gemini_client.py         # Gemini API 호출 (속도 제한·재시도 포함)
│   └── generate_report.py       # 캠페인별 + 섹션3 AI 생성 흐름 조립
│
├── prompts/
│   ├── prompt_combined.py       # 섹션1·2·3 프롬프트 템플릿 (실제 사용 중)
│   └── prompt_section4.py       # 섹션4 요약 프롬프트 — 아직 미구현
│
├── storage/
│   └── save_draft.py            # sprint_notes_drafts 테이블에 최종 결과 저장
│
├── legacy/                      # 이전 방식(섹션별 개별 호출) 코드 — 현재 미사용, 참고용 보관
│
├── README/                      # 참고 문서 (스키마, 논의 기록 등)
│   ├── reference_notes.md
│   └── schema.md
│
├── test_section4_summary.py     # 섹션4 요약 성능 테스트 스크립트
└── requirements.txt
```
