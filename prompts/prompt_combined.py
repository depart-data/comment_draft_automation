"""
prompts/prompt_combined.py

섹션1·2·3을 하나의 프롬프트로 합쳐서, Gemini 호출을 계정당 3회 → 1회로
줄입니다. (하루 요청 한도 20회 확인 후, 처리 가능한 계정 수를 늘리기 위한 개선)

구조화 출력(JSON 스키마 강제)을 사용해서, 응답을 {"section1": "...", "section2": "...",
"section3": "..."} 형태로 안전하게 파싱합니다.

데이터가 없는 섹션(예: 트래픽 캠페인이 없는 주)은 애초에 프롬프트에 포함하지
않고, AI 호출 없이 정적 메시지로 처리합니다 — 없는 데이터를 지어내지 않도록
방지하는 장치입니다.

트레이드오프: 섹션별로 나눠 호출하던 이전 방식과 달리, 실패 시 "어느
섹션에서 실패했는지"는 더 이상 구분할 수 없습니다 (전체 실패로만 기록됩니다).
실제 실패 원인 대부분이 API 한도·네트워크 문제라 특정 섹션 문제가 아니라는
점에서, 이 정보 손실은 감수 가능하다고 판단했습니다.
"""

import json

# 포함되는 섹션 종류에 따라 required 목록이 달라지므로, 스키마는 함수로 생성
def build_response_schema(included_sections: list) -> dict:
    """
    포함된 섹션 이름 목록(예: ["section1", "section2"])에 대해서만
    JSON 스키마의 필수 필드로 지정합니다.
    """
    return {
        "type": "object",
        "properties": {name: {"type": "string"} for name in included_sections},
        "required": included_sections,
    }


# 섹션별 형식 템플릿 (각 prompts/prompt_sectionN.py의 "형식" 블록과 동일)
_SECTION1_FORMAT = """[섹션1 형식 — section1 키에 아래 형식 그대로 작성]

■ 이번주 평균 CTR
전체 평균 CTR: [avg_ctr]% (총 [content_count]개 콘텐츠 평균)

■ 주간 총 집행 요약
총 노출: [total_impressions]
총 클릭: [total_clicks]
총 도달: [total_reach]

■ 노출 연령·성별 TOP3
1순위: [top3_by_impressions[0].age_range], [top3_by_impressions[0].gender]
2순위: [top3_by_impressions[1].age_range], [top3_by_impressions[1].gender]
3순위: [top3_by_impressions[2].age_range], [top3_by_impressions[2].gender]

■ 클릭 연령·성별 TOP3
1순위: [top3_by_clicks[0].age_range], [top3_by_clicks[0].gender]
2순위: [top3_by_clicks[1].age_range], [top3_by_clicks[1].gender]
3순위: [top3_by_clicks[2].age_range], [top3_by_clicks[2].gender]

■ 도달 연령·성별 TOP3
1순위: [top3_by_reach[0].age_range], [top3_by_reach[0].gender]
2순위: [top3_by_reach[1].age_range], [top3_by_reach[1].gender]
3순위: [top3_by_reach[2].age_range], [top3_by_reach[2].gender]"""

_SECTION2_FORMAT = """[섹션2 형식 — section2 키에 아래 형식 그대로 작성]

■ 클릭율이 가장 높았던 콘텐츠 (CTR = [top_ctr_ad.ctr]%)
[top_ctr_ad.ad_name]

■ 광고비 효율이 가장 좋았던 콘텐츠 (CPC = [best_cpc_ad.cpc]원)
[best_cpc_ad.ad_name]

■ [age_range]세 [성별 라벨](타겟층)에서 가장 클릭이 높았던 콘텐츠
[top_click_ad.ad_name]

■ [age_range]세 [성별 라벨](타겟층)에서 가장 노출이 높았던 콘텐츠
[top_impression_ad.ad_name]

(segment_highlights 배열의 항목 수만큼, 위 타겟층 두 항목씩 반복. gender는 M=남성,F=여성,U=성별 미상)"""

