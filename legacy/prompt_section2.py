"""
prompts/prompt_section2.py

섹션2(콘텐츠 하이라이트) 프롬프트를 조립합니다.

"1등이 무엇인지" 계산은 이미 extract/build_section2_highlights.py에서
파이썬으로 정확히 끝낸 상태입니다. 여기서 AI에게 맡기는 역할은 오직
"이미 정해진 사실을 지정된 양식으로 포맷팅하는 것"뿐입니다 (재계산 없음).

입력 데이터 출처: extract/build_section2_highlights.py의 build_section2_highlights() 반환값
"""

import json

GENDER_LABEL = {"M": "남성", "F": "여성", "U": "성별 미상"}


def build_prompt_section2(highlights: dict) -> str:
    """
    섹션2 하이라이트 데이터(dict)를 받아 Gemini에 보낼 프롬프트 문자열을 조립합니다.

    Args:
        highlights: build_section2_highlights()의 반환값

    Returns:
        str: 완성된 프롬프트 텍스트
    """
    data_json = json.dumps(highlights, ensure_ascii=False, indent=2, default=str)

    return f"""아래는 이번 주 인스타그램 광고 콘텐츠 중 특정 항목에서 1위를 기록한
콘텐츠 정보입니다. 이 데이터를 바탕으로 클라이언트에게 보낼 "콘텐츠 하이라이트"
섹션을, 아래 지정된 형식 그대로 작성해 주세요.

기본 조건
- 광고명·순위의 값 자체는 아래 제공된 데이터를 그대로 사용합니다. 순위를 다시
  계산하거나 다른 콘텐츠로 바꾸지 마세요. (1위는 이미 정해진 사실입니다. 단,
  아래 콤마 표기 규칙은 값을 바꾸는 것이 아니라 "표기 방식"이므로 반드시 적용하세요.)
- 인사말, 안내 문구, 마무리 인사 없이, 아래 형식의 본문 내용만 출력합니다.
- 숫자는 반드시 천 단위마다 콤마(,)로 구분해서 표기합니다. 데이터의 숫자가
  콤마 없이 주어져도, 출력할 때는 콤마를 넣어서 표기하세요.
- 데이터의 gender 값은 M=남성, F=여성, U=성별 미상으로 표기합니다.
- 아래 형식의 "■" 기호 구조를 그대로 유지합니다.
- top_ctr_ad 또는 best_cpc_ad가 null이면 해당 항목은 생략합니다.
- segment_highlights 배열의 항목 수만큼, 타겟층 관련 두 항목(클릭 1위/노출 1위)씩
  반복해서 작성하세요. 배열이 비어있으면 타겟층 관련 항목 전체를 생략합니다.
  해당 세그먼트의 top_click_ad 또는 top_impression_ad가 null이면 그 항목만 생략합니다.

형식 (아래 구조를 그대로 따르되, 실제 값은 데이터에서 가져와 채워 넣으세요):

■ 클릭율이 가장 높았던 콘텐츠 (CTR = [top_ctr_ad.ctr]%)
[top_ctr_ad.ad_name]

■ 광고비 효율이 가장 좋았던 콘텐츠 (CPC = [best_cpc_ad.cpc]원)
[best_cpc_ad.ad_name]

■ [age_range]세 [성별 라벨](타겟층)에서 가장 클릭이 높았던 콘텐츠
[top_click_ad.ad_name]

■ [age_range]세 [성별 라벨](타겟층)에서 가장 노출이 높았던 콘텐츠
[top_impression_ad.ad_name]

데이터:
{data_json}
"""
