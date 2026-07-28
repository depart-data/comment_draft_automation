"""
extract/db_extract_daily.py

섹션1(주간전체요약)·섹션2(콘텐츠별 상세 브리핑)에 필요한 원본 데이터를
"요일별로 쪼갠 원재료" 형태의 객체로 저장합니다.

목적: CTR, CPC 같은 파생 지표를 미리 계산해서 저장하지 않고,
      impressions_monday, clicks_monday 처럼 요일별 원본값만 저장해서
      나중에 필요한 어떤 지표든 자유롭게 조합해 계산할 수 있게 합니다.

기본 세팅(인자 생략 시): 파일 상단 "⚙️ 설정" 블록의 값을 사용합니다.
바꿔야 할 변수는 3개뿐입니다: DEFAULT_IG_ID(계정), DEFAULT_START_DATE/END_DATE(조회 기간),
DEFAULT_CAMPAIGN_TYPE(트래픽/구매전환 구분).

캠페인 유형 필터링은 ad_name 접두어가 아니라 campaigns.objective를 기준으로 합니다.
(광고명에 "트래픽"/"구매전환" 접두어가 붙은 광고는 전체의 6~7%뿐이라는 것이 확인되어,
 접두어 방식에서 objective 방식으로 전환함 — 2026-07-13)

사전 준비:
    extract/db_connect.py, config/settings.py 가 있는 프로젝트 구조여야 합니다.
"""

import os
import sys
import pandas as pd

# 프로젝트 루트(extract/의 상위 폴더)를 sys.path에 추가해 config 패키지를 찾을 수 있게 함
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_connect import run_query
from config.settings import OBJECTIVE_MAP


# ══════════════════════════════════════════════════════════════
#  ⚙️  설정 — 매주/매 브랜드 리포트 작성 시 여기 3개만 바꾸면 됩니다
# ══════════════════════════════════════════════════════════════
DEFAULT_IG_ID = 19                    # 조회할 인스타 계정 번호 (ig_accounts.id)
DEFAULT_START_DATE = "2026-06-29"     # 조회 기간 시작일 (반드시 '월요일')
DEFAULT_END_DATE = "2026-07-05"       # 조회 기간 종료일 (반드시 '일요일')
DEFAULT_CAMPAIGN_TYPE = "traffic"     # "traffic"(트래픽) 또는 "sales"(구매전환)
# ══════════════════════════════════════════════════════════════

# 요일 순서 (월~일 고정 순서로 항상 동일하게 키가 생성되도록)
WEEKDAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# 요일별로 쪼갤 지표 목록 (ad_performance_daily 원본 컬럼 기준)
DAILY_METRICS = ["impressions", "clicks", "reach", "spend"]

# 요일별로 계산해서 함께 저장하는 파생 지표 (원재료를 조합해 계산)
DERIVED_METRICS = ["ctr", "cpc", "cpm"]


# ------------------------------------------------------------
# 1. 원본 데이터 가져오기 (광고 단위, 날짜별로 SUM — 연령/성별은 합쳐서 광고 총계만)
# ------------------------------------------------------------

def get_daily_ad_raw(
    ig_id: int = DEFAULT_IG_ID,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    campaign_type: str = DEFAULT_CAMPAIGN_TYPE,
) -> pd.DataFrame:
    """
    특정 계정(ig_id)의 특정 주간에 새로 생성된 광고들의 성과를
    ad_id + as_of_date(일자) 단위로 SUM해서 가져옵니다. (연령/성별은 합산)

    필터 기준:
    1) fb_created_time — 그 주간에 새로 생성된 광고만 포함
    2) as_of_date — 그 주간에 발생한 성과만 집계
    3) campaigns.objective — campaign_type("traffic"/"sales")에 해당하는 캠페인만
       (ad_name 접두어 방식은 커버리지가 6~7%뿐이라 폐기함)

    Returns:
        pandas.DataFrame (컬럼: ad_id, ad_name, as_of_date,
                           impressions, clicks, reach, spend)
    """
    objectives = OBJECTIVE_MAP[campaign_type]
    query = """
        SELECT
            a.id AS ad_id,
            a.ad_name,
            p.as_of_date,
            SUM(p.impressions) AS impressions,
            SUM(p.clicks) AS clicks,
            SUM(p.reach) AS reach,
            SUM(p.spend) AS spend
        FROM ads a
        JOIN ad_accounts acc ON a.account_id = acc.id
        JOIN ad_sets s ON a.ad_set_id = s.id
        JOIN campaigns c ON s.campaign_id = c.id
        JOIN ad_performance_daily p ON p.ad_id = a.id
        WHERE acc.ig_account_id = %s
          AND a.fb_created_time >= %s
          AND a.fb_created_time < (%s::date + INTERVAL '1 day')
          AND p.as_of_date BETWEEN %s AND %s
          AND c.objective = ANY(%s)
        GROUP BY a.id, a.ad_name, p.as_of_date
        ORDER BY a.id, p.as_of_date;
    """
    return run_query(
        query,
        params=(ig_id, start_date, end_date, start_date, end_date, list(objectives)),
    )


