"""
extract/build_campaign_report.py

캠페인·광고 단위 트래픽/구매전환 성과 + WoW 비교 + 계정 성장지표(섹션3)를
전부 통합해서 뽑아내는 메인 오케스트레이터입니다.

로직:
1) 대상: ad_account_id 직접 지정 (나중에 자동화 단계에서는 config.accounts의
   계정 목록을 순회)
2) 캠페인 식별: campaigns.fb_created_time이 지정 주간의 월~금 사이인 캠페인만
   (캠페인명에 config.settings.CAMPAIGN_NAME_KEYWORDS 포함된 대행 캠페인만 대상)
3) 성과 집계: 캠페인 시작 요일과 무관하게, 그 주 일요일까지 전체 기간으로 고정
4) 캠페인별 노출/도달/클릭/광고비/CTR/구매/ROAS를 원재료+파생지표로 수집,
   트래픽/구매전환을 분리해서 각각 전체 합계 및 평균 계산
   (한쪽 유형이 아예 없는 브랜드도 있으므로, 없으면 "해당 없음"으로 명확히 구분)
5) 캠페인 유형(트래픽/구매전환)별 WoW 비교
6) 계정 성장지표(섹션3): 팔로워(초기대비/전주대비/전월대비/메인타겟층),
   조회수·프로필방문·좋아요(전주대비), 전체상호작용(전주대비/전월대비)

※ 이 단계에서는 DB 적재 없이 결과만 출력합니다 (초안 테이블은 추후 별도 작업).

사전 준비:
    extract/db_connect.py, extract/build_section3_comparisons.py,
    config/settings.py, config/accounts.py 가 있는 프로젝트 구조여야 합니다.
"""

import os
import sys
import pandas as pd

# 프로젝트 루트(extract/의 상위 폴더)를 sys.path에 추가해 config 패키지를 찾을 수 있게 함
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_connect import run_query
from build_section3_comparisons import build_section3_comparisons
from config.settings import OBJECTIVE_MAP, CAMPAIGN_NAME_KEYWORDS, CREATION_WINDOW_DAYS, WOW_OFFSET_DAYS
from config.accounts import get_target_segments, is_name_filter_exempt


# ══════════════════════════════════════════════════════════════
#  ⚙️  테스트 설정
# ══════════════════════════════════════════════════════════════
AD_ACCOUNT_ID = 14
WEEK_START = "2026-07-06"   # 월요일 — 캠페인 식별 시작일 & 성과 집계 시작일
WEEK_END = "2026-07-12"     # 일요일 — 성과 집계 종료일 (캠페인 시작일 무관하게 고정)
# 캠페인 식별 종료일은 config.settings.CREATION_WINDOW_DAYS(기본 4일 -> 금요일)로 자동 계산됨
# ══════════════════════════════════════════════════════════════

# objective 값 -> "traffic"/"sales" 역매핑 (트래픽/구매전환 외 목적은 리포트 범위 밖)
OBJECTIVE_TO_TYPE = {obj: t for t, objs in OBJECTIVE_MAP.items() for obj in objs}


# ------------------------------------------------------------
# 1. 캠페인 식별 (월~금 생성된 캠페인만, 트래픽/구매전환 objective만)
# ------------------------------------------------------------

def get_campaigns_in_creation_window(ad_account_id: int, week_start: str) -> pd.DataFrame:
    """
    지정 주간의 월요일~금요일 사이에 생성된 캠페인 중,
    트래픽 또는 구매전환 목적이면서 캠페인명에 config.settings.CAMPAIGN_NAME_KEYWORDS
    중 하나라도 포함된 캠페인만 식별합니다.
    (주말엔 보통 캠페인을 새로 만들지 않는다는 전제)
    (개별 브랜드사가 자체적으로 별도 캠페인을 돌릴 수 있어, 대행 캠페인만 골라내기 위한 필터)

    ※ config.accounts.NO_NAME_FILTER_ACCOUNTS에 등록된 계정(디파트 자체 운영
      계정)은 캠페인명에 depart/디파트가 안 붙으므로, 이름 조건 없이 전부
      조회합니다 (2026-07-22 확정).
    """
    creation_end = (pd.to_datetime(week_start) + pd.Timedelta(days=CREATION_WINDOW_DAYS)).strftime("%Y-%m-%d")
    all_objectives = [obj for objs in OBJECTIVE_MAP.values() for obj in objs]

    if is_name_filter_exempt(ad_account_id):
        # 이름 필터 없이 objective/기간 조건만 적용
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

    # 캠페인명 키워드 필터를 동적으로 구성 (OR 조건)
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


# ------------------------------------------------------------
# 2. 캠페인별 성과 집계 (일요일까지 고정 기간)
# ------------------------------------------------------------

def get_campaign_performance(campaign_id: int, week_start: str, week_end: str) -> dict:
    """
    특정 캠페인에 속한 모든 광고(ad_sets -> ads)의 성과를
    week_start~week_end 기간으로 SUM해서 원재료를 가져옵니다.
    """
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
    """
    특정 캠페인에 속한 광고 각각에 대해, 캠페인 레벨과 동일한 지표
    (노출/도달/클릭/광고비/CTR/구매/ROAS)를 개별적으로 계산합니다.
    """
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


# ------------------------------------------------------------
# 3. 전체 조립: 유형(트래픽/구매전환)별로 분리해서 집계 + 계정 성장지표
# ------------------------------------------------------------

