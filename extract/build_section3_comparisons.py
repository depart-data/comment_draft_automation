"""
extract/build_section3_comparisons.py

섹션3(계정 성장지표)의 비교 지표를 만듭니다.

- 팔로워: 초기대비 / 전주대비(WoW) / 전월대비(MoM) / 메인 타겟층별 전주대비
- 조회수: 전주대비(WoW)만
- 프로필방문: 전주대비(WoW)만
- 좋아요: 전주대비(WoW)만
- 전체상호작용: 전주대비(WoW) / 전월대비(MoM)

초기대비 기준일 = min(client_created_at, 최초 데이터수집일)
  - client_created_at이 실제 데이터수집일보다 늦게 찍히는 예외 케이스(예: coralier_official)를
    방어하기 위해 두 값 중 더 이른 날짜를 사용합니다.
  - connected_at은 전체 계정이 특정 날짜(2026-02-03)에 일괄 재연결된 흔적으로 확인되어
    기준일로 사용하지 않습니다.

※ 예전 db_extract.py에 있던 get_account_growth_raw/_wow/build_section3 로직을
  이 파일로 완전히 흡수했습니다 (db_extract.py는 더 이상 사용하지 않음).

사전 준비:
    extract/db_connect.py, config/settings.py 가 있는 프로젝트 구조여야 합니다.
"""

import os
import sys
import pandas as pd

# 프로젝트 루트(extract/의 상위 폴더)를 sys.path에 추가해 config 패키지를 찾을 수 있게 함
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_connect import run_query
from config.settings import WOW_OFFSET_DAYS, MOM_OFFSET_DAYS


# ------------------------------------------------------------
# 0. 계정 전체 성장지표 원본 + WoW 계산 (구 db_extract.py에서 흡수)
# ------------------------------------------------------------

def get_account_growth_raw(ig_id: int, start_date: str, end_date: str):
    """
    특정 계정(ig_id)의 특정 주간(start_date~end_date)에 대해
    - 누적값(followers_count)은 그 주간 마지막 날짜의 값
    - 증분값(views, profile_views, likes, total_interactions)은 그 주간 합계
    를 가져옵니다.

    Returns:
        dict 또는 None (해당 기간 데이터가 없는 경우)
    """
    query = """
        SELECT
            (SELECT followers_count
             FROM ig_insights_total
             WHERE ig_id = %s AND as_of_date BETWEEN %s AND %s
             ORDER BY as_of_date DESC
             LIMIT 1) AS followers_count,
            SUM(total_views) AS total_views,
            SUM(profile_views) AS profile_views,
            SUM(likes) AS likes,
            SUM(total_interactions) AS total_interactions
        FROM ig_insights_total
        WHERE ig_id = %s AND as_of_date BETWEEN %s AND %s;
    """
    df = run_query(query, params=(ig_id, start_date, end_date, ig_id, start_date, end_date))

    if df.empty or df.iloc[0]["followers_count"] is None:
        return None

    row = df.iloc[0]
    return {
        "followers_count": int(row["followers_count"]) if row["followers_count"] is not None else 0,
        "total_views": int(row["total_views"]) if row["total_views"] is not None else 0,
        "profile_views": int(row["profile_views"]) if row["profile_views"] is not None else 0,
        "likes": int(row["likes"]) if row["likes"] is not None else 0,
        "total_interactions": int(row["total_interactions"]) if row["total_interactions"] is not None else 0,
    }


def _wow(current: float, previous: float) -> dict:
    """
    이번 주 값(current)과 지난 주 값(previous)을 비교해서
    증감(delta)과 성장률(growth_pct)을 계산합니다.
    """
    delta = current - previous
    growth_pct = round(delta / previous * 100, 1) if previous else None
    return {"value": current, "delta": delta, "growth_pct": growth_pct}