_SECTION3_FORMAT = """[섹션3 형식 — section3 키에 아래 형식 그대로 작성]

**1. 팔로워** (초기 대비 / 전주 대비)
* 총 팔로워 수: [followers.wow.value]명
* 증감: ([followers.baseline.delta]명 증가/감소 / [followers.wow.delta]명 증가/감소)
* 성장률: ([followers.baseline.growth_pct]% 증가/감소 / [followers.wow.growth_pct]% 증가/감소)

**1-1. 타겟층 팔로워** (전주 대비)
* [연령] [성별] : [값]명 ([증감]명 증가/감소, [성장률]%)
(followers.target_segments 배열 항목 수만큼 반복, 비어있으면 이 섹션 생략)

**2. 조회수** (전주 대비)
* 총 조회수: [views.wow.value]회
* 증감: [views.wow.delta]회 증가/감소

**3. 프로필 방문** (전주 대비)
* 총 프로필 방문: [profile_views.wow.value]회
* 증감: [profile_views.wow.delta]회 증가/감소

**4. 좋아요** (전주 대비)
* 총 좋아요: [likes.wow.value]회
* 증감: [likes.wow.delta]회 증가/감소

**5. 전체 상호작용** (전주 대비 / 전월 대비)
* 총 전체 상호작용: [total_interactions.wow.value]회
* 증감: ([total_interactions.wow.delta]회 증가/감소 / [total_interactions.mom.delta]회 증가/감소)"""

_FORMATS = {
    "section1": _SECTION1_FORMAT,
    "section2": _SECTION2_FORMAT,
    "section3": _SECTION3_FORMAT,
}


def build_prompt_combined(section_data: dict) -> str:
    """
    데이터가 있는 섹션들만 모아서 하나의 프롬프트로 합칩니다.

    Args:
        section_data: {"section1": highlights1_dict, "section2": highlights2_dict,
                        "section3": account_growth_dict} 중 실제 데이터가 있는
                        섹션들만 포함된 dict (없는 섹션은 애초에 키 자체가 없음)

    Returns:
        str: 완성된 프롬프트 텍스트
    """
    format_blocks = "\n\n".join(_FORMATS[name] for name in section_data.keys())
    data_json = json.dumps(section_data, ensure_ascii=False, indent=2, default=str)
    included_names = ", ".join(section_data.keys())

    return f"""[필수 규칙] 모든 숫자는 예외 없이 천 단위마다 콤마(,)를 넣어서 출력하세요.
데이터에 1410, 98397처럼 콤마 없는 숫자가 있어도, 반드시 1,410 / 98,397 형태로
바꿔서 출력해야 합니다.

아래는 인스타그램 광고 계정의 이번 주 성과 데이터입니다. 이 데이터를 바탕으로
클라이언트에게 보낼 주간 리포트를 작성해 주세요. 이번 요청에는 {included_names}만
포함되어 있습니다 (해당 섹션만 작성하세요).

기본 조건
- 수치·순위·광고명의 값 자체는 아래 제공된 데이터를 그대로 사용합니다.
  재계산하거나 순서를 바꾸지 마세요. (콤마 표기는 값 변경이 아니라 표기 방식이므로
  위 필수 규칙에 따라 반드시 적용합니다.)
- 인사말, 안내 문구, 마무리 인사 없이, 아래 형식의 본문 내용만 출력합니다.
- 증감이 양수면 "증가", 음수면 "감소"라는 단어를 함께 표기합니다.
- 각 섹션의 볼드 헤더(**)와 글머리 기호(*, ■) 구조를 그대로 유지합니다.
- 반드시 JSON 형식으로만 응답하세요. {included_names} 키에 각각 아래 형식대로
  작성한 텍스트를 문자열 값으로 담으세요.

{format_blocks}

데이터:
{data_json}
"""
