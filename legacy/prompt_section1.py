"""
prompts/prompt_section1.py

섹션1(주간전체요약) 프롬프트를 조립합니다.

TOP3 순위 계산은 이미 extract/build_section1_highlights.py에서 파이썬으로
정확히 끝낸 상태입니다. 여기서 AI에게 맡기는 역할은 오직 "이미 정해진 사실을
지정된 양식으로 포맷팅하는 것"뿐입니다 (재계산 없음).

입력 데이터 출처: extract/build_section1_highlights.py의 build_section1_highlights() 반환값
"""

import json


def build_prompt_section1(data: dict) -> str:
    """
    섹션1 하이라이트 데이터(dict)를 받아 Gemini에 보낼 프롬프트 문자열을 조립합니다.

    Args:
        data: build_section1_highlights()의 반환값

    Returns:
        str: 완성된 프롬프트 텍스트
    """
    data_json = json.dumps(data, ensure_ascii=False, indent=2, default=str)

    return f"""아래는 이번 주 인스타그램 광고(트래픽 캠페인)의 전체 집행 데이터입니다.
이 데이터를 바탕으로 클라이언트에게 보낼 "주간전체요약" 섹션을, 아래 지정된
형식 그대로 작성해 주세요.

기본 조건
- 수치·순위의 값 자체는 아래 제공된 데이터를 그대로 사용합니다. 재계산하거나
  순서를 바꾸지 마세요. (TOP3는 이미 정해진 순위입니다. 단, 아래 콤마 표기
  규칙은 값을 바꾸는 것이 아니라 "표기 방식"이므로 반드시 적용하세요.)
- 인사말, 안내 문구, 마무리 인사 없이, 아래 형식의 본문 내용만 출력합니다.
- 숫자는 반드시 천 단위마다 콤마(,)로 구분해서 표기합니다. 데이터의 숫자가
  콤마 없이 주어져도, 출력할 때는 콤마를 넣어서 표기하세요.
  (예: 26035 → 26,035 / 877 → 877 / 23303 → 23,303)
- 아래 형식의 "■" 기호 구조를 그대로 유지합니다.
- top3_by_impressions/top3_by_clicks/top3_by_reach 배열은 항상 배열 순서
  그대로(이미 순위대로 정렬되어 있음) 1순위, 2순위, 3순위로 표기하세요.
  배열 길이가 3보다 적으면 있는 만큼만 표기하세요.

형식 (아래 구조를 그대로 따르되, 실제 값은 데이터에서 가져와 채워 넣으세요):

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
3순위: [top3_by_reach[2].age_range], [top3_by_reach[2].gender]

데이터:
{data_json}
"""