def build_section3(ig_id: int, start_date: str, end_date: str) -> dict:
    """
    섹션3(팔로워 및 계정 성장지표) 5개 지표에 대해, 직전 동일 길이 주간과
    비교해서 증감·성장률을 계산합니다.
    """
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)

    prev_start = start - pd.Timedelta(days=WOW_OFFSET_DAYS)
    prev_end = end - pd.Timedelta(days=WOW_OFFSET_DAYS)

    current = get_account_growth_raw(ig_id, start_date, end_date)
    previous = get_account_growth_raw(ig_id, prev_start.strftime("%Y-%m-%d"), prev_end.strftime("%Y-%m-%d"))

    if current is None:
        return {"error": f"ig_id={ig_id}, 기간={start_date}~{end_date}에 해당하는 계정 성장 데이터가 없습니다."}

    if previous is None:
        # 직전 주 데이터가 없으면 증감/성장률은 계산할 수 없음
        return {
            "warning": f"직전 주({prev_start.date()}~{prev_end.date()}) 데이터가 없어 증감·성장률을 계산할 수 없습니다.",
            "followers": {"value": current["followers_count"], "delta": None, "growth_pct": None},
            "views": {"value": current["total_views"], "delta": None, "growth_pct": None},
            "profile_views": {"value": current["profile_views"], "delta": None, "growth_pct": None},
            "likes": {"value": current["likes"], "delta": None, "growth_pct": None},
            "total_interactions": {"value": current["total_interactions"], "delta": None, "growth_pct": None},
        }

    return {
        "followers": _wow(current["followers_count"], previous["followers_count"]),
        "views": _wow(current["total_views"], previous["total_views"]),
        "profile_views": _wow(current["profile_views"], previous["profile_views"]),
        "likes": _wow(current["likes"], previous["likes"]),
        "total_interactions": _wow(current["total_interactions"], previous["total_interactions"]),
    }


# ------------------------------------------------------------
# 1. 초기대비 기준일 계산
# ------------------------------------------------------------

def get_baseline_date(ig_id: int) -> str:
    """
    초기대비 기준일 = min(client_created_at, 최초 데이터수집일)
    """
    query = """
        SELECT
            c.created_at AS client_created_at,
            (SELECT MIN(as_of_date) FROM ig_insights_total WHERE ig_id = %s) AS first_data_date
        FROM ig_accounts ig
        JOIN business_portfolios bp ON ig.business_portfolio_id = bp.id
        JOIN clients c ON bp.client_id = c.id
        WHERE ig.id = %s;
    """
    df = run_query(query, params=(ig_id, ig_id))
    if df.empty:
        return None

    row = df.iloc[0]
    client_created = pd.to_datetime(row["client_created_at"]).date() if pd.notna(row["client_created_at"]) else None
    first_data = pd.to_datetime(row["first_data_date"]).date() if pd.notna(row["first_data_date"]) else None

    candidates = [d for d in [client_created, first_data] if d is not None]
    if not candidates:
        return None
    return min(candidates).strftime("%Y-%m-%d")


def get_followers_near_date(ig_id: int, target_date: str):
    """
    target_date 이후 가장 가까운 날짜의 followers_count를 가져옵니다.
    (target_date 자체에 데이터가 없을 수 있으므로 '이후 최초 데이터'로 근사)
    """
    query = """
        SELECT as_of_date, followers_count
        FROM ig_insights_total
        WHERE ig_id = %s AND as_of_date >= %s
        ORDER BY as_of_date ASC
        LIMIT 1;
    """
    df = run_query(query, params=(ig_id, target_date))
    if df.empty:
        return None
    return {
        "as_of_date": str(df.iloc[0]["as_of_date"]),
        "followers_count": int(df.iloc[0]["followers_count"]),
    }


