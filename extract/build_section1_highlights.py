"""
extract/build_section1_highlights.py

섹션1(주간전체요약)에 필요한 데이터를 계산합니다.
- 이번주 평균 CTR (총클릭/총노출 SUM/SUM 기준 — 콘텐츠별 CTR 평균 아님, Simpson's paradox 방지)
- 주간 총 집행 요약 (총 노출/클릭/도달)
- 노출/클릭/도달 각각 기준 연령·성별 TOP3

"TOP3가 무엇인지"는 사실 판단이라 AI가 아니라 파이썬으로 직접 계산합니다.

입력: data["traffic"] (build_campaign_report.py의 _summarize_group() 결과 —
      단일 캠페인이든 여러 캠페인 합계든 구조만 같으면 그대로 재사용 가능)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_connect import run_query

GENDER_LABEL = {"male": "남성", "female": "여성", "unknown": "성별 미상"}


def _flatten_traffic_ads(traffic_group: dict) -> list:
    ads = []
    for c in traffic_group.get("campaigns", []):
        ads.extend(c["ads"])
    return ads


def get_demo_breakdown_for_ads(ad_ids: list, week_start: str, week_end: str):
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
    data["traffic"]에 들어온 캠페인(들)의 광고를 대상으로 계산합니다.
    (호출부에서 캠페인 1개짜리 그룹을 넘기면 "그 캠페인만의" 섹션1이 됨)
    """
    traffic_group = data["traffic"]
    if not traffic_group.get("has_data"):
        return None

    ads = _flatten_traffic_ads(traffic_group)
    content_count = len(ads)

    total_impressions = traffic_group["total_impressions"]
    total_clicks = traffic_group["total_clicks"]
    # SUM/SUM으로 계산 (콘텐츠별 CTR을 평균 내면 Simpson's paradox로 왜곡될 수 있어
    # 지양 — reference_notes.md 참고. 2026-09-08 avg_ctr에서 overall_ctr로 교체)
    overall_ctr = round(total_clicks / total_impressions * 100, 2) if total_impressions else None

    ad_ids = [a["ad_id"] for a in ads]
    demo_df = get_demo_breakdown_for_ads(ad_ids, week_start, week_end)

    return {
        "overall_ctr": overall_ctr,
        "content_count": content_count,
        "total_impressions": traffic_group["total_impressions"],
        "total_clicks": traffic_group["total_clicks"],
        "total_reach": traffic_group["total_reach"],
        "top3_by_impressions": _top3(demo_df, "impressions"),
        "top3_by_clicks": _top3(demo_df, "clicks"),
        "top3_by_reach": _top3(demo_df, "reach"),
    }
