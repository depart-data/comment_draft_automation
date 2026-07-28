"""
run_weekly_reports.py

전체 파이프라인의 최상위 진입점입니다.
config.accounts에 등록된 모든 ad_account_id를 순회하면서, 각 계정의
주간 리포트를 생성합니다.

트리거 스케줄 (2026-07-21 확정): 매주 월요일 오전 11시 + 매주 화요일 오전 11시
(수동 "초안 생성" 버튼 트리거는 폐기됨 — 아래 이전 계획 참고)
sprint_notes_drafts는 스프린트 넘버 + ad_account_id로 구분되므로, 화요일
실행분이 월요일 실행분을 사실상 대체하는 최신본으로 남게 됩니다.

# ── 이전 계획 (폐기, 참고용으로 주석 처리만 하고 삭제하지 않음) ──
# "이번 주"는 config.week_utils.get_report_week_range()로 자동 계산됩니다.
# 업무 사이클(콘텐츠 게시 N주 → 광고 집행 N+1주 → 리포트 작성 N+2주)에 따라,
# 트리거 시점의 "지난 주(캠페인이 집행됐던 주간)"가 리포트 대상이 됩니다.
# 오늘이 월요일이든 아니든(월요일 10시 / 월요일 13시 / 초안 생성 버튼 클릭,
# 어느 요일에 눌러도) 항상 같은 지난 주 범위를 가리킵니다.
# ────────────────────────────────────────────────

week_end는 이제 트리거 요일에 따라 달라집니다 (실행일 - 1일, 어제까지).
캠페인이 "월요일 시작 ~ 그 다음 주 월요일까지" 운영되기 때문에, 화요일
실행분은 월요일 실행분보다 하루치(월요일 오전 시간대) 성과를 더 포함합니다.
자세한 계산 로직은 config/week_utils.py 참고.

DB 적재(storage/save_draft.py)가 실제로 연결되어 있습니다.
성공/실패 모두 sprint_notes_drafts 테이블에 저장됩니다.
sprint_number는 clients.sprint_anchor_date/sprint_anchor_number 기준으로
save_draft_report() 내부에서 자동 계산됩니다 (2026-07-22 확정, 더 이상 임시값 아님).

2026-07-28 개편: generate_weekly_report()의 반환 구조가
{"section1","section2","section3"} 고정 3개에서
{"campaigns": [{"campaign_name":..., "text":...}, ...], "section3": "..."}
로 바뀌었습니다 (트래픽 캠페인이 여러 개면 각각 따로 리포트가 생성되므로).
아래 콘솔 출력부도 이 구조에 맞게 캠페인 개수만큼 반복 출력합니다.

※ 이 파일 자체는 스케줄러가 아닙니다. 실행하면 즉시 1회 동작합니다.
   "매주 월요일/화요일 11시 자동 실행"은 이 파일을 호출하는 별도의 스케줄러
   (Windows 작업 스케줄러 / cron 등, config.settings.SCHEDULE_CRON 참고)가
   추후 담당합니다. 지금은 지금까지 해온 것처럼 즉시 테스트용으로 실행하면 됩니다.

사전 준비:
    config/, extract/, prompts/, ai/ 폴더가 모두 프로젝트 루트 아래에 있어야 합니다.
"""

from config.accounts import get_active_ad_account_ids
from config.settings import SCHEDULE_DESCRIPTION
from config.week_utils import get_report_week_range
from ai.generate_report import generate_weekly_report
from storage.save_draft import save_draft_report

# ══════════════════════════════════════════════════════════════
#  ⚙️  설정
# ══════════════════════════════════════════════════════════════
# 기본값: 오늘 날짜 기준 자동 계산 (None으로 두면 자동 계산됨)
# 테스트 등의 이유로 특정 주간을 강제로 지정하고 싶으면 아래 두 줄의 주석을
# 풀고 직접 값을 넣으세요 (예: WEEK_START = "2026-07-06").
# (이건 "수동 트리거"가 아니라 로컬 테스트용 오버라이드입니다 — 수동 트리거
#  버튼 자체는 폐기되었습니다)
WEEK_START = None
WEEK_END = None
# ══════════════════════════════════════════════════════════════


def run_all_accounts(week_start: str, week_end: str) -> dict:
    """
    config.accounts에 등록된 전체 계정을 순회하며 리포트를 생성합니다.
    한 계정에서 오류가 나도 나머지 계정은 계속 진행됩니다.

    Returns:
        dict: {ad_account_id: {"status": "success"/"failed", "result": ..., "error": ...}}
    """
    ad_account_ids = get_active_ad_account_ids()
    summary = {}

    for ad_account_id in ad_account_ids:
        print("\n" + "#" * 70)
        print(f"#  ad_account_id = {ad_account_id}")
        print("#" * 70)

        try:
            result = generate_weekly_report(ad_account_id, week_start, week_end)

            if "error" in result:
                # 데이터 자체가 없는 경우 (예: 이 기간에 캠페인이 없음).
                # AI 실패는 아니지만, 감사 추적을 위해 실패로 기록해서 저장합니다.
                print(f"⚠️ {result['error']}")
                save_draft_report(
                    ad_account_id, week_start, error_message=result["error"]
                )
                summary[ad_account_id] = {"status": "failed", "error": result["error"]}
                continue

            for i, camp in enumerate(result.get("campaigns", []), start=1):
                print(f"\n=== 트래픽 캠페인 {i}: {camp['campaign_name']} ===")
                print(camp["text"])

            print(f"\n=== 섹션3: 계정 성장지표 ===")
            print(result.get("section3", ""))

            save_draft_report(ad_account_id, week_start, report_sections=result)
            print(f"\n✅ sprint_notes_drafts에 저장 완료 (ad_account_id={ad_account_id})")

            summary[ad_account_id] = {"status": "success", "result": result}

        except Exception as e:
            print(f"❌ ad_account_id={ad_account_id} 처리 중 예외 발생: {e}")
            try:
                save_draft_report(ad_account_id, week_start, error_message=str(e))
                print(f"✅ 실패 내역도 sprint_notes_drafts에 기록됨 (ad_account_id={ad_account_id})")
            except Exception as save_error:
                print(f"❌ 실패 내역 저장도 실패함: {save_error}")
            summary[ad_account_id] = {"status": "failed", "error": str(e)}

    return summary


if __name__ == "__main__":
    week_start = WEEK_START
    week_end = WEEK_END
    if week_start is None or week_end is None:
        week_start, week_end = get_report_week_range()

    print(f"실행 스케줄(참고용): {SCHEDULE_DESCRIPTION}")
    print(f"조회 주간: {week_start} ~ {week_end}")
    print(f"대상 계정: {get_active_ad_account_ids()}")

    summary = run_all_accounts(week_start, week_end)

    print("\n" + "=" * 70)
    print("=== 전체 실행 요약 ===")
    for ad_account_id, info in summary.items():
        print(f"ad_account_id={ad_account_id}: {info['status']}")

    success_count = sum(1 for v in summary.values() if v["status"] == "success")
    print(f"\n성공: {success_count}/{len(summary)}")
