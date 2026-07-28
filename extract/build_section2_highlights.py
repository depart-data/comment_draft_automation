"""
extract/build_section2_highlights.py

섹션2(콘텐츠 하이라이트)에 필요한 데이터를 계산합니다.
- CTR이 가장 높았던 콘텐츠
- 광고비 효율(CPC가 가장 낮은)이 가장 좋았던 콘텐츠
- 타겟층(연령·성별)별로 클릭이 가장 높았던 콘텐츠
- 타겟층별로 노출이 가장 높았던 콘텐츠

"1등이 무엇인지"는 사실 판단이라 AI가 아니라 파이썬으로 직접 계산합니다.
(AI는 이 결과를 정해진 양식으로 포맷팅하는 역할만 합니다 — prompts/prompt_section2.py)

입력: extract/build_campaign_report.py의 결과 중 data["traffic"] (트래픽 그룹)
      config.accounts.get_target_segments(ad_account_id)로 타겟층 목록 조회
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_connect import run_query

# config.accounts의 타겟 세그먼트는 ig_insights_demographics 기준 약자(M/F/U)를 쓰지만,
# ad_performance_daily는 전체 단어(male/female/unknown)를 씁니다. 이 차이 때문에
# 쿼리가 매칭되지 않는 문제가 있어 여기서 변환합니다.
GENDER_CODE_TO_AD_PERF = {"M": "male", "F": "female", "U": "unknown"}


def _flatten_traffic_ads(traffic_group: dict) -> list:
    """트래픽 그룹의 모든 캠페인 내 광고를 하나의 리스트로 펼칩니다."""
    ads = []
    for c in traffic_group.get("campaigns", []):
        ads.extend(c["ads"])
    return ads


def get_top_ctr_ad(traffic_group: dict):
    """CTR이 가장 높았던 콘텐츠를 찾습니다."""
    ads = [a for a in _flatten_traffic_ads(traffic_group) if a["ctr"] is not None]
    if not ads:
        return None
    return max(ads, key=lambda a: a["ctr"])


def get_best_cpc_ad(traffic_group: dict):
    """광고비 효율(CPC가 가장 낮은)이 가장 좋았던 콘텐츠를 찾습니다."""
    candidates = []
    for a in _flatten_traffic_ads(traffic_group):
        if a["clicks"] > 0:
            cpc = round(a["spend"] / a["clicks"], 2)
            candidates.append({**a, "cpc": cpc})
    if not candidates:
        return None
    return min(candidates, key=lambda a: a["cpc"])


def get_segment_top_ads(traffic_group: dict, age_range: str, gender: str, week_start: str, week_end: str) -> dict:
    """
    특정 타겟층(연령·성별)에서 클릭이 가장 높았던 콘텐츠와,
    노출이 가장 높았던 콘텐츠를 각각 찾습니다.
    """
    ads = _flatten_traffic_ads(traffic_group)
    ad_ids = [a["ad_id"] for a in ads]
    ad_name_map = {a["ad_id"]: a["ad_name"] for a in ads}

    if not ad_ids:
        return {"top_click_ad": None, "top_impression_ad": None}

    # ad_performance_daily는 gender를 전체 단어(male/female/unknown)로 저장하므로 변환
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

    Args:
        data: build_campaign_report_data()의 반환값 전체
        week_start, week_end: 조회 주간
        target_segments: config.accounts.get_target_segments(ad_account_id) 결과,
                          [("18-24", "F"), ("25-34", "M"), ...] 형태

    Returns:
        dict: {
            "top_ctr_ad": {"ad_name": ..., "ctr": ...} 또는 None,
            "best_cpc_ad": {"ad_name": ..., "cpc": ...} 또는 None,
            "segment_highlights": [
                {"age_range": ..., "gender": ..., "top_click_ad": {...}, "top_impression_ad": {...}},
                ...
            ]
        }
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