# ------------------------------------------------------------
# 2. 요일별 원재료 객체로 재구성
# ------------------------------------------------------------

def build_daily_components(
    ig_id: int = DEFAULT_IG_ID,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    campaign_type: str = DEFAULT_CAMPAIGN_TYPE,
) -> list:
    """
    광고별로 impressions_monday, clicks_monday 같은 요일별 원재료 키를 가진
    딕셔너리를 만들어 리스트로 반환합니다.

    예시 반환값 (광고 1개):
        {
            "ad_id": 8829,
            "ad_name": "트래픽 S24-1 ...",
            "impressions_monday": 500, "impressions_tuesday": 420, ...,
            "clicks_monday": 12, "clicks_tuesday": 9, ...,
            "reach_monday": 480, ...,
            "spend_monday": 15000.0, ...,
            "ctr_monday": 2.4, "ctr_tuesday": 2.14, ...,
            "cpc_monday": 1250.0, ...,
            "cpm_monday": 30000.0, ...,
        }

    해당 날짜에 데이터가 없는 요일은 원재료(impressions 등)는 0으로,
    파생 지표(ctr/cpc/cpm)는 분모가 0이라 계산 불가하므로 None으로 채웁니다.
    """
    raw_df = get_daily_ad_raw(ig_id, start_date, end_date, campaign_type)

    if raw_df.empty:
        return []

    # as_of_date -> 요일 이름 매핑 (start_date를 월요일로 간주)
    date_to_weekday = {}
    start = pd.to_datetime(start_date)
    for offset, weekday_name in enumerate(WEEKDAY_NAMES):
        date_to_weekday[(start + pd.Timedelta(days=offset)).strftime("%Y-%m-%d")] = weekday_name

    results = []
    for (ad_id, ad_name), group in raw_df.groupby(["ad_id", "ad_name"]):
        record = {"ad_id": ad_id, "ad_name": ad_name}

        # 모든 요일 x 모든 지표를 우선 0으로 초기화 (데이터 없는 날 대비)
        for metric in DAILY_METRICS:
            for weekday_name in WEEKDAY_NAMES:
                record[f"{metric}_{weekday_name}"] = 0

        # 실제 값으로 채워넣기
        for _, row in group.iterrows():
            date_str = row["as_of_date"].strftime("%Y-%m-%d") if hasattr(row["as_of_date"], "strftime") else str(row["as_of_date"])
            weekday_name = date_to_weekday.get(date_str)
            if weekday_name is None:
                # start_date~end_date 범위를 벗어난 날짜(방어적 처리)
                continue
            for metric in DAILY_METRICS:
                record[f"{metric}_{weekday_name}"] = row[metric] if pd.notna(row[metric]) else 0

        # 파생 지표(CTR, CPC, CPM)를 요일별로 계산해서 추가
        # impressions/clicks/spend가 이미 요일별로 채워져 있으므로 그대로 조합
        for weekday_name in WEEKDAY_NAMES:
            imp = record[f"impressions_{weekday_name}"]
            clk = record[f"clicks_{weekday_name}"]
            spd = record[f"spend_{weekday_name}"]
            record[f"ctr_{weekday_name}"] = round(clk / imp * 100, 2) if imp else None
            record[f"cpc_{weekday_name}"] = round(spd / clk, 2) if clk else None
            record[f"cpm_{weekday_name}"] = round(spd / imp * 1000, 2) if imp else None

        results.append(record)

    return results


# ------------------------------------------------------------
# 2b. 성별 x 연령대 원본 데이터 (요일 분해 없이, 주간 전체 합산)
# ------------------------------------------------------------