def build_followers_baseline_comparison(ig_id: int, current_start: str, current_end: str) -> dict:
    """
    팔로워 초기대비 비교: 기준일 시점 팔로워 수 vs 현재(이번 기간 마지막 날) 팔로워 수
    """
    baseline_date = get_baseline_date(ig_id)
    if baseline_date is None:
        return {"error": "초기대비 기준일을 찾을 수 없습니다 (클라이언트/데이터 정보 없음)."}

    baseline = get_followers_near_date(ig_id, baseline_date)
    current = get_account_growth_raw(ig_id, current_start, current_end)

    if baseline is None or current is None:
        return {"error": "초기대비 비교에 필요한 데이터가 부족합니다."}

    comparison = _wow(current["followers_count"], baseline["followers_count"])
    return {
        "baseline_date_target": baseline_date,   # 계산된 기준일 (실제 데이터가 없을 수 있음)
        "baseline_date_actual": baseline["as_of_date"],  # 실제로 값을 가져온 날짜
        **comparison,
    }


# ------------------------------------------------------------
# 2. MoM (기본 28일 전 비교, config.settings.MOM_OFFSET_DAYS 기준)
# ------------------------------------------------------------

def build_mom_metric(ig_id: int, current_start: str, current_end: str, metric: str) -> dict:
    """
    지정 지표를 MOM_OFFSET_DAYS(기본 28일, 4주) 전 같은 길이의 기간과 비교합니다.
    metric: "followers_count" 또는 "total_interactions" 등 get_account_growth_raw의 키
    """
    start = pd.to_datetime(current_start)
    end = pd.to_datetime(current_end)

    prev_start = (start - pd.Timedelta(days=MOM_OFFSET_DAYS)).strftime("%Y-%m-%d")
    prev_end = (end - pd.Timedelta(days=MOM_OFFSET_DAYS)).strftime("%Y-%m-%d")

    current = get_account_growth_raw(ig_id, current_start, current_end)
    previous = get_account_growth_raw(ig_id, prev_start, prev_end)

    if current is None:
        return {"error": f"이번 기간({current_start}~{current_end}) 데이터가 없습니다."}
    if previous is None:
        return {
            "warning": f"{MOM_OFFSET_DAYS}일 전 기간({prev_start}~{prev_end}) 데이터가 없어 MoM 계산 불가",
            "value": current[metric], "delta": None, "growth_pct": None,
            "prev_period": (prev_start, prev_end),
        }

    result = _wow(current[metric], previous[metric])
    result["prev_period"] = (prev_start, prev_end)
    return result


# ------------------------------------------------------------
# 2b. 메인 타겟층(성별×연령대) 팔로워 증감
# ------------------------------------------------------------

def get_segment_followers_at_period_end(ig_id: int, age_range: str, gender: str, start_date: str, end_date: str):
    """
    지정 기간(start_date~end_date) 내, 해당 연령·성별 조합의 가장 마지막 날짜
    팔로워 수(스냅샷)를 가져옵니다. ig_insights_demographics 기준.
    """
    query = """
        SELECT as_of_date, followers
        FROM ig_insights_demographics
        WHERE ig_id = %s AND age_range = %s AND gender = %s
          AND as_of_date BETWEEN %s AND %s
        ORDER BY as_of_date DESC
        LIMIT 1;
    """
    df = run_query(query, params=(ig_id, age_range, gender, start_date, end_date))
    if df.empty or pd.isna(df.iloc[0]["followers"]):
        return None
    return int(df.iloc[0]["followers"])


