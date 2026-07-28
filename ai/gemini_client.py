"""
ai/gemini_client.py

Gemini API 호출을 담당합니다.
- 요청 속도 제한: config.settings.RATE_LIMIT_PER_MINUTE(기본 분당 3회, 실제
  한도인 분당 5회보다 여유를 둔 안전값) 초과 시 자동으로 대기합니다.
- 재시도: API 호출이 실패하면 지수 백오프(2초, 4초, 8초...)로 최대 3회까지
  재시도합니다.
- 구조화 출력: generate_structured_content()로 JSON 스키마를 강제해서,
  섹션1~3을 한 번의 호출로 합쳐 받아올 때 파싱 실수 없이 dict로 반환합니다.
  (하루 요청 한도가 20회로 확인되어, 계정당 3회→1회로 줄이기 위해 도입)

사전 준비:
    pip install google-genai python-dotenv
    .env 파일에 GEMINI_API_KEY=... 추가
"""

import os
import sys
import time
import json
from collections import deque
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 프로젝트 루트를 sys.path에 추가해 config 패키지를 찾을 수 있게 함
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import GEMINI_MODEL, RATE_LIMIT_PER_MINUTE

load_dotenv()

# 최근 호출 시각을 기록해 속도 제한을 계산하는 큐
_call_timestamps = deque()

_client = None


def _get_client():
    """Gemini 클라이언트를 1회만 생성해서 재사용합니다."""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(".env에 GEMINI_API_KEY가 설정되어 있지 않습니다.")
        _client = genai.Client(api_key=api_key)
    return _client


def _wait_for_rate_limit():
    """
    최근 60초 이내 호출 횟수가 RATE_LIMIT_PER_MINUTE를 넘지 않도록,
    필요하면 대기합니다.
    """
    now = time.time()
    while _call_timestamps and now - _call_timestamps[0] > 60:
        _call_timestamps.popleft()

    if len(_call_timestamps) >= RATE_LIMIT_PER_MINUTE:
        wait_seconds = 60 - (now - _call_timestamps[0]) + 0.1
        if wait_seconds > 0:
            print(f"⏳ 속도 제한({RATE_LIMIT_PER_MINUTE}회/분)으로 {wait_seconds:.1f}초 대기합니다...")
            time.sleep(wait_seconds)


def generate_content(prompt: str, max_retries: int = 3) -> str:
    """
    속도 제한과 재시도 로직을 적용해서 Gemini API를 호출하고,
    생성된 텍스트를 반환합니다. (자유 텍스트 응답용, 단일 섹션 호출 등에 사용)

    Args:
        prompt: 전달할 프롬프트 전체 텍스트
        max_retries: 실패 시 최대 재시도 횟수 (기본 3회)

    Returns:
        str: 모델이 생성한 응답 텍스트
    """
    client = _get_client()

    last_error = None
    for attempt in range(1, max_retries + 1):
        _wait_for_rate_limit()
        _call_timestamps.append(time.time())

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            return response.text
        except Exception as e:
            last_error = e
            wait = 2 ** attempt  # 2초, 4초, 8초...
            print(f"⚠️ API 호출 실패 ({attempt}/{max_retries}회차): {e}")
            if attempt < max_retries:
                print(f"   {wait}초 후 재시도합니다...")
                time.sleep(wait)

    raise RuntimeError(f"Gemini API 호출이 {max_retries}회 모두 실패했습니다: {last_error}")


def generate_structured_content(prompt: str, response_schema: dict, max_retries: int = 3) -> dict:
    """
    JSON 스키마를 강제해서 Gemini API를 호출하고, 파싱된 dict를 반환합니다.
    섹션1~3을 하나의 호출로 합쳐 받아올 때 사용합니다 (계정당 요청 3회 → 1회).

    Args:
        prompt: 전달할 프롬프트 전체 텍스트
        response_schema: 강제할 JSON 스키마 (OpenAPI 서브셋 형식의 dict)
        max_retries: 실패 시 최대 재시도 횟수 (기본 3회)

    Returns:
        dict: 스키마에 맞게 파싱된 응답
    """
    client = _get_client()

    last_error = None
    for attempt in range(1, max_retries + 1):
        _wait_for_rate_limit()
        _call_timestamps.append(time.time())

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            last_error = e
            wait = 2 ** attempt
            print(f"⚠️ API 호출 실패 ({attempt}/{max_retries}회차): {e}")
            if attempt < max_retries:
                print(f"   {wait}초 후 재시도합니다...")
                time.sleep(wait)

    raise RuntimeError(f"Gemini API 호출이 {max_retries}회 모두 실패했습니다: {last_error}")


if __name__ == "__main__":
    # 간단한 동작 테스트
    test_prompt = "안녕하세요라고 존댓말로 짧게 인사해 주세요."
    print(generate_content(test_prompt))