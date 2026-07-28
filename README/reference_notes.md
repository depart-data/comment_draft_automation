# db_extract_daily.py 데이터 참고 문서

작성일: 2026-07-10
대상 파일: `db_extract_daily.py`
기본 세팅: `ig_id=19`, `2026-06-29(월)~2026-07-05(일)`, `name_prefix='트래픽'`

---

## 설계 원칙

CTR, CPC 같은 파생 지표를 미리 계산해서 저장하지 않고, `impressions_monday`,
`clicks_monday`처럼 **요일별 원재료**를 먼저 저장한 뒤, 필요한 지표를 그 위에서
조합해 계산하는 방식으로 설계함. 단, CTR/CPC/CPM은 이후 요청에 따라 예외적으로
요일별로 미리 계산해서 함께 저장해둠.

---

## 1. 저장된 객체 (구현 완료)

### ① 섹션1·2 — 광고 단위, 요일별 원재료 + 파생지표

- **함수**: `build_daily_components(ig_id, start_date, end_date, name_prefix)`
- **참조 테이블**: `ads` + `ad_accounts` + `ad_performance_daily`
- **필터**: `fb_created_time`(그 주간 생성) + `as_of_date`(그 주간 성과) 이중 필터, `ad_name LIKE '트래픽%'`
- **반환 형태**: 광고별 딕셔너리의 **리스트** (광고 5개 → 리스트 길이 5)

| 키 패턴 | 설명 | 개수 |
|---|---|---|
| `ad_id`, `ad_name` | 식별자 | 2개 |
| `impressions_{요일}`, `clicks_{요일}`, `reach_{요일}`, `spend_{요일}` | 원재료 (4지표 × 7요일) | 28개 |
| `ctr_{요일}`, `cpc_{요일}`, `cpm_{요일}` | 파생지표 (3지표 × 7요일) | 21개 |

- 데이터 없는 요일: 원재료 `0`, 파생지표 `None`
- 검증 완료: 요일별 합산 = 성별·연령대 합산 = 기존 주간 검증값 (S24-1 기준 노출 2,996 / 클릭 49 3중 일치)

### ② 섹션2 — 광고 단위, 성별×연령대 원본 (요일 분해 없음)

- **함수**: `build_demo_components(ig_id, start_date, end_date, name_prefix)`
- **참조 테이블**: 위와 동일
- **반환 형태**: 광고별 딕셔너리의 리스트, 각 안에 `demo_breakdown` 리스트 포함

```
{
  "ad_id": 8829,
  "ad_name": "...",
  "demo_breakdown": [
    {"age_range": "18-24", "gender": "male", "impressions": .., "clicks": .., "reach": .., "spend": ..},
    ... (연령 7종 × 성별 최대 3종 조합, 데이터 있는 조합만)
  ]
}
```

- 주간 전체 합산 (요일 구분 없음)

### ③ 섹션3 — 계정 단위, 요일별 원재료

- **함수**: `build_daily_account_components(ig_id, start_date, end_date)`
- **참조 테이블**: `ig_insights_total` (섹션1·2와 무관한 별도 소스, 계정 전체 통합 지표)
- **반환 형태**: 계정 전체 딕셔너리 **1개** (리스트 아님)

| 키 패턴 | 설명 | 비고 |
|---|---|---|
| `followers_count_{요일}` | 팔로워 수 | ⚠️ 누적 스냅샷 — SUM 금지, 마지막 요일(일요일)만 사용 |
| `total_views_{요일}` | 조회수 | 일별 증분값, SUM 가능 (단, 이번 주는 월요일 값 오염 확인됨) |
| `profile_views_{요일}` | 프로필 방문 | 일별 증분값, SUM 가능 |
| `likes_{요일}` | 좋아요 | 일별 증분값, SUM 가능 |
| `total_interactions_{요일}` | 전체 상호작용 | 일별 증분값, SUM 가능 |

- `follows`/`unfollows`는 데이터 대부분 0/NULL로 신뢰 불가 확인되어 **제외**

---

## 2. 아직 계산 안 한 것

### 이미 가져온 객체만으로 계산 가능 (추가 DB 조회 불필요)

| 항목 | 재료 | 계산 방법 |
|---|---|---|
| 섹션1 - CTR 높은 순 나열 | ① 객체의 `ctr_{요일}` 또는 주간 합산 CTR | 광고 리스트를 CTR 기준 정렬 |
| 섹션1 - 반응 연령·성별 TOP3 | ② 객체의 `demo_breakdown` | 모든 광고의 `demo_breakdown`을 연령·성별별로 합산 후 상위 3개 추출 |
| 섹션2 - 성별 노출·클릭 비중(%) | ② 객체의 `demo_breakdown` | `gender`별로 SUM 후 광고 전체 대비 비율 계산 |
| 섹션2 - 성별 CTR | ② 객체의 `demo_breakdown` | `gender`별 `clicks÷impressions×100` |
| 섹션2 - 연령·성별 TOP3 (광고별) | ② 객체의 `demo_breakdown` | 광고 1개 안에서 `impressions`/`clicks` 기준 상위 3개 추출 |

### 추가 DB 조회가 필요함 (예외)

| 항목 | 이유 |
|---|---|
| 섹션3 - 팔로워/조회수/방문/좋아요/상호작용 **증감·성장률(WoW)** | 현재 객체는 "이번 주"만 담고 있음. 비교하려면 `build_daily_account_components()`를 **직전 주간(날짜를 7일씩 밀어서)**으로 한 번 더 호출해 "지난 주" 객체를 별도로 가져와야 함 |

---

## 3. 알려진 데이터 이슈 (참고)

- **6/29(월) `total_views` 등 오염**: 세부 컬럼(`views_ad`, `views_post` 등)이 비어있는데 `total_views`만 비정상적으로 큰 값(61,658). 6월 말까지 "주간 집계 → 월요일에 몰아서 저장"하던 방식이 원인으로 추정, 6월 말부터 일별 수집으로 전환되어 이후 데이터는 정상화된 것으로 확인됨(7/6 이후 정상 패턴 확인).
- **`follows`/`unfollows` 신뢰 불가**: 대부분 0 또는 NULL, 원인 미확인. 코드에서 완전히 제외 처리함.
- **팔로워 수 실제 리포트 값 불일치**: 리포트 작성자가 대시보드를 옮겨 적는 과정에서 오기로 판단, 별도 조치 불필요로 결론.
