"""
extract/db_connect.py

PostgreSQL DB 접근 스크립트

사전 준비:
    pip install psycopg2-binary python-dotenv pandas

사용법:
    1) .env.example을 복사해서 .env로 저장하고, 실제 접속 정보를 채워넣으세요.
    2) run_query()로 SELECT 쿼리를 실행하세요.

주의:
    - 이 스크립트는 기본적으로 SELECT(조회) 용도로 작성되어 있습니다.
    - 데이터를 변경하는 쿼리(INSERT/UPDATE/DELETE 등)는 이 스크립트로 실행하지 않는 것을 권장합니다.
"""

import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv

# .env 파일에서 접속 정보 로드
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


def get_connection():
    """DB 커넥션을 생성해서 반환합니다."""
    missing = [k for k, v in DB_CONFIG.items() if not v]
    if missing:
        raise ValueError(
            f".env에 다음 값이 비어있습니다: {missing}. "
            f".env.example을 참고해서 .env 파일을 채워주세요."
        )
    return psycopg2.connect(**DB_CONFIG)


def run_query(query: str, params: tuple = None) -> pd.DataFrame:
    """
    SELECT 쿼리를 실행하고 결과를 pandas DataFrame으로 반환합니다.

    Args:
        query: 실행할 SQL 쿼리 (SELECT 권장)
        params: 쿼리에 바인딩할 파라미터 (SQL 인젝션 방지를 위해 문자열 포매팅 대신 사용)

    Returns:
        pandas.DataFrame
    """
    conn = get_connection()
    try:
        df = pd.read_sql_query(query, conn, params=params)
        return df
    finally:
        conn.close()


def test_connection():
    """DB 접속이 정상적으로 되는지 확인합니다."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            print(f"✅ 접속 성공\nPostgreSQL 버전: {version}")
    finally:
        conn.close()


if __name__ == "__main__":
    test_connection()