def get_demo_raw(
    ig_id: int = DEFAULT_IG_ID,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    campaign_type: str = DEFAULT_CAMPAIGN_TYPE,
) -> pd.DataFrame:
    """
    특정 계정(ig_id)의 특정 주간에 새로 생성된 광고들의 성과를
    ad_id + age_range + gender 단위로 SUM해서 가져옵니다. (요일 분해 없음, 주간 전체 합산)

    필터 기준은 get_daily_ad_raw()와 동일합니다 (campaigns.objective 기준).
    """
    objectives = OBJECTIVE_MAP[campaign_type]
    query = """
        SELECT
            a.id AS ad_id,
            a.ad_name,
            p.age_range,
            p.gender,
            SUM(p.impressions) AS impressions,
            SUM(p.clicks) AS clicks,
            SUM(p.reach) AS reach,
            SUM(p.spend) AS spend
        FROM ads a
        JOIN ad_accounts acc ON a.account_id = acc.id
        JOIN ad_sets s ON a.ad_set_id = s.id
        JOIN campaigns c ON s.campaign_id = c.id
        JOIN ad_performance_daily p ON p.ad_id = a.id
        WHERE acc.ig_account_id = %s
          AND a.fb_created_time >= %s
          AND a.fb_created_time < (%s::date + INTERVAL '1 day')
          AND p.as_of_date BETWEEN %s AND %s
          AND c.objective = ANY(%s)
        GROUP BY a.id, a.ad_name, p.age_range, p.gender
        ORDER BY a.id, p.age_range, p.gender;
    """
    return run_query(
        query,
        params=(ig_id, start_date, end_date, start_date, end_date, list(objectives)),
    )


def build_demo_components(
    ig_id: int = DEFAULT_IG_ID,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    campaign_type: str = DEFAULT_CAMPAIGN_TYPE,
) -> list:
    """
    광고별로 성별x연령대 조합 데이터를 요일 분해 없이(주간 전체 합산) 객체로 저장합니다.

    예시 반환값 (광고 1개):
        {
            "ad_id": 8829,
            "ad_name": "트래픽 S24-1 ...",
            "demo_breakdown": [
                {"age_range": "18-24", "gender": "male", "impressions": 500, "clicks": 12, "reach": 480, "spend": 15000.0},
                {"age_range": "18-24", "gender": "female", "impressions": 300, "clicks": 8, "reach": 290, "spend": 9000.0},
                ...
            ]
        }

    CTR 등 파생 지표는 여기서 계산하지 않습니다 — 필요할 때 demo_breakdown 안의
    impressions/clicks를 조합해서 계산하세요.
    """
    raw_df = get_demo_raw(ig_id, start_date, end_date, campaign_type)

    if raw_df.empty:
        return []

    results = []
    for (ad_id, ad_name), group in raw_df.groupby(["ad_id", "ad_name"]):
        demo_breakdown = []
        for _, row in group.iterrows():
            demo_breakdown.append({
                "age_range": row["age_range"],
                "gender": row["gender"],
                "impressions": int(row["impressions"]) if pd.notna(row["impressions"]) else 0,
                "clicks": int(row["clicks"]) if pd.notna(row["clicks"]) else 0,
                "reach": int(row["reach"]) if pd.notna(row["reach"]) else 0,
                "spend": float(row["spend"]) if pd.notna(row["spend"]) else 0.0,
            })
        results.append({
            "ad_id": ad_id,
            "ad_name": ad_name,
            "demo_breakdown": demo_breakdown,
        })

    return results


# ------------------------------------------------------------
# 3. 섹션3(계정 성장지표) — 요일별 원재료
# ------------------------------------------------------------

# 섹션3에서 요일별로 쪼갤 지표 목록 (ig_insights_total 원본 컬럼 기준)
# 주의: followers_count는 성격상 "누적 스냅샷"이라, 활용 시 SUM이 아니라
#       마지막 요일(일요일) 값만 사용해야 합니다. 나머지 4개는 일별 증분값이라
#       SUM해서 사용합니다.
# 참고: follows/unfollows는 값이 대부분 0 또는 NULL로 확인되어 (수집 파이프라인
#       이슈로 추정) 신뢰할 수 없는 컬럼으로 판단, 목록에서 제외했습니다.
ACCOUNT_DAILY_METRICS = [
    "followers_count",
    "total_views",
    "profile_views",
    "likes",
    "total_interactions",
]


def get_daily_account_raw(
    ig_id: int = DEFAULT_IG_ID,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
) -> pd.DataFrame:
    """
    특정 계정(ig_id)의 특정 주간, ig_insights_total의 일별 원본 값을
    가공 없이 그대로 가져옵니다.

    Returns:
        pandas.DataFrame (컬럼: as_of_date, followers_count, total_views,
                           profile_views, likes, total_interactions)
    """
    query = """
        SELECT
            as_of_date,
            followers_count,
            total_views,
            profile_views,
            likes,
            total_interactions
        FROM ig_insights_total
        WHERE ig_id = %s AND as_of_date BETWEEN %s AND %s
        ORDER BY as_of_date;
    """
    return run_query(query, params=(ig_id, start_date, end_date))


