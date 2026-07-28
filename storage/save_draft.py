"""
storage/save_draft.py

생성된 리포트 텍스트를 sprint_notes_drafts 테이블에 저장합니다.

테이블은 실제로 생성되어 있고, run_weekly_reports.py에서 정상적으로 호출되어
저장됩니다 (2026-07-28 실행 확인).

테이블 구조 (2026-07-28 실제 스키마 재확인 — created_at 외에 updated_at도
있음, 기존 문서에 누락되어 있었음):
    CREATE TABLE public.sprint_notes_drafts (
        id bigserial NOT NULL,
        client_id int8 NOT NULL,
        ad_account_id int8 NOT NULL,
        sprint_number int4 NOT NULL,
        title text NULL,
        focus text NULL,
        objectives jsonb NULL,
        notes text NULL,
        tags _text NULL,
        status varchar(20) DEFAULT 'draft'::character varying NOT NULL,
        error_message text NULL,
        created_at timestamptz DEFAULT now() NOT NULL,
        updated_at timestamptz DEFAULT now() NOT NULL,
        CONSTRAINT sprint_notes_drafts_pkey PRIMARY KEY (id)
    );

필드 매핑 확정 사항:
    - title, focus, objectives, tags: 전부 NULL (사용 안 함)
    - notes: 트래픽 캠페인별 리포트(개수만큼 반복) + 섹션3을 "## " 마크다운
             으로 파이썬이 직접 합친 전체 텍스트 (2026-07-28 개편 — 이전엔
             섹션1/2/3 고정 3블록이었으나, 이제 캠페인이 여러 개면 그
             개수만큼 블록이 반복됨. build_notes_markdown() 참고)
             (AI 프롬프트가 아니라 이 파일의 코드가 조립 — 형식 실수 방지)
    - 성공 시: status='draft', notes=조립된 텍스트, error_message=NULL
    - 실패 시: status='failed', notes="⚠️ 에러 발생", error_message=상세 원인
    - model_used 컬럼은 최종 설계에서 제외하기로 결정됨 (사용 안 함)
    - sprint_number: clients.sprint_anchor_date/sprint_anchor_number 기준으로
      자동 계산됨 (get_sprint_number_for_client 참고, 2026-07-22 확정)
      계산 방식: anchor_date가 속한 주(월요일 기준) = sprint_anchor_number,
      그 이후 매 7일(1주)마다 +1씩 증가

사전 준비:
    extract/db_connect.py, .env 파일이 있는 프로젝트 구조여야 합니다.
"""

import os
import sys
from datetime import timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extract"))

from db_connect import run_query, get_connection


def get_client_id_for_ad_account(ad_account_id: int) -> int:
    """
    ad_account_id로부터 상위 개념인 client_id를 조회합니다.
    (ad_accounts -> business_portfolios -> clients)
    """
    query = """
        SELECT bp.client_id
        FROM ad_accounts acc
        JOIN business_portfolios bp ON bp.id = acc.business_portfolio_id
        WHERE acc.id = %s;
    """
    df = run_query(query, params=(ad_account_id,))
    if df.empty:
        raise ValueError(f"ad_account_id={ad_account_id}에 연결된 client_id를 찾을 수 없습니다.")
    return int(df.iloc[0]["client_id"])


def get_sprint_number_for_client(client_id: int, week_start: str) -> int:
    """
    clients.sprint_anchor_date / sprint_anchor_number를 기준으로,
    지정 week_start(반드시 월요일)에 해당하는 스프린트 번호를 계산합니다.

    계산 방식:
    1. sprint_anchor_date가 속한 주의 월요일을 구함 (anchor_week_monday)
       ※ sprint_anchor_date가 NULL인 경우, clients.created_at으로 대체합니다.
         (2026-07-22 확인: 현재 전체 브랜드 중 이 대체가 실제로 필요한 경우는
         0건이지만, 향후 새 클라이언트 추가 시를 대비한 방어 로직입니다.
         대체가 발생하면 콘솔에 경고를 출력합니다.)
    2. week_start와 anchor_week_monday 사이의 주(week) 차이를 계산
    3. sprint_number = sprint_anchor_number + 그 주 차이
       (anchor_date가 속한 주 = sprint_anchor_number, 그 다음 주부터 +1씩 증가)

    Args:
        client_id: 대상 클라이언트 ID
        week_start: 대상 리포트의 week_start (YYYY-MM-DD, 월요일)

    Returns:
        int: 계산된 스프린트 번호
    """
    query = "SELECT sprint_anchor_date, sprint_anchor_number, created_at FROM clients WHERE id = %s;"
    df = run_query(query, params=(client_id,))
    if df.empty:
        raise ValueError(f"client_id={client_id}에 해당하는 클라이언트를 찾을 수 없습니다.")

    row = df.iloc[0]
    anchor_number = int(row["sprint_anchor_number"])

    if pd.isna(row["sprint_anchor_date"]):
        # sprint_anchor_date가 없으면 client_created_at으로 대체
        if pd.isna(row["created_at"]):
            raise ValueError(
                f"client_id={client_id}: sprint_anchor_date와 created_at이 모두 없어 "
                f"스프린트 번호를 계산할 수 없습니다."
            )
        anchor_date = pd.to_datetime(row["created_at"]).date()
        print(
            f"⚠️ client_id={client_id}의 sprint_anchor_date가 비어있어, "
            f"created_at({anchor_date})으로 대체해서 스프린트 번호를 계산합니다."
        )
    else:
        anchor_date = pd.to_datetime(row["sprint_anchor_date"]).date()

    anchor_week_monday = anchor_date - timedelta(days=anchor_date.weekday())
    target_week_monday = pd.to_datetime(week_start).date()

    week_offset = (target_week_monday - anchor_week_monday).days // 7
    return anchor_number + week_offset


