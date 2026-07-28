"""
extract/build_campaign_report.py

캠페인·광고 단위 트래픽 성과 + 계정 성장지표(섹션3)를 뽑아내는 메인
오케스트레이터입니다.

로직 (2026-07-28 개편):
1) 대상: ad_account_id 직접 지정
2) 캠페인 식별: campaigns.fb_created_time이 지정 주간의 월~금 사이인 캠페인 중,
   트래픽 또는 구매전환 목적이면서 캠페인명에
   config.settings.CAMPAIGN_NAME_KEYWORDS(depart/디파트) 포함된 캠페인만 식별
   (스프린트 번호 필터는 제거됨 — clients.sprint_anchor_number가 클라이언트
    대부분 미설정(기본값 1) 상태로 확인되어, 계산된 번호를 신뢰할 수 없었음.
    개발팀이 각 클라이언트의 정확한 sprint_anchor_number를 재입력하기 전까지는
    이 필터를 사용하지 않기로 함)
   config.accounts.NO_NAME_FILTER_ACCOUNTS(디파트 자체 운영 계정)는
   이름 조건 자체를 건너뜁니다.
3) 성과 집계: 캠페인 시작 요일과 무관하게, 그 주 일요일까지 전체 기간으로 고정
4) 섹션1·2는 "캠페인별로 각각 따로" 생성합니다 (전체 합산 X). 같은 주에
   정규 주간 캠페인과 특별 캠페인(예: "팔로워 상위 5개")이 함께 잡혀도,
   섞어서 하나로 뭉치지 않고 캠페인명과 함께 각각 블록으로 보여줘서
   사람이 눈으로 구분할 수 있게 합니다. (구매전환은 리포트에 출력하지 않음
   — 기존에 확정된 방침대로, 트래픽만 리포트에 반영)
5) 계정 성장지표(섹션3)는 캠페인과 무관한 계정 전체 값이므로, 딱 1번만 출력

사전 준비:
    extract/db_connect.py, extract/client_utils.py,
    extract/build_section1_highlights.py, extract/build_section2_highlights.py,
    extract/build_section3_comparisons.py,
    config/settings.py, config/accounts.py 가 있는 프로젝트 구조여야 합니다.
"""

import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_connect import run_query
from build_section1_highlights import build_section1_highlights
from build_section2_highlights import build_section2_highlights
from build_section3_comparisons import build_section3_comparisons
from config.settings import OBJECTIVE_MAP, CAMPAIGN_NAME_KEYWORDS, CREATION_WINDOW_DAYS, WOW_OFFSET_DAYS
from config.accounts import get_target_segments, is_name_filter_exempt


AD_ACCOUNT_ID = 14
WEEK_START = "2026-07-20"
WEEK_END = "2026-07-26"

OBJECTIVE_TO_TYPE = {obj: t for t, objs in OBJECTIVE_MAP.items() for obj in objs}


def get_campaigns_in_creation_window(ad_account_id: int, week_start: str) -> pd.DataFrame:
    """
    지정 주간의 월요일~금요일 사이에 생성된 캠페인 중,
    트래픽 또는 구매전환 목적이면서 캠페인명에
    config.settings.CAMPAIGN_NAME_KEYWORDS 중 하나가 포함된 캠페인만 식별합니다.
    (스프린트 번호 필터는 데이터 신뢰도 문제로 제거됨 — 위 모듈 docstring 참고)

    config.accounts.NO_NAME_FILTER_ACCOUNTS에 등록된 계정(디파트 자체 운영
    계정)은 이름 조건 자체를 건너뛰고 objective/기간 조건만 적용합니다.
    """
    creation_end = (pd.to_datetime(week_start) + pd.Timedelta(days=CREATION_WINDOW_DAYS)).strftime("%Y-%m-%d")
    all_objectives = [obj for objs in OBJECTIVE_MAP.values() for obj in objs]

    if is_name_filter_exempt(ad_account_id):
        query = """
            SELECT id AS campaign_id, name AS campaign_name, objective, fb_created_time
            FROM campaigns
            WHERE ad_account_id = %s
              AND fb_created_time >= %s
              AND fb_created_time < (%s::date + INTERVAL '1 day')
              AND objective = ANY(%s)
            ORDER BY fb_created_time;
        """
        params = [ad_account_id, week_start, creation_end, all_objectives]
        return run_query(query, params=tuple(params))

    name_conditions = " OR ".join(["name ILIKE %s"] * len(CAMPAIGN_NAME_KEYWORDS))
    name_params = [f"%{kw}%" for kw in CAMPAIGN_NAME_KEYWORDS]

    query = f"""
        SELECT id AS campaign_id, name AS campaign_name, objective, fb_created_time
        FROM campaigns
        WHERE ad_account_id = %s
          AND fb_created_time >= %s
          AND fb_created_time < (%s::date + INTERVAL '1 day')
          AND objective = ANY(%s)
          AND ({name_conditions})
        ORDER BY fb_created_time;
    """
    params = [ad_account_id, week_start, creation_end, all_objectives] + name_params
    return run_query(query, params=tuple(params))


