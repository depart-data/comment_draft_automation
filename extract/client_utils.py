"""
extract/client_utils.py

client_id 조회, sprint_number 계산 등 여러 곳(extract/, storage/)에서
공통으로 쓰이는 로직을 모아둔 파일입니다.

원래 storage/save_draft.py에만 있던 로직인데, extract/build_campaign_report.py의
캠페인 식별 단계(3번째 필터: 스프린트 번호 매칭)에서도 필요해져서
공통 위치로 옮겼습니다 (2026-07-28).

사전 준비:
    extract/db_connect.py, .env 파일이 있는 프로젝트 구조여야 합니다.
"""

import os
import sys
from datetime import timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_connect import run_query


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

    계산 방식 (2026-07-22 확정, 2026-07-28 client_id=15(루업)로 재검증 완료:
    anchor_date=2025-12-01, anchor_number=1 -> 2026-07-20 주간 = 스프린트 34,
    실제 캠페인명 "S34"와 정확히 일치 확인됨):
    1. sprint_anchor_date가 속한 주의 월요일을 구함 (anchor_week_monday)
       ※ sprint_anchor_date가 NULL인 경우, clients.created_at으로 대체합니다.
    2. week_start와 anchor_week_monday 사이의 주(week) 차이를 계산
    3. sprint_number = sprint_anchor_number + 그 주 차이

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