def build_notes_markdown(report_sections: dict) -> str:
    """
    캠페인별 리포트 + 섹션3을 "## " 마크다운 헤더로 구분해서 하나의 텍스트로
    합칩니다. (AI가 아니라 파이썬 코드가 형식을 강제 — 형식 실수 방지)

    2026-07-28 개편: 이전엔 {"section1","section2","section3"} 고정 3개
    구조였으나, 이제 트래픽 캠페인이 여러 개면 그 개수만큼 블록이 반복됩니다.

    Args:
        report_sections: ai/generate_report.py의 generate_weekly_report() 반환값
                          {"campaigns": [{"campaign_name":..., "text":...}, ...],
                           "section3": "..."}

    Returns:
        str: "## 트래픽 캠페인 1: {name}\\n{text}\\n\\n...\\n\\n## 섹션3: 계정 성장지표\\n{text}" 형태
    """
    blocks = []
    for i, camp in enumerate(report_sections.get("campaigns", []), start=1):
        blocks.append(f"## 트래픽 캠페인 {i}: {camp['campaign_name']}\n{camp['text']}")

    blocks.append(f"## 섹션3: 계정 성장지표\n{report_sections.get('section3', '')}")

    return "\n\n".join(blocks)


def save_draft_report(
    ad_account_id: int,
    week_start: str,
    report_sections: dict = None,
    error_message: str = None,
) -> None:
    """
    생성된 리포트(또는 실패 정보)를 sprint_notes_drafts 테이블에 저장합니다.
    sprint_number는 clients.sprint_anchor_date/sprint_anchor_number를 기준으로
    이 함수 내부에서 자동 계산됩니다 (get_sprint_number_for_client 참고).

    같은 (ad_account_id, sprint_number) 조합의 행이 이미 있으면 그 행을
    UPDATE(덮어쓰기)하고, 없으면 새로 INSERT합니다. 이렇게 하면 월요일 11시
    실행분을 화요일 11시 실행분이 자동으로 덮어써서, 조회 측(개발팀 구현)이
    "브랜드 id + 스프린트 넘버"로 조회했을 때 항상 최신 결과 하나만 남습니다.

    ※ 테이블에 (ad_account_id, sprint_number) UNIQUE 제약이 없어서,
      DB의 UPSERT(ON CONFLICT) 대신 애플리케이션 레벨에서 "조회 후 분기"
      방식으로 구현했습니다. 트리거가 하루 최대 2회(월/화 11시)로 드물게
      실행되는 구조라 동시성 문제는 사실상 없다고 판단했습니다.

    성공한 경우와 실패한 경우 중 정확히 하나의 인자만 채워서 호출하세요.

    Args:
        ad_account_id: 대상 광고 계정 ID
        week_start: 이번 리포트의 week_start (YYYY-MM-DD, 월요일) — sprint_number
                     자동 계산에 사용됨
        report_sections: 성공 시, ai/generate_report.py의 generate_weekly_report()
                          반환값 {"section1": ..., "section2": ..., "section3": ...}
        error_message: 실패 시, "[combined] 생성 중 실패: ..." 형태의 에러 메시지
                        (ai/generate_report.py가 던지는 RuntimeError의 메시지 그대로)

    Raises:
        ValueError: report_sections와 error_message 둘 다 없거나 둘 다 있는 경우,
                    또는 client_id/sprint_anchor 정보를 찾을 수 없는 경우
    """
    if (report_sections is None) == (error_message is None):
        raise ValueError("report_sections 또는 error_message 중 정확히 하나만 전달해야 합니다.")

    client_id = get_client_id_for_ad_account(ad_account_id)
    sprint_number = get_sprint_number_for_client(client_id, week_start)

    if report_sections is not None:
        status = "draft"
        notes = build_notes_markdown(report_sections)
        error_message_value = None
    else:
        status = "failed"
        notes = f"⚠️ {error_message}"
        error_message_value = error_message

    # 같은 (ad_account_id, sprint_number) 조합의 기존 행이 있는지 확인
    existing_query = """
        SELECT id
        FROM sprint_notes_drafts
        WHERE ad_account_id = %s AND sprint_number = %s
        LIMIT 1;
    """
    existing_df = run_query(existing_query, params=(ad_account_id, sprint_number))

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if not existing_df.empty:
                # 기존 행이 있으면 덮어쓰기. created_at(최초 생성 시각)은 그대로
                # 두고, updated_at만 now()로 갱신해서 "언제 마지막으로 갱신됐는지"를
                # 정확히 반영합니다 (2026-07-28 수정 — 이전에는 반대로 created_at을
                # 덮어쓰고 updated_at은 건드리지 않아서 값이 거꾸로 찍혔음).
                existing_id = int(existing_df.iloc[0]["id"])
                update_query = """
                    UPDATE sprint_notes_drafts
                    SET notes = %s, status = %s, error_message = %s, updated_at = now()
                    WHERE id = %s;
                """
                cur.execute(update_query, (notes, status, error_message_value, existing_id))
            else:
                # 없으면 새로 삽입
                insert_query = """
                    INSERT INTO sprint_notes_drafts
                        (client_id, ad_account_id, sprint_number, notes, status, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """
                cur.execute(
                    insert_query,
                    (client_id, ad_account_id, sprint_number, notes, status, error_message_value),
                )
        conn.commit()
    finally:
        conn.close()