def get_campaign_performance(campaign_id: int, week_start: str, week_end: str) -> dict:
    query = """
        SELECT
            SUM(p.impressions) AS impressions,
            SUM(p.clicks) AS clicks,
            SUM(p.reach) AS reach,
            SUM(p.spend) AS spend,
            SUM(p.purchase_count) AS purchase_count,
            SUM(p.purchase_value) AS purchase_value
        FROM ad_sets s
        JOIN ads a ON a.ad_set_id = s.id
        JOIN ad_performance_daily p ON p.ad_id = a.id
        WHERE s.campaign_id = %s
          AND p.as_of_date BETWEEN %s AND %s;
    """
    df = run_query(query, params=(campaign_id, week_start, week_end))
    row = df.iloc[0]
    impressions = int(row["impressions"]) if pd.notna(row["impressions"]) else 0
    clicks = int(row["clicks"]) if pd.notna(row["clicks"]) else 0
    reach = int(row["reach"]) if pd.notna(row["reach"]) else 0
    spend = float(row["spend"]) if pd.notna(row["spend"]) else 0.0
    purchase_count = int(row["purchase_count"]) if pd.notna(row["purchase_count"]) else 0
    purchase_value = float(row["purchase_value"]) if pd.notna(row["purchase_value"]) else 0.0

    return {
        "impressions": impressions,
        "clicks": clicks,
        "reach": reach,
        "spend": spend,
        "purchase_count": purchase_count,
        "purchase_value": purchase_value,
        "ctr": round(clicks / impressions * 100, 2) if impressions else None,
        "roas": round(purchase_value / spend, 2) if spend else None,
    }


def get_ads_in_campaign_performance(campaign_id: int, week_start: str, week_end: str) -> list:
    query = """
        SELECT
            a.id AS ad_id,
            a.ad_name,
            SUM(p.impressions) AS impressions,
            SUM(p.clicks) AS clicks,
            SUM(p.reach) AS reach,
            SUM(p.spend) AS spend,
            SUM(p.purchase_count) AS purchase_count,
            SUM(p.purchase_value) AS purchase_value
        FROM ad_sets s
        JOIN ads a ON a.ad_set_id = s.id
        JOIN ad_performance_daily p ON p.ad_id = a.id
        WHERE s.campaign_id = %s
          AND p.as_of_date BETWEEN %s AND %s
        GROUP BY a.id, a.ad_name
        ORDER BY a.id;
    """
    df = run_query(query, params=(campaign_id, week_start, week_end))

    ads = []
    for _, row in df.iterrows():
        impressions = int(row["impressions"]) if pd.notna(row["impressions"]) else 0
        clicks = int(row["clicks"]) if pd.notna(row["clicks"]) else 0
        reach = int(row["reach"]) if pd.notna(row["reach"]) else 0
        spend = float(row["spend"]) if pd.notna(row["spend"]) else 0.0
        purchase_count = int(row["purchase_count"]) if pd.notna(row["purchase_count"]) else 0
        purchase_value = float(row["purchase_value"]) if pd.notna(row["purchase_value"]) else 0.0
        ads.append({
            "ad_id": row["ad_id"],
            "ad_name": row["ad_name"],
            "impressions": impressions,
            "clicks": clicks,
            "reach": reach,
            "spend": spend,
            "purchase_count": purchase_count,
            "purchase_value": purchase_value,
            "ctr": round(clicks / impressions * 100, 2) if impressions else None,
            "roas": round(purchase_value / spend, 2) if spend else None,
        })
    return ads


