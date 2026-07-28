"""
build_section1_text.py

섹션1(주간전체요약) 보고서를 API 호출 없이, 순수 파이썬 텍스트 조합으로 생성합니다.
db_extract_daily.py에서 이미 뽑아둔 객체(요일별 원재료, 성별x연령대)만 사용하고,
추가 DB 조회나 LLM 호출 없이 계산된 값을 정해진 양식 문자열에 그대로 끼워넣습니다.

사전 준비:
    db_connect.py, db_extract_daily.py 와 같은 폴더에 있어야 합니다.
"""

from db_extract_daily import (
    build_daily_components,
    build_demo_components,
    WEEKDAY_NAMES,
    DEFAULT_IG_ID,
    DEFAULT_START_DATE,
    DEFAULT_END_DATE,
    DEFAULT_NAME_PREFIX,
)


# ------------------------------------------------------------
# 1. 저장된 객체만으로 섹션1 데이터 집계 (추가 DB 조회 없음)
# ------------------------------------------------------------

def aggregate_section1_data(
    ig_id: int = DEFAULT_IG_ID,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    name_prefix: str = DEFAULT_NAME_PREFIX,
) -> dict:
    """
    build_daily_components()와 build_demo_components() 결과만 가지고
    섹션1(주간전체요약)에 필요한 값을 계산합니다. 새로운 DB 쿼리는 없습니다.
    """
    daily_components = build_daily_components(ig_id, start_date, end_date, name_prefix)
    demo_components = build_demo_components(ig_id, start_date, end_date, name_prefix)

    if not daily_components:
        return {"error": f"ig_id={ig_id}, 기간={start_date}~{end_date}에 해당하는 데이터가 없습니다."}

    # 광고별 주간 총계 (요일별 원재료를 SUM)
    ad_totals = []
    for record in daily_components:
        impressions = sum(record[f"impressions_{w}"] for w in WEEKDAY_NAMES)
        clicks = sum(record[f"clicks_{w}"] for w in WEEKDAY_NAMES)
        reach = sum(record[f"reach_{w}"] for w in WEEKDAY_NAMES)
        spend = sum(record[f"spend_{w}"] for w in WEEKDAY_NAMES)
        ctr = round(clicks / impressions * 100, 2) if impressions else 0.0
        cpc = round(spend / clicks, 2) if clicks else None
        ad_totals.append({
            "ad_id": record["ad_id"],
            "ad_name": record["ad_name"],
            "impressions": impressions,
            "clicks": clicks,
            "reach": reach,
            "spend": spend,
            "ctr": ctr,
            "cpc": cpc,
        })

    # 평균 CTR (광고별 CTR의 평균 — 총합 재계산 아님)
    avg_ctr = round(sum(a["ctr"] for a in ad_totals) / len(ad_totals), 2)

    # 총계
    total_impressions = sum(a["impressions"] for a in ad_totals)
    total_clicks = sum(a["clicks"] for a in ad_totals)
    total_reach = sum(a["reach"] for a in ad_totals)

    # CTR 높은 순 정렬 (CPC 나열도 동일한 순서를 그대로 사용)
    sorted_ads = sorted(ad_totals, key=lambda x: x["ctr"], reverse=True)
    ctr_ranking = [a["ad_name"] for a in sorted_ads]
    cpc_ranking = [{"ad_name": a["ad_name"], "cpc": a["cpc"]} for a in sorted_ads]

    # 반응 연령·성별 TOP3 (모든 광고의 demo_breakdown을 합산 후 노출 기준 상위 3개)
    gender_kr = {"male": "남성", "female": "여성", "unknown": "성별 미상"}
    demo_totals = {}
    for record in demo_components:
        for demo in record["demo_breakdown"]:
            key = (demo["gender"], demo["age_range"])
            demo_totals[key] = demo_totals.get(key, 0) + demo["impressions"]
    top3_sorted = sorted(demo_totals.items(), key=lambda x: x[1], reverse=True)[:3]
    top3_demo_overall = [f"{gender_kr.get(g, g)} / {a}세" for (g, a), _ in top3_sorted]

    return {
        "content_count": len(ad_totals),
        "avg_ctr": avg_ctr,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_reach": total_reach,
        "ctr_ranking": ctr_ranking,
        "cpc_ranking": cpc_ranking,
        "top3_demo_overall": top3_demo_overall,
    }


# ------------------------------------------------------------
# 2. 텍스트 양식에 그대로 끼워넣기 (API 호출 없음)
# ------------------------------------------------------------

def format_section1_text(data: dict) -> str:
    """
    aggregate_section1_data()의 결과를 원본 리포트와 동일한 양식 문자열에
    그대로 끼워넣습니다. LLM 호출 없이 순수 텍스트 조합입니다.
    """
    if "error" in data:
        return f"⚠️ {data['error']}"

    lines = []
    lines.append("섹션1. 주간전체요약")

    lines.append("■ 이번주 평균 CTR")
    lines.append(f"전체 평균 CTR: {data['avg_ctr']}% (총 {data['content_count']}개 콘텐츠 평균)")

    lines.append("■ 주간 총 집행 요약")
    lines.append(f"총 노출: {data['total_impressions']:,}")
    lines.append(f"총 클릭: {data['total_clicks']:,}")
    lines.append(f"총 도달: {data['total_reach']:,}")

    lines.append("■ 콘텐츠별 클릭당 비용 (CPC)")
    for item in data["cpc_ranking"]:
        cpc_str = f"${item['cpc']:.2f}" if item["cpc"] is not None else "N/A"
        lines.append(f"{item['ad_name']} {cpc_str}")

    lines.append("■ 반응 연령·성별 TOP3")
    for i, demo in enumerate(data["top3_demo_overall"], start=1):
        lines.append(f"{i}위 {demo}")

    lines.append("■ CTR 높은 순 콘텐츠 나열")
    for ad_name in data["ctr_ranking"]:
        lines.append(ad_name)

    return "\n".join(lines)


def build_section1_report(
    ig_id: int = DEFAULT_IG_ID,
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    name_prefix: str = DEFAULT_NAME_PREFIX,
) -> str:
    """섹션1 데이터를 집계하고 바로 텍스트로 조합해서 반환합니다 (API 호출 없음)."""
    data = aggregate_section1_data(ig_id, start_date, end_date, name_prefix)
    return format_section1_text(data)


if __name__ == "__main__":
    print(build_section1_report())