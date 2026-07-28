"""
ai/generate_report.py

extract/build_campaign_report.py의 build_per_campaign_report()를 사용해서,
트래픽 캠페인을 "각각 따로" AI로 정리하고, 계정 성장지표(섹션3)는 계정
전체 기준으로 딱 1번만 정리합니다. (2026-07-28 개편)

이전에는 캠페인들을 전부 합쳐서 섹션1·2를 만들었으나, 같은 주에 정규
주간 캠페인과 특별 캠페인(예: "팔로워 상위 5개")이 함께 잡히면 콘텐츠
개수가 왜곡되는 문제가 있었습니다. 이제는 캠페인별로 분리해서 각각 AI
호출 1회(섹션1+2)를 하고, 섹션3은 캠페인과 무관하므로 별도로 1회만
호출합니다. 계정당 총 호출 횟수 = (트래픽 캠페인 수 + 1).
(하루 요청 한도 500회 확인 후, 이 정도 호출 증가는 문제없다고 판단)

기존 prompts/prompt_combined.py를 그대로 재사용합니다 — 캠페인별로는
{"section1":..., "section2":...}만 넣어서 호출하고, 섹션3은
{"section3":...}만 넣어서 별도 호출합니다.

전부 성공하거나, 실패한 지점(어느 캠페인인지 / 섹션3인지)을 정확히
알 수 있게 태그가 붙은 메시지로 예외를 발생시킵니다. 하나라도 실패하면
그 시점에서 중단됩니다 (부분 성공 저장 없음, 이전과 동일한 원칙 유지).

사전 준비:
    config/, extract/, prompts/, ai/ 폴더가 모두 프로젝트 루트 아래에 있어야 합니다.
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)

sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "extract"))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "prompts"))
sys.path.insert(0, _THIS_DIR)

from build_campaign_report import build_per_campaign_report
from prompt_combined import build_prompt_combined, build_response_schema
from gemini_client import generate_structured_content


def generate_weekly_report(ad_account_id: int, week_start: str, week_end: str) -> dict:
    """
    지정 계정·주간의 리포트를 생성합니다. 트래픽 캠페인마다 각각 섹션1+2를
    만들고, 섹션3(계정 전체)은 1번만 만듭니다.

    Returns:
        dict: {
            "campaigns": [
                {"campaign_name": ..., "text": "섹션1+2 텍스트"},
                ...
            ],
            "section3": "섹션3 텍스트"
        }
        또는 {"error": ...} (데이터 자체가 없는 경우)

    Raises:
        RuntimeError: AI 생성 실패 시. 메시지에 어느 캠페인/섹션에서
                      실패했는지 태그가 붙습니다
                      (예: "[캠페인: [디파트]260720 - S34 트래픽] 생성 중 실패: ...").
                      이 메시지는 storage/save_draft.py에서 error_message와
                      notes에 동일하게 저장됩니다.
    """
    data = build_per_campaign_report(ad_account_id, week_start, week_end)
    if "error" in data:
        return {"error": data["error"]}

    campaign_reports = []
    for camp in data["traffic_campaigns"]:
        if camp["section1"] is None:
            campaign_reports.append({
                "campaign_name": camp["campaign_name"],
                "text": "이 캠페인은 데이터가 없어 리포트를 생성할 수 없습니다.",
            })
            continue

        section_data_for_ai = {"section1": camp["section1"], "section2": camp["section2"]}
        prompt = build_prompt_combined(section_data_for_ai)
        schema = build_response_schema(["section1", "section2"])

        try:
            ai_result = generate_structured_content(prompt, schema)
        except Exception as e:
            raise RuntimeError(f"[캠페인: {camp['campaign_name']}] 생성 중 실패: {e}") from e

        # section1/section2는 줄 단위 배열로 응답받음 (prompts/prompt_combined.py 참고
        # — Gemini가 통짜 문자열에서 줄바꿈을 가끔 안 지키는 문제 때문에 배열로 강제)
        section1_text = "\n".join(ai_result["section1"])
        section2_text = "\n".join(ai_result["section2"])
        combined_text = section1_text + "\n\n" + section2_text
        campaign_reports.append({
            "campaign_name": camp["campaign_name"],
            "text": combined_text,
        })

    account_growth = data["account_growth"]
    if "error" in account_growth:
        section3_text = account_growth["error"]
    else:
        prompt3 = build_prompt_combined({"section3": account_growth})
        schema3 = build_response_schema(["section3"])
        try:
            ai_result3 = generate_structured_content(prompt3, schema3)
        except Exception as e:
            raise RuntimeError(f"[섹션3] 생성 중 실패: {e}") from e
        section3_text = "\n".join(ai_result3["section3"])

    return {
        "campaigns": campaign_reports,
        "section3": section3_text,
    }


if __name__ == "__main__":
    AD_ACCOUNT_ID = 14
    WEEK_START = "2026-07-20"
    WEEK_END = "2026-07-26"

    try:
        result = generate_weekly_report(AD_ACCOUNT_ID, WEEK_START, WEEK_END)

        if "error" in result:
            print(result["error"])
        else:
            for i, camp in enumerate(result["campaigns"], start=1):
                print(f"=== 트래픽 캠페인 {i}: {camp['campaign_name']} ===")
                print(camp["text"])
                print()
            print("=== 섹션3: 계정 성장지표 ===")
            print(result["section3"])
    except RuntimeError as e:
        print(f"리포트 생성 실패: {e}")
