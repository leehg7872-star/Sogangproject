"""
deps.py — 전역 상태 (kuzu_conn, openai_client)

모든 라우터가 이 모듈을 import해서 공유 상태에 접근한다.
app.py의 lifespan에서 초기화한다.
"""

import kuzu
from openai import AsyncOpenAI

kuzu_conn: kuzu.Connection = None
openai_client: AsyncOpenAI = None
