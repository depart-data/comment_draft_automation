"""
extract/build_section2_highlights.py

섹션2(콘텐츠 하이라이트)에 필요한 데이터를 계산합니다.
- CTR이 가장 높았던 콘텐츠
- 광고비 효율(CPC가 가장 낮은)이 가장 좋았던 콘텐츠
- 타겟층(연령·성별)별로 클릭이 가장 높았던 콘텐츠
- 타겟층별로 노출이 가장 높았던 콘텐츠

입력: data["traffic"] (build_campaign_report.py의 _summarize_group() 결과 —
      단일 캠페인이든 여러 캠페인 합계든 구조만 같으면 그대로 재사용 가능)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_connect import run_query

GENDER_CODE_TO_AD_PERF = {"M": "male", "F": "female", "U": "unknown"}


def _flatten_traffic_ads(traffic_group: dict) -> list:
    ads = []
    for c in traffic_group.get("campaigns", []):
        ads.extend(c["ads"])
    return ads


def get_top_ctr_ad(traffic_group: dict):
    ads = [a for a in _flatten_traffic_ads(traffic_group) if a["ctr"] is not None]
    if not ads:
        return None
    return max(ads, key=lambda a: a["ctr"])


def get_best_cpc_ad(traffic_group: dict):
    candidates = []
    for a in _flatten_traffic_ads(traffic_group):
        if a["clicks"] > 0:
            cpc = round(a["spend"] / a["clicks"], 2)
            candidates.append({**a, "cpc": cpc})
    if not candidates:
        return None
    return min(candidates, key=lambda a: a["cpc"])


def get_segment_top_ads(traffic_group: dict, age_range: str, gender: str, week_start: str, week_end: str) -> dict:
    ads = _flatten_traffic_ads(traffic_group)
    ad_ids = [a["ad_id"] for a in ads]
    ad_name_map = {a["ad_id"]: a["ad_name"] for a in ads}

    if not ad_ids:
        return {"top_click_ad": None, "top_impression_ad": None}

    ad_perf_gender = GENDER_CODE_TO_AD_PERF.get(gender, gender)

    query = """
        SELECT ad_id, SUM(impressions) AS impressions, SUM(clicks) AS clicks
        FROM ad_performance_daily
        WHERE ad_id = ANY(%s) AND age_range = %s AND gender = %s
          AND as_of_date BETWEEN %s AND %s
        GROUP BY ad_id;
    """
    df = run_query(query, params=(ad_ids, age_range, ad_perf_gender, week_start, week_end))

    if df.empty:
        return {"top_click_ad": None, "top_impression_ad": None}

    top_click_row = df.loc[df["clicks"].idxmax()]
    top_impression_row = df.loc[df["impressions"].idxmax()]

    return {
        "top_click_ad": {
            "ad_name": ad_name_map.get(top_click_row["ad_id"]),
            "clicks": int(top_click_row["clicks"]),
        },
        "top_impression_ad": {
            "ad_name": ad_name_map.get(top_impression_row["ad_id"]),
            "impressions": int(top_impression_row["impressions"]),
        },
    }


def build_section2_highlights(data: dict, week_start: str, week_end: str, target_segments: list) -> dict:
    """
    섹션2에 필요한 모든 하이라이트를 조립합니다.
    data["traffic"]에 들어온 캠페인(들)의 광고를 대상으로 계산합니다.
    """
    traffic_group = data["traffic"]

    top_ctr = get_top_ctr_ad(traffic_group)
    best_cpc = get_best_cpc_ad(traffic_group)

    segment_highlights = []
    for age_range, gender in target_segments:
        seg_result = get_segment_top_ads(traffic_group, age_range, gender, week_start, week_end)
        segment_highlights.append({
            "age_range": age_range,
            "gender": gender,
            **seg_result,
        })

    return {
        "top_ctr_ad": {"ad_name": top_ctr["ad_name"], "ctr": top_ctr["ctr"]} if top_ctr else None,
        "best_cpc_ad": {"ad_name": best_cpc["ad_name"], "cpc": best_cpc["cpc"]} if best_cpc else None,
        "segment_highlights": segment_highlights,
    }