def _summarize_group(campaign_results: list) -> dict:
    """
    같은 유형(트래픽 또는 구매전환) 캠페인 리스트를 받아 합계/평균을 계산합니다.
    캠페인이 하나도 없으면 has_data=False로 표시해서, 이후 리포트 작성 시
    "해당 없음"으로 명확히 구분할 수 있게 합니다.
    """
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

    # 캠페인을 유형(traffic/sales)별로 분리해서 수집
    grouped = {"traffic": [], "sales": []}
    for _, c in campaigns_df.iterrows():
        campaign_type = OBJECTIVE_TO_TYPE.get(c["objective"])
        if campaign_type is None:
            continue  # 트래픽/구매전환 외 objective는 리포트 범위 밖 (get_campaigns_in_creation_window에서 이미 필터링됨)

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

    # ig_account_id 조회 (계정 성장지표용)
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


def _print_group(label: str, group: dict):
    print(f"=== {label} ===\n")
    if not group["has_data"]:
        print(f"⚠️ 해당 없음 — 이 기간에 {label} 캠페인이 없습니다.\n")
        return

    for c in group["campaigns"]:
        print(f"[{c['campaign_name']}] (campaign_id={c['campaign_id']}, objective={c['objective']}, 생성={c['fb_created_time']})")
        print(f"  노출: {c['impressions']:,} / 도달: {c['reach']:,} / 클릭: {c['clicks']:,} / 광고비: {c['spend']:,.0f}")
        print(f"  CTR: {c['ctr']}% / 구매: {c['purchase_count']}건 / 구매액: {c['purchase_value']:,.0f} / ROAS: {c['roas']}")
        print(f"  └─ 캠페인 내 광고 {len(c['ads'])}개:")
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


# ------------------------------------------------------------
# 4. WoW 비교 (트래픽끼리, 구매전환끼리만 비교)
# ------------------------------------------------------------

WOW_FIELDS = [
    "campaign_count", "total_impressions", "total_clicks", "total_reach", "total_spend",
    "total_purchase_count", "total_purchase_value", "overall_ctr", "overall_roas",
]


def _wow(current, previous):
    """이번 주 값(current)과 지난 주 값(previous)을 비교해 증감·성장률을 계산합니다."""
    if current is None or previous is None:
        return {"value": current, "delta": None, "growth_pct": None}
    delta = current - previous
    growth_pct = round(delta / previous * 100, 1) if previous else None
    return {"value": current, "delta": delta, "growth_pct": growth_pct}


def build_wow_comparison(ad_account_id: int, this_week_start: str, this_week_end: str) -> dict:
    """
    지정한 이번 주(this_week_start~this_week_end)와 정확히 WOW_OFFSET_DAYS(기본 7)일
    전인 지난 주를 같은 로직(캠페인명 키워드 필터 포함)으로 각각 집계한 뒤,
    트래픽은 트래픽끼리, 구매전환은 구매전환끼리만 비교합니다.
    """
    prev_week_start = (pd.to_datetime(this_week_start) - pd.Timedelta(days=WOW_OFFSET_DAYS)).strftime("%Y-%m-%d")
    prev_week_end = (pd.to_datetime(this_week_end) - pd.Timedelta(days=WOW_OFFSET_DAYS)).strftime("%Y-%m-%d")

    this_week = build_campaign_report_data(ad_account_id, this_week_start, this_week_end)
    prev_week = build_campaign_report_data(ad_account_id, prev_week_start, prev_week_end)

    result = {
        "prev_week_range": (prev_week_start, prev_week_end),
        "prev_week_raw": prev_week,  # 검증용 — 지난 주 원본(캠페인·광고 상세 포함) 그대로 보존
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
    result = build_campaign_report_data(AD_ACCOUNT_ID, WEEK_START, WEEK_END)

    if "error" in result:
        print(f"⚠️ {result['error']}")
    else:
        _print_group("트래픽", result["traffic"])
        _print_group("구매전환", result["sales"])

        print("=== 계정 성장지표 (섹션3) ===")
        growth = result["account_growth"]
        if "error" in growth:
            print(f"⚠️ {growth['error']}")
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

    print("\n" + "=" * 60)
    print(f"=== WoW 비교 (이번 주 {WEEK_START}~{WEEK_END} vs 지난 주) ===\n")
    wow = build_wow_comparison(AD_ACCOUNT_ID, WEEK_START, WEEK_END)
    print(f"지난 주 범위: {wow['prev_week_range'][0]} ~ {wow['prev_week_range'][1]}\n")
    for campaign_type, label in [("traffic", "트래픽"), ("sales", "구매전환")]:
        print(f"--- {label} WoW ---")
        group = wow[campaign_type]
        if not group["has_comparison"]:
            print(f"⚠️ {group['note']}\n")
            continue
        print(f"(이번 주 데이터 존재: {group['this_week_has_data']} / 지난 주 데이터 존재: {group['prev_week_has_data']})")
        for field in WOW_FIELDS:
            m = group[field]
            print(f"{field}: 이번주={m['value']} / 증감={m['delta']} / 성장률={m['growth_pct']}%")
        print()

    print("\n" + "=" * 60)
    print(f"=== [검증용] 지난 주 원본 상세 ({wow['prev_week_range'][0]}~{wow['prev_week_range'][1]}) ===\n")
    prev_raw = wow["prev_week_raw"]
    if "error" in prev_raw:
        print(f"⚠️ {prev_raw['error']}")
    else:
        _print_group("트래픽 (지난 주)", prev_raw["traffic"])
        _print_group("구매전환 (지난 주)", prev_raw["sales"])
        print()