def build_daily_account_components(
    ig_id: int = DEFAULT_IG_ID,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
):
    """
    섹션3(팔로워 및 계정 성장지표)의 7개 지표를 요일별 원재료 키로 가진
    딕셔너리 하나로 반환합니다 (계정 단위라 광고처럼 여러 개가 아니라 1개).

    예시 반환값:
        {
            "ig_id": 19,
            "followers_count_monday": 1581, "followers_count_tuesday": 1634, ...,
            "total_views_monday": 61658, ...,
            "profile_views_monday": 2942, ...,
            "likes_monday": 212, ...,
            "total_interactions_monday": 735, ...,
        }

    해당 날짜에 데이터가 없는 요일은 0으로 채웁니다.
    WoW 증감·성장률 등 파생 지표는 여기서 계산하지 않습니다 — 필요할 때
    이 원재료를 조합해서 계산하세요.
    주의: followers_count는 누적 스냅샷이므로 SUM하지 말고 마지막 요일 값만 사용하세요.
    """
    raw_df = get_daily_account_raw(ig_id, start_date, end_date)

    if raw_df.empty:
        return None

    date_to_weekday = {}
    start = pd.to_datetime(start_date)
    for offset, weekday_name in enumerate(WEEKDAY_NAMES):
        date_to_weekday[(start + pd.Timedelta(days=offset)).strftime("%Y-%m-%d")] = weekday_name

    record = {"ig_id": ig_id}
    for metric in ACCOUNT_DAILY_METRICS:
        for weekday_name in WEEKDAY_NAMES:
            record[f"{metric}_{weekday_name}"] = 0

    for _, row in raw_df.iterrows():
        date_str = row["as_of_date"].strftime("%Y-%m-%d") if hasattr(row["as_of_date"], "strftime") else str(row["as_of_date"])
        weekday_name = date_to_weekday.get(date_str)
        if weekday_name is None:
            continue
        for metric in ACCOUNT_DAILY_METRICS:
            record[f"{metric}_{weekday_name}"] = row[metric] if pd.notna(row[metric]) else 0

    return record


if __name__ == "__main__":
    components = build_daily_components()

    if not components:
        print(f"⚠️ ig_id={DEFAULT_IG_ID}, 기간={DEFAULT_START_DATE}~{DEFAULT_END_DATE}에 해당하는 데이터가 없습니다.")
    else:
        print(f"=== [섹션1·2] 요일별 원재료 + 파생지표 객체 (광고 {len(components)}개) ===\n")
        for record in components:
            print(f"[{record['ad_name']}] (ad_id={record['ad_id']})")
            for metric in DAILY_METRICS:
                values = [f"{weekday_name}={record[f'{metric}_{weekday_name}']}" for weekday_name in WEEKDAY_NAMES]
                print(f"  {metric}: " + ", ".join(values))
            for metric in DERIVED_METRICS:
                values = [f"{weekday_name}={record[f'{metric}_{weekday_name}']}" for weekday_name in WEEKDAY_NAMES]
                print(f"  [파생] {metric}: " + ", ".join(values))
            print()

    print("\n" + "=" * 60)

    demo_components = build_demo_components()
    if not demo_components:
        print(f"⚠️ 성별x연령대 데이터가 없습니다.")
    else:
        print(f"=== [섹션2] 성별x연령대 원본 객체 (요일 분해 없음, 주간 전체 합산, 광고 {len(demo_components)}개) ===\n")
        for record in demo_components:
            print(f"[{record['ad_name']}] (ad_id={record['ad_id']})")
            for demo in record["demo_breakdown"]:
                print(f"  {demo['gender']} / {demo['age_range']}: impressions={demo['impressions']}, clicks={demo['clicks']}, reach={demo['reach']}, spend={demo['spend']}")
            print()

    print("\n" + "=" * 60)

    account_record = build_daily_account_components()
    if account_record is None:
        print(f"⚠️ ig_id={DEFAULT_IG_ID}, 기간={DEFAULT_START_DATE}~{DEFAULT_END_DATE}에 해당하는 계정 성장 데이터가 없습니다.")
    else:
        print(f"=== [섹션3] 요일별 원재료 객체 (ig_id={DEFAULT_IG_ID}) ===\n")
        for metric in ACCOUNT_DAILY_METRICS:
            values = [f"{weekday_name}={account_record[f'{metric}_{weekday_name}']}" for weekday_name in WEEKDAY_NAMES]
            print(f"{metric}: " + ", ".join(values))

        print("\n=== 활용 예시: 원재료로 지표 계산 ===")
        total_views_sum = sum(account_record[f"total_views_{w}"] for w in WEEKDAY_NAMES)
        print(f"총 조회수 (7일 SUM) = {total_views_sum}")
        followers_last_day = account_record[f"followers_count_{WEEKDAY_NAMES[-1]}"]
        print(f"팔로워 수 (스냅샷, 일요일 값만 사용) = {followers_last_day}  ※ SUM 아님, 누적값이므로 마지막 요일만")
