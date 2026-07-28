"""
prompts/prompt_section4.py

지난 주차들의 섹션4 텍스트를 요약해서, 작성자가 이번 주 섹션4를 쓸 때
참고할 수 있는 자료를 만드는 프롬프트입니다.

※ 아직 구현되지 않았습니다. 자리만 마련해둔 상태입니다.

주의: 이건 섹션1~3과 성격이 다릅니다 — "숫자를 정해진 양식으로 포맷팅"하는
게 아니라 "과거 텍스트들의 패턴을 요약"하는 작업이라, 할루시네이션 위험이
섹션1~3보다 높습니다 (reference_notes.md의 "섹션4 할루시네이션 방지 방안"
논의 참고 — 주장에 근거 데이터 인용 강제, 금지 패턴 명시 등).
구현 시 이 위험 관리 방안을 함께 반영해야 합니다.

입력 데이터 출처: extract/build_section4_context.py의 get_past_section4_texts() 반환값
(현재 그 함수 자체가 미구현 상태)
"""


def build_prompt_section4(past_texts: list) -> str:
    """
    과거 섹션4 텍스트 목록을 받아, 요약 참고자료를 만드는 프롬프트를 조립합니다.

    Args:
        past_texts: extract/build_section4_context.py의 get_past_section4_texts() 반환값

    Returns:
        str: 완성된 프롬프트 텍스트

    Raises:
        NotImplementedError: 아직 구현되지 않았습니다.
    """
    raise NotImplementedError("섹션4 참고자료 프롬프트는 아직 구현되지 않았습니다.")
