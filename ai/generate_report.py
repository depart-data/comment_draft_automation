"""
ai/generate_report.py

extract/에서 뽑은 데이터를 prompts/combined로 하나의 프롬프트로 합치고,
ai/gemini_client.py의 구조화 출력으로 Gemini API를 "계정당 1회만" 호출해서
섹션1·2·3을 동시에 만듭니다.

(이전에는 섹션별로 3회 호출했으나, 하루 요청 한도가 20회로 확인되어
 계정당 1회로 줄여 처리 가능한 계정 수를 3배 이상 늘렸습니다.)

데이터가 없는 섹션(예: 트래픽 캠페인이 없는 주)은 프롬프트에 아예 포함하지
않고, AI 호출 없이 정적 안내 메시지로 처리합니다.

전부 성공하거나 전부 실패하는 방식입니다 (부분 성공 저장 없음). 실패 시
"[combined] 생성 중 실패: (원인)" 형태의 단일 메시지로 예외를 발생시킵니다.
(섹션별 실패 위치 구분은 통합 호출 방식의 트레이드오프로 포기함)

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

from build_campaign_report import build_campaign_report_data
from build_section1_highlights import build_section1_highlights
from build_section2_highlights import build_section2_highlights
from prompt_combined import build_prompt_combined, build_response_schema
from gemini_client import generate_structured_content
from config.accounts import get_target_segments


def generate_weekly_report(ad_account_id: int, week_start: str, week_end: str) -> dict:
    """
    지정 계정·주간의 리포트를 섹션1·2·3 한 번의 AI 호출로 생성합니다.

    Returns:
        dict: {"section1": ..., "section2": ..., "section3": ...}
              또는 {"error": ...} (데이터 자체가 없는 경우)

    Raises:
        RuntimeError: AI 생성에 실패한 경우. 메시지 형식: "[combined] 생성 중 실패: (원인)"
                      이 메시지는 나중에 storage/save_draft.py에서 error_message와
                      section1~3_text 컬럼에 동일하게 저장할 용도입니다.
    """
    data = build_campaign_report_data(ad_account_id, week_start, week_end)
    if "error" in data:
        return {"error": data["error"]}

    report_sections = {}
    section_data_for_ai = {}

    # 섹션1 (데이터 있으면 AI 호출 대상에 포함, 없으면 정적 메시지)
    if data["traffic"]["has_data"]:
        section_data_for_ai["section1"] = build_section1_highlights(data, week_start, week_end)
    else:
        report_sections["section1"] = "⚠️ 이 기간에 트래픽 캠페인이 없어 섹션1을 생성할 수 없습니다."

    # 섹션2 (데이터 있으면 AI 호출 대상에 포함, 없으면 정적 메시지)
    if data["traffic"]["has_data"]:
        target_segments = get_target_segments(ad_account_id)
        section_data_for_ai["section2"] = build_section2_highlights(data, week_start, week_end, target_segments)
    else:
        report_sections["section2"] = "⚠️ 이 기간에 트래픽 캠페인이 없어 섹션2를 생성할 수 없습니다."

    # 섹션3 (데이터 있으면 AI 호출 대상에 포함, 없으면 정적 메시지)
    if "error" not in data["account_growth"]:
        section_data_for_ai["section3"] = data["account_growth"]
    else:
        report_sections["section3"] = f"⚠️ {data['account_growth']['error']}"

    # AI로 만들 섹션이 하나도 없으면, API 호출 없이 정적 메시지만 반환
    if not section_data_for_ai:
        return report_sections

    prompt = build_prompt_combined(section_data_for_ai)
    schema = build_response_schema(list(section_data_for_ai.keys()))

    try:
        ai_result = generate_structured_content(prompt, schema)
    except Exception as e:
        raise RuntimeError(f"[combined] 생성 중 실패: {e}") from e

    report_sections.update(ai_result)
    return report_sections


if __name__ == "__main__":
    AD_ACCOUNT_ID = 14
    WEEK_START = "2026-07-06"
    WEEK_END = "2026-07-12"

    try:
        result = generate_weekly_report(AD_ACCOUNT_ID, WEEK_START, WEEK_END)

        if "error" in result:
            print(f"⚠️ {result['error']}")
        else:
            for section in ["section1", "section2", "section3"]:
                print(f"=== {section} ===")
                print(result.get(section, "(없음)"))
                print()
    except RuntimeError as e:
        print(f"❌ 리포트 생성 실패: {e}")