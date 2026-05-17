"""
utils/llm.py — LLM 호출 래퍼 (_llm, _llm_json)
"""

import re, json
import deps


async def llm(system: str, user: str, temperature: float = 0.3, max_tokens: int = 1200) -> str:
    resp = await deps.openai_client.chat.completions.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


async def llm_json(system: str, user: str, temperature: float = 0.2, max_tokens: int = 2000) -> dict | list:
    system_j = system + "\n\n반드시 유효한 JSON만 출력하세요. 마크다운 코드블록, 설명 텍스트, 주석 금지. JSON 외 어떤 문자도 포함하지 마세요."
    raw = await llm(system_j, user, temperature, max_tokens)
    raw = re.sub(r"```(?:json)?|```", "", raw).strip()
    match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', raw)
    if match:
        raw = match.group(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"[LLM JSON 파싱 실패] raw 응답 앞 200자: {raw[:200]}")
        return {}
