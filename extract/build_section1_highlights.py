"""
extract/build_section1_highlights.py

섹션1(주간전체요약)에 필요한 데이터를 계산합니다.
- 이번주 평균 CTR (콘텐츠별 CTR의 평균)
- 주간 총 집행 요약 (총 노출/클릭/도달)
- 노출/클릭/도달 각각 기준 연령·성별 TOP3

"TOP3가 무엇인지"는 사실 판단이라 AI가 아니라 파이썬으로 직접 계산합니다.
(AI는 이 결과를 정해진 양식으로 포맷팅하는 역할만 합니다 — prompts/prompt_section1.py)

입력: extract/build_campaign_report.py의 결과 중 data["traffic"] (트래픽 그룹)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_connect import run_query

GENDER_LABEL = {"male": "남성", "female": "여성", "unknown": "성별 미상"}


def _flatten_traffic_ads(traffic_group: dict) -> list:
    """트래픽 그룹의 모든 캠페인 내 광고를 하나의 리스트로 펼칩니다."""
    ads = []
    for c in traffic_group.get("campaigns", []):
        ads.extend(c["ads"])
    return ads


def get_demo_breakdown_for_ads(ad_ids: list, week_start: str, week_end: str):
    """
    지정한 광고들(ad_ids) 전체를 합산해서, 연령·성별 조합별
    노출/클릭/도달 합계를 가져옵니다.
    """
    query = """
        SELECT age_range, gender,
               SUM(impressions) AS impressions,
               SUM(clicks) AS clicks,
               SUM(reach) AS reach
        FROM ad_performance_daily
        WHERE ad_id = ANY(%s) AND as_of_date BETWEEN %s AND %s
        GROUP BY age_range, gender;
    """
    return run_query(query, params=(ad_ids, week_start, week_end))


def _top3(demo_df, metric: str) -> list:
    """demo_df를 지정 지표(metric) 기준 내림차순 정렬해서 상위 3개를 반환합니다."""
    if demo_df.empty:
        return []
    sorted_df = demo_df.sort_values(metric, ascending=False).head(3)
    return [
        {"age_range": row["age_range"], "gender": GENDER_LABEL.get(row["gender"], row["gender"])}
        for _, row in sorted_df.iterrows()
    ]


def build_section1_highlights(data: dict, week_start: str, week_end: str) -> dict:
    """
    섹션1에 필요한 모든 하이라이트를 조립합니다.

    Args:
        data: build_campaign_report_data()의 반환값 전체
        week_start, week_end: 조회 주간

    Returns:
        dict 또는 None (트래픽 데이터가 없는 경우)
    """
    traffic_group = data["traffic"]
    if not traffic_group.get("has_data"):
        return None

    ads = _flatten_traffic_ads(traffic_group)
    content_count = len(ads)

    valid_ctrs = [a["ctr"] for a in ads if a["ctr"] is not None]
    avg_ctr = round(sum(valid_ctrs) / len(valid_ctrs), 2) if valid_ctrs else None

    ad_ids = [a["ad_id"] for a in ads]
    demo_df = get_demo_breakdown_for_ads(ad_ids, week_start, week_end)

    return {
        "avg_ctr": avg_ctr,
        "content_count": content_count,
        "total_impressions": traffic_group["total_impressions"],
        "total_clicks": traffic_group["total_clicks"],
        "total_reach": traffic_group["total_reach"],
        "top3_by_impressions": _top3(demo_df, "impressions"),
        "top3_by_clicks": _top3(demo_df, "clicks"),
        "top3_by_reach": _top3(demo_df, "reach"),
    }