def _summarize_group(campaign_results: list) -> dict:
    if not campaign_results:
        return {
            "has_data": False,
            "campaigns": [],
            "campaign_count": 0,
            "total_impressions": 0, "total_clicks": 0, "total_reach": 0, "total_spend": 0.0,
            "total_purchase_count": 0, "total_purchase_value": 0.0,
            "overall_ctr": None, "overall_roas": None,
            "avg_ctr_per_campaign": None, "avg_roas_per_campaign": None,
        }

    total_impressions = sum(c["impressions"] for c in campaign_results)
    total_clicks = sum(c["clicks"] for c in campaign_results)
    total_reach = sum(c["reach"] for c in campaign_results)
    total_spend = sum(c["spend"] for c in campaign_results)
    total_purchase_count = sum(c["purchase_count"] for c in campaign_results)
    total_purchase_value = sum(c["purchase_value"] for c in campaign_results)

    overall_ctr = round(total_clicks / total_impressions * 100, 2) if total_impressions else None
    overall_roas = round(total_purchase_value / total_spend, 2) if total_spend else None

    valid_ctrs = [c["ctr"] for c in campaign_results if c["ctr"] is not None]
    valid_roas = [c["roas"] for c in campaign_results if c["roas"] is not None]
    avg_ctr = round(sum(valid_ctrs) / len(valid_ctrs), 2) if valid_ctrs else None
    avg_roas = round(sum(valid_roas) / len(valid_roas), 2) if valid_roas else None

    return {
        "has_data": True,
        "campaigns": campaign_results,
        "campaign_count": len(campaign_results),
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_reach": total_reach,
        "total_spend": total_spend,
        "total_purchase_count": total_purchase_count,
        "total_purchase_value": total_purchase_value,
        "overall_ctr": overall_ctr,
        "overall_roas": overall_roas,
        "avg_ctr_per_campaign": avg_ctr,
        "avg_roas_per_campaign": avg_roas,
    }


def build_campaign_report_data(ad_account_id: int, week_start: str, week_end: str) -> dict:
    campaigns_df = get_campaigns_in_creation_window(ad_account_id, week_start)

    if campaigns_df.empty:
        return {"error": f"ad_account_id={ad_account_id}, {week_start}(월)~금 사이에 생성된 트래픽/구매전환 캠페인이 없습니다."}

    grouped = {"traffic": [], "sales": []}
    for _, c in campaigns_df.iterrows():
        campaign_type = OBJECTIVE_TO_TYPE.get(c["objective"])
        if campaign_type is None:
            continue

        perf = get_campaign_performance(c["campaign_id"], week_start, week_end)
        ads = get_ads_in_campaign_performance(c["campaign_id"], week_start, week_end)
        grouped[campaign_type].append({
            "campaign_id": c["campaign_id"],
            "campaign_name": c["campaign_name"],
            "objective": c["objective"],
            "fb_created_time": str(c["fb_created_time"]),
            **perf,
            "ads": ads,
        })

    ig_id_query = "SELECT ig_account_id FROM ad_accounts WHERE id = %s;"
    ig_df = run_query(ig_id_query, params=(ad_account_id,))
    ig_id = int(ig_df.iloc[0]["ig_account_id"]) if not ig_df.empty and pd.notna(ig_df.iloc[0]["ig_account_id"]) else None

    account_growth = (
        build_section3_comparisons(ig_id, week_start, week_end, target_segments=get_target_segments(ad_account_id))
        if ig_id else {"error": "ig_account_id를 찾을 수 없습니다."}
    )

    return {
        "traffic": _summarize_group(grouped["traffic"]),
        "sales": _summarize_group(grouped["sales"]),
        "account_growth": account_growth,
    }


def build_per_campaign_report(ad_account_id: int, week_start: str, week_end: str) -> dict:
    """
    섹션1·2를 "캠페인별로 각각" 생성합니다 (전체 합산 X).
    같은 주에 정규 주간 캠페인과 특별 캠페인이 함께 잡혀도, 섞지 않고
    캠페인명과 함께 각각 블록으로 반환해서 사람이 눈으로 구분할 수 있게 합니다.
    구매전환은 리포트에 포함하지 않습니다 (트래픽만 반영하는 기존 방침).
    섹션3(계정 성장지표)은 캠페인과 무관한 계정 전체 값이라 딱 1번만 포함됩니다.

    Returns:
        dict: {
            "traffic_campaigns": [
                {"campaign_name": ..., "campaign_id": ..., "section1": {...}, "section2": {...}},
                ...
            ],
            "account_growth": {...}  # 섹션3, 계정 전체 1개
        }
        또는 {"error": ...} (데이터 자체가 없는 경우)
    """
    data = build_campaign_report_data(ad_account_id, week_start, week_end)
    if "error" in data:
        return {"error": data["error"]}

    target_segments = get_target_segments(ad_account_id)
    traffic_campaigns_report = []

    for campaign in data["traffic"].get("campaigns", []):
        # 캠페인 1개짜리 그룹으로 다시 요약 (build_section1/2_highlights가
        # 기대하는 구조 그대로 재사용하기 위함 — 캠페인 개수만 1개로 좁힌 것)
        single_campaign_group = _summarize_group([campaign])
        synthetic_data = {"traffic": single_campaign_group}

        section1 = build_section1_highlights(synthetic_data, week_start, week_end)
        section2 = build_section2_highlights(synthetic_data, week_start, week_end, target_segments)

        traffic_campaigns_report.append({
            "campaign_id": campaign["campaign_id"],
            "campaign_name": campaign["campaign_name"],
            "section1": section1,
            "section2": section2,
        })

    return {
        "traffic_campaigns": traffic_campaigns_report,
        "account_growth": data["account_growth"],
    }


def _print_group(label: str, group: dict):
    print(f"=== {label} ===\n")
    if not group["has_data"]:
        print(f"해당 없음 - 이 기간에 {label} 캠페인이 없습니다.\n")
        return

    for c in group["campaigns"]:
        print(f"[{c['campaign_name']}] (campaign_id={c['campaign_id']}, objective={c['objective']}, 생성={c['fb_created_time']})")
        print(f"  노출: {c['impressions']:,} / 도달: {c['reach']:,} / 클릭: {c['clicks']:,} / 광고비: {c['spend']:,.0f}")
        print(f"  CTR: {c['ctr']}% / 구매: {c['purchase_count']}건 / 구매액: {c['purchase_value']:,.0f} / ROAS: {c['roas']}")
        print(f"  캠페인 내 광고 {len(c['ads'])}개:")
        for ad in c["ads"]:
            print(f"      [{ad['ad_name']}] (ad_id={ad['ad_id']})")
            print(f"        노출: {ad['impressions']:,} / 도달: {ad['reach']:,} / 클릭: {ad['clicks']:,} / 광고비: {ad['spend']:,.0f}")
            print(f"        CTR: {ad['ctr']}% / 구매: {ad['purchase_count']}건 / 구매액: {ad['purchase_value']:,.0f} / ROAS: {ad['roas']}")
        print()

    print(f"--- {label} 전체 합계 및 평균 ---")
    for k in ["campaign_count", "total_impressions", "total_clicks", "total_reach", "total_spend",
              "total_purchase_count", "total_purchase_value", "overall_ctr", "overall_roas",
              "avg_ctr_per_campaign", "avg_roas_per_campaign"]:
        print(f"{k}: {group[k]}")
    print()


WOW_FIELDS = [
    "campaign_count", "total_impressions", "total_clicks", "total_reach", "total_spend",
    "total_purchase_count", "total_purchase_value", "overall_ctr", "overall_roas",
]


def _wow(current, previous):
    if current is None or previous is None:
        return {"value": current, "delta": None, "growth_pct": None}
    delta = current - previous
    growth_pct = round(delta / previous * 100, 1) if previous else None
    return {"value": current, "delta": delta, "growth_pct": growth_pct}


