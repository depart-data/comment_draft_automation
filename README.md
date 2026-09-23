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

## 작동 방식

1. `config/week_utils.py`가 오늘 날짜를 기준으로 리포트 대상인 "지난 주" 범위(`week_start`~`week_end`)를 계산합니다.
2. `config/accounts.py`의 `AD_ACCOUNT_IDS`에 등록된 계정을 하나씩 순회합니다.
3. `extract/` 계층이 DB(`ad_performance_daily`, `ig_insights_total` 등)에서 원본 데이터를 가져와 집계합니다. **CTR·노출·클릭·팔로워 증감 같은 수치 계산은 전부 파이썬이 직접 계산**하고, AI에는 계산이 끝난 결과값만 넘깁니다(할루시네이션·재계산 오류 방지).
4. `ai/generate_report.py`가 `prompts/prompt_combined.py`의 정해진 형식 템플릿 + 집계된 데이터를 Gemini에 보내, **정해진 양식으로 텍스트만 정리**하도록 합니다(숫자 재계산이나 순서 변경은 금지).
5. `storage/save_draft.py`가 결과(또는 실패 시 에러 메시지)를 `sprint_notes_drafts` 테이블에 저장합니다. 같은 (계정, 스프린트) 조합이 이미 있으면 덮어씁니다.
6. 섹션4(SNS 브랜딩 전략 코멘트)는 AI를 쓰지 않고 사람이 직접 작성하는 영역입니다 — 할루시네이션 우려로 의도적으로 자동화하지 않았습니다.

## 실행 방법

1. 가상환경 생성 및 패키지 설치

```
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt   # Windows
```

2. `.env`, `client_secret.json`, `token.json` 파일 준비 (위 "실행 전 필요한 파일" 항목 참고, 김성원에게 요청)

3. 전체 계정 실행

```
./.venv/Scripts/python run_weekly_reports.py
```

기본값은 오늘 날짜 기준으로 "지난 주" 범위를 자동 계산해서 실행됩니다. 특정 주간을 강제로 지정하려면 `run_weekly_reports.py` 상단의 `WEEK_START`/`WEEK_END` 주석을 풀고 값을 넣으면 됩니다.

이 파일 자체는 스케줄러가 아니라, 실행하면 즉시 1회 동작합니다. "매주 월/화 자동 실행"은 이 파일을 호출하는 별도의 외부 스케줄러(Windows 작업 스케줄러 등)가 담당합니다.

## 브랜드/계정 추가·수정

`config/accounts.py`의 `AD_ACCOUNT_IDS`, `TARGET_SEGMENTS`를 수정합니다. 계정 추가 시 DB의 `ad_accounts` 테이블에 해당 계정이 이미 등록되어 있어야 하고, `ad_performance_daily`에 실제 성과 데이터가 있는지 확인하는 걸 추천합니다 (데이터가 없으면 에러는 안 나지만 계속 "데이터 없음" 실패로만 기록됩니다).

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
