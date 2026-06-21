"""
app.py — 서강 진로 코파일럿 FastAPI 진입점

역할: DB·LLM 클라이언트 초기화 + 라우터 등록 + 정적 파일 서빙
비즈니스 로직은 routers/ 와 utils/ 에 위치한다.

실행:
  GATEWAY_API_KEY=your-key uvicorn app:app --reload --port 8000
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from openai import AsyncOpenAI

import config
import deps
from routers import dashboard, planner, rebalance, recommender, opportunities, alumni

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(BASE_DIR, "sogang_copilot_v3.html")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🔧 KUZU 그래프 DB 연결 중...")
    deps.kuzu_conn = config.get_connection(config.DB_PATH)
    print("✅ KUZU 연결 완료")

    deps.openai_client = AsyncOpenAI(
        api_key=os.getenv("GATEWAY_API_KEY", ""),
        base_url="https://factchat-cloud.mindlogic.ai/v1/gateway",
    )
    print("✅ API Gateway 클라이언트 준비 완료")

    yield
    print("서버 종료")


app = FastAPI(
    title="서강 진로 코파일럿 API",
    description="OWL 온톨로지 + KUZU 그래프 + API Gateway (claude-sonnet-4-20250514) 기반 5-모듈 학사 AI",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 라우터 등록 ────────────────────────────────────────────────
app.include_router(dashboard.router)
app.include_router(planner.router)         # MODULE 01
app.include_router(rebalance.router)       # MODULE 02
app.include_router(recommender.router)     # MODULE 03
app.include_router(opportunities.router)   # MODULE 04
app.include_router(alumni.router)          # MODULE 05



# ── 정적 파일 서빙 ─────────────────────────────────────────────
@app.get("/")
async def root():
    if not os.path.exists(HTML_FILE):
        raise HTTPException(404, "sogang_copilot_v3.html 파일을 찾을 수 없습니다.")
    return FileResponse(HTML_FILE)


@app.get("/api/health")
async def health():
    from utils.llm import _MODEL
    return {"status": "ok", "db": config.DB_PATH, "model": _MODEL}


# ── 보조 그래프 조회 API ───────────────────────────────────────
@app.get("/api/graph/dept/{dept_name}")
async def get_dept_courses(dept_name: str):
    dept = config.query_dept_info(deps.kuzu_conn, dept_name)
    if not dept:
        raise HTTPException(404, f"학과 없음: {dept_name}")
    courses = config.query_dept_courses(deps.kuzu_conn, dept["iri"])
    return {"dept": dept, "courses": courses, "total": len(courses)}


@app.get("/api/graph/prereq/{course_code}")
async def get_prereq(course_code: str):
    chain = config.query_prereq_chain(deps.kuzu_conn, course_code.upper())
    return {"code": course_code.upper(), "prereq_chain": chain}


@app.get("/api/graph/combined/{dept_name}")
async def get_combined(dept_name: str):
    dept = config.query_dept_info(deps.kuzu_conn, dept_name)
    if not dept:
        raise HTTPException(404, f"학과 없음: {dept_name}")
    combined = config.query_combined_majors_for_dept(deps.kuzu_conn, dept["iri"])
    return {"dept": dept["name"], "combined_majors": combined}


@app.get("/api/graph/codeshare/{prefix}")
async def get_codeshare(prefix: str):
    return config.query_code_shares(deps.kuzu_conn, prefix.upper())


@app.get("/api/stats")
async def get_stats():
    result = {}
    for tbl in ["AcademicCluster", "College", "Department", "Major", "Course", "AcademicPolicy"]:
        r = deps.kuzu_conn.execute(f"MATCH (n:{tbl}) RETURN count(n) AS cnt")
        result[tbl] = r.get_next()[0]
    return result