def build_wow_comparison(ad_account_id: int, this_week_start: str, this_week_end: str) -> dict:
    prev_week_start = (pd.to_datetime(this_week_start) - pd.Timedelta(days=WOW_OFFSET_DAYS)).strftime("%Y-%m-%d")
    prev_week_end = (pd.to_datetime(this_week_end) - pd.Timedelta(days=WOW_OFFSET_DAYS)).strftime("%Y-%m-%d")

    this_week = build_campaign_report_data(ad_account_id, this_week_start, this_week_end)
    prev_week = build_campaign_report_data(ad_account_id, prev_week_start, prev_week_end)

    result = {
        "prev_week_range": (prev_week_start, prev_week_end),
        "prev_week_raw": prev_week,
    }

    for campaign_type in ["traffic", "sales"]:
        cur_group = this_week.get(campaign_type, {"has_data": False}) if "error" not in this_week else {"has_data": False}
        prev_group = prev_week.get(campaign_type, {"has_data": False}) if "error" not in prev_week else {"has_data": False}

        if not cur_group.get("has_data") and not prev_group.get("has_data"):
            result[campaign_type] = {"has_comparison": False, "note": "이번 주/지난 주 모두 해당 유형 캠페인 없음"}
            continue

        wow_metrics = {}
        for field in WOW_FIELDS:
            cur_val = cur_group.get(field) if cur_group.get("has_data") else (0 if field != "overall_ctr" and field != "overall_roas" else None)
            prev_val = prev_group.get(field) if prev_group.get("has_data") else (0 if field != "overall_ctr" and field != "overall_roas" else None)
            wow_metrics[field] = _wow(cur_val, prev_val)

        result[campaign_type] = {
            "has_comparison": True,
            "this_week_has_data": cur_group.get("has_data", False),
            "prev_week_has_data": prev_group.get("has_data", False),
            **wow_metrics,
        }

    return result


if __name__ == "__main__":
    result = build_per_campaign_report(AD_ACCOUNT_ID, WEEK_START, WEEK_END)

    if "error" in result:
        print(result["error"])
    else:
        for i, camp in enumerate(result["traffic_campaigns"], start=1):
            print(f"=== 트래픽 캠페인 {i} : {camp['campaign_name']} ===\n")

            s1 = camp["section1"]
            if s1 is None:
                print("(이 캠페인은 데이터가 없어 섹션1을 생성할 수 없습니다)\n")
            else:
                print("■ 이번주 평균 CTR")
                print(f"전체 평균 CTR: {s1['avg_ctr']}% (총 {s1['content_count']}개 콘텐츠 평균)")
                print("■ 주간 총 집행 요약")
                print(f"총 노출: {s1['total_impressions']:,} / 총 클릭: {s1['total_clicks']:,} / 총 도달: {s1['total_reach']:,}")
                print("■ 노출 연령·성별 TOP3")
                for idx, item in enumerate(s1["top3_by_impressions"], start=1):
                    print(f"{idx}순위: {item['age_range']}, {item['gender']}")

            s2 = camp["section2"]
            print()
            if s2["top_ctr_ad"]:
                print(f"■ 클릭율이 가장 높았던 콘텐츠 (CTR = {s2['top_ctr_ad']['ctr']}%)")
                print(s2["top_ctr_ad"]["ad_name"])
            if s2["best_cpc_ad"]:
                print(f"■ 광고비 효율이 가장 좋았던 콘텐츠 (CPC = {s2['best_cpc_ad']['cpc']}원)")
                print(s2["best_cpc_ad"]["ad_name"])

            print("\n" + "─" * 40 + "\n")

        print("=== 섹션3: 계정 성장지표 (계정 전체, 캠페인 무관) ===\n")
        growth = result["account_growth"]
        if "error" in growth:
            print(growth["error"])
        else:
            print("[팔로워]")
            print(f"  전주대비: {growth['followers']['wow']}")
            print(f"  전월대비: {growth['followers']['mom']}")
            print(f"  초기대비: {growth['followers']['baseline']}")
            print("  메인 타겟층별 팔로워 전주대비:")
            for seg in growth["followers"].get("target_segments", []):
                print(f"    {seg}")
            print("[조회수] 전주대비:", growth["views"]["wow"])
            print("[프로필방문] 전주대비:", growth["profile_views"]["wow"])
            print("[좋아요] 전주대비:", growth["likes"]["wow"])
            print("[전체상호작용]")
            print(f"  전주대비: {growth['total_interactions']['wow']}")
            print(f"  전월대비: {growth['total_interactions']['mom']}")