def build_target_segment_followers_wow(ig_id: int, week_start: str, week_end: str, target_segments: list) -> list:
    """
    지정한 타겟 세그먼트(연령·성별 조합) 목록에 대해, 팔로워 수의
    전주대비(WoW)를 각각 계산합니다. (스냅샷 비교, SUM 아님)

    target_segments 예시: [("18-24", "F"), ("25-34", "M")]
    """
    start = pd.to_datetime(week_start)
    end = pd.to_datetime(week_end)
    prev_start = (start - pd.Timedelta(days=WOW_OFFSET_DAYS)).strftime("%Y-%m-%d")
    prev_end = (end - pd.Timedelta(days=WOW_OFFSET_DAYS)).strftime("%Y-%m-%d")

    results = []
    for age_range, gender in target_segments:
        current = get_segment_followers_at_period_end(ig_id, age_range, gender, week_start, week_end)
        previous = get_segment_followers_at_period_end(ig_id, age_range, gender, prev_start, prev_end)

        if current is None:
            results.append({
                "age_range": age_range, "gender": gender,
                "error": f"이번 기간({week_start}~{week_end}) 데이터가 없습니다.",
            })
            continue

        if previous is None:
            results.append({
                "age_range": age_range, "gender": gender,
                "warning": f"지난 주({prev_start}~{prev_end}) 데이터가 없어 WoW 계산 불가",
                "wow": {"value": current, "delta": None, "growth_pct": None},
            })
            continue

        results.append({
            "age_range": age_range, "gender": gender,
            "wow": _wow(current, previous),
        })

    return results


# ------------------------------------------------------------
# 3. 전체 조립
# ------------------------------------------------------------

def build_section3_comparisons(ig_id: int, week_start: str, week_end: str, target_segments: list = None) -> dict:
    """
    섹션3 5개 지표에 대해 요구된 비교(초기대비/WoW/MoM)를 전부 계산합니다.
    target_segments가 주어지면, 메인 타겟층(연령·성별)별 팔로워 WoW도 함께 계산합니다.
    """
    wow_all = build_section3(ig_id, week_start, week_end)

    if "error" in wow_all:
        return {"error": wow_all["error"]}

    followers_baseline = build_followers_baseline_comparison(ig_id, week_start, week_end)
    followers_mom = build_mom_metric(ig_id, week_start, week_end, "followers_count")
    interactions_mom = build_mom_metric(ig_id, week_start, week_end, "total_interactions")

    target_segment_results = (
        build_target_segment_followers_wow(ig_id, week_start, week_end, target_segments)
        if target_segments else []
    )

    return {
        "followers": {
            "wow": wow_all.get("followers"),
            "mom": followers_mom,
            "baseline": followers_baseline,
            "target_segments": target_segment_results,
        },
        "views": {
            "wow": wow_all.get("views"),
        },
        "profile_views": {
            "wow": wow_all.get("profile_views"),
        },
        "likes": {
            "wow": wow_all.get("likes"),
        },
        "total_interactions": {
            "wow": wow_all.get("total_interactions"),
            "mom": interactions_mom,
        },
    }


if __name__ == "__main__":
    IG_ID = 19
    WEEK_START = "2026-07-06"
    WEEK_END = "2026-07-12"
    TARGET_SEGMENTS = [("18-24", "F"), ("18-24", "M"), ("25-34", "F"), ("25-34", "M")]

    result = build_section3_comparisons(IG_ID, WEEK_START, WEEK_END, target_segments=TARGET_SEGMENTS)

    if "error" in result:
        print(f"⚠️ {result['error']}")
    else:
        print("=== 팔로워 ===")
        print(f"  전주대비: {result['followers']['wow']}")
        print(f"  전월대비: {result['followers']['mom']}")
        print(f"  초기대비: {result['followers']['baseline']}")
        print("  메인 타겟층별 팔로워 전주대비:")
        for seg in result["followers"]["target_segments"]:
            print(f"    {seg}")

        print("\n=== 조회수 ===")
        print(f"  전주대비: {result['views']['wow']}")

        print("\n=== 프로필방문 ===")
        print(f"  전주대비: {result['profile_views']['wow']}")

        print("\n=== 좋아요 ===")
        print(f"  전주대비: {result['likes']['wow']}")

        print("\n=== 전체상호작용 ===")
        print(f"  전주대비: {result['total_interactions']['wow']}")
        print(f"  전월대비: {result['total_interactions']['mom']}")
