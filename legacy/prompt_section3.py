"""
prompts/prompt_section3.py

섹션3(계정 성장지표) 프롬프트를 조립합니다.

토큰 소모를 줄이고 검증도 쉽게 하기 위해, account_growth 데이터만
프롬프트에 담습니다. 모델이 숫자를 재계산하지 않고, 있는 값을 그대로
활용해 정해진 형식(마크다운 볼드 헤더 + * 리스트)에 채워 넣도록 지시합니다.

입력 데이터 출처: extract/build_campaign_report.py 결과의 "account_growth" 키
    (extract/build_section3_comparisons.py의 build_section3_comparisons() 반환값)
"""

import json


def build_prompt_section3(data: dict) -> str:
    """
    섹션3 데이터(dict)를 받아 Gemini에 보낼 프롬프트 문자열을 조립합니다.

    Args:
        data: build_campaign_report_data()의 반환값 전체(dict).
              내부의 data["account_growth"]만 사용합니다.

    Returns:
        str: 완성된 프롬프트 텍스트
    """
    growth = data["account_growth"]
    data_json = json.dumps(growth, ensure_ascii=False, indent=2, default=str)

    return f"""[필수 규칙] 모든 숫자는 예외 없이 천 단위마다 콤마(,)를 넣어서 출력하세요.
데이터에 1410, 98397처럼 콤마 없는 숫자가 있어도, 반드시 1,410 / 98,397 형태로
바꿔서 출력해야 합니다. 콤마 없이 숫자를 쓰는 것은 이 지시 위반입니다.

아래는 인스타그램 계정의 이번 주 성장지표 데이터입니다.
이 데이터를 바탕으로 클라이언트에게 보낼 "계정 성장지표" 섹션을, 아래 지정된
형식 그대로 작성해 주세요.

기본 조건
- 수치의 값 자체는 아래 제공된 데이터를 그대로 사용합니다. 재계산하지 마세요.
  (콤마를 넣는 것은 "값 변경"이 아니라 "표기"이며, 위 필수 규칙에 따라 반드시 적용합니다.)
- 인사말, 안내 문구, 마무리 인사("추가로 궁금하신 사항이 있으시면..." 등) 없이,
  아래 형식의 본문 내용만 출력합니다. 다른 설명을 앞뒤에 붙이지 마세요.
- 증감이 양수면 "증가", 음수면 "감소"라는 단어를 함께 표기합니다.
- 주관적인 평가나 추측은 배제하고, 데이터에 기반한 사실만 전달합니다.
- 아래 형식의 볼드 헤더(**)와 글머리 기호(*) 구조를 그대로 유지합니다.

형식 (아래 구조를 그대로 따르되, 실제 값은 데이터에서 가져와 채워 넣으세요.
괄호 안 두 값의 순서는 헤더에 표시된 비교 기준 순서와 동일하게, 라벨 없이 값만 적으세요):

**1. 팔로워** (초기 대비 / 전주 대비)
* 총 팔로워 수: [followers.wow.value]명
* 증감: ([followers.baseline.delta]명 증가/감소 / [followers.wow.delta]명 증가/감소)
* 성장률: ([followers.baseline.growth_pct]% 증가/감소 / [followers.wow.growth_pct]% 증가/감소)

**1-1. 타겟층 팔로워** (전주 대비)
* [연령] [성별] : [값]명 ([증감]명 증가/감소, [성장률]%)
  ※ followers.target_segments 배열의 항목 수만큼, 항목마다 한 줄씩 작성하세요.
     배열이 비어있으면 이 섹션(1-1) 전체를 생략하세요.

**2. 조회수** (전주 대비)
* 총 조회수: [views.wow.value]회
* 증감: [views.wow.delta]회

**3. 프로필 방문** (전주 대비)
* 총 프로필 방문: [profile_views.wow.value]회
* 증감: [profile_views.wow.delta]회

**4. 좋아요** (전주 대비)
* 총 좋아요: [likes.wow.value]회
* 증감: [likes.wow.delta]회

**5. 전체 상호작용** (전주 대비 / 전월 대비)
* 총 전체 상호작용: [total_interactions.wow.value]회
* 증감: ([total_interactions.wow.delta]회 증가/감소 / [total_interactions.mom.delta]회 증가/감소)

데이터:
{data_json}
"""