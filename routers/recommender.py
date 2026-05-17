"""
routers/recommender.py — MODULE 03: 직무 적합도 강의 추천

엔드포인트:
  POST /api/recommender  TOPSIS 선별 + LLM fit 점수 평가
"""

import json
from fastapi import APIRouter

import config
import deps
from models import RecommenderRequest
from utils.common import completed_set, dept_iri_from_profile, major_display
from utils.career import get_career_profile, weighted_fit
from utils.inference import sanitize_prereq_map, topsis_rank
from utils.llm import llm, llm_json

router = APIRouter()

RECOMMENDER_SYSTEM = """당신은 서강대학교 강의 추천 AI입니다.
미이수 과목 목록과 목표 직무를 받아 각 과목의 직무 적합도(0~100)를 평가합니다.

출력 JSON 구조 (배열):
[
  {
    "code": "CHI4008",
    "name": "무역 중국어",
    "credits": 3,
    "type": "ElectiveCourse",
    "typeLabel": "전공선택",
    "fit": 95,
    "gpa": 3.6,
    "description": "무역관련 중국어 집중",
    "fitReason": "직무 연관성 한 줄 설명"
  }
]

fit 점수 기준:
- 80 이상: 직무 핵심 관련
- 50~79: 부분 연관
- 49 이하: 간접 연관"""


@router.post("/api/recommender")
async def recommender(req: RecommenderRequest):
    """MODULE 03: 직무 적합도 강의 추천"""
    p         = req.profile
    dept_iri  = dept_iri_from_profile(p)
    completed = completed_set(p)

    all_courses = config.query_dept_courses(deps.kuzu_conn, dept_iri) if dept_iri else []
    for extra_name in [p.secondaryMajor, p.thirdMajor]:
        if extra_name:
            extra_dept = config.query_dept_info(deps.kuzu_conn, extra_name)
            if extra_dept:
                all_courses += config.query_dept_courses(deps.kuzu_conn, extra_dept["iri"])

    seen_codes: set = set()
    unfinished = []
    for c in all_courses:
        if c["code"] not in seen_codes and c["code"].upper() not in completed and (c["credits"] or 0) > 0:
            seen_codes.add(c["code"])
            unfinished.append(c)

    if req.filterType != "all":
        unfinished = [c for c in unfinished if c["type"] == req.filterType]

    career = await get_career_profile(p)

    def _slim_rec(c: dict) -> dict:
        return {
            "code":        c.get("code", ""),
            "name":        c.get("name", ""),
            "credits":     c.get("credits", 0),
            "type":        c.get("type", ""),
            "description": (c.get("description") or "")[:80],
            "pre_fit":     weighted_fit(c, career),
        }

    try:
        current_year = int(p.currentYS.split("-")[0]) if p.currentYS else 3
    except (IndexError, ValueError):
        current_year = 3

    for c in unfinished:
        c["_fit"] = weighted_fit(c, career)
    prereq_map = sanitize_prereq_map(
        config.query_prereq_map_bulk(deps.kuzu_conn, [c["code"] for c in unfinished])
    )
    scored = topsis_rank(unfinished, completed, current_year, prereq_map=prereq_map)

    context = {
        "job":             p.job,
        "industries":      p.industries or "",
        "major":           p.major,
        "track":           p.track,
        "career_keywords": career.get("keywords", [])[:8],
        "courses":         [_slim_rec(c) for c in scored[:40]],
    }

    courses_scored = await llm_json(
        RECOMMENDER_SYSTEM,
        f"다음 과목 목록에 직무 적합도를 부여하세요:\n{json.dumps(context, ensure_ascii=False, indent=2)}",
        max_tokens=4000,
    )

    if not isinstance(courses_scored, list):
        courses_scored = []

    if req.sortBy == "fit":
        courses_scored.sort(key=lambda x: -x.get("fit", 0))
    elif req.sortBy == "gpa":
        courses_scored.sort(key=lambda x: -x.get("gpa", 0))
    else:
        courses_scored.sort(key=lambda x: x.get("code", ""))

    top3 = courses_scored[:3]
    rationale_prompt = (
        f"직무: {p.job}\n"
        f"학과: {major_display(p)} / 경로: {p.track}\n"
        f"상위 3개 강의:\n" +
        "\n".join(f"- {c.get('code')} {c.get('name')}: {c.get('description','')}" for c in top3)
    )
    rationale_text = await llm(
        "당신은 서강대학교 진로 상담 AI입니다. 각 강의가 해당 직무에 왜 적합한지 한 단락씩 한국어로 설명하세요.",
        rationale_prompt,
        max_tokens=600,
    )

    return {
        "courses":        courses_scored,
        "total":          len(courses_scored),
        "top3_rationale": rationale_text,
        "job":            p.job,
    }
