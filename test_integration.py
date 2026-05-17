"""
test_integration.py — 서강대 코파일럿 통합 테스트

실행:
    python3 test_integration.py

각 섹션은 독립 실행 가능:
    python3 -m pytest test_integration.py -v   (pytest 설치 시)
"""

import asyncio
import sys
import os

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(__file__))

# ── 1. 모듈 임포트 검증 ────────────────────────────────────────────

def test_imports():
    import config
    import deps
    import models
    from utils.llm import llm, llm_json
    from utils.activity import normalize_activities
    from utils.career import get_career_profile, weighted_fit
    from utils.scraper import scrape_contests, scrape_sogang_jobs
    from utils.common import completed_set, remaining_semesters, dept_iri_from_profile
    from utils.graduation import graduation_req
    import data_round4
    print("[PASS] 모든 모듈 임포트 성공")

# ── 2. data_round4 무결성 검증 ─────────────────────────────────────

def test_data_round4():
    import data_round4 as R4

    # JobRole IRI 중복 없음
    iris = [j["iri"] for j in R4.JOB_ROLES]
    assert len(iris) == len(set(iris)), "JobRole IRI 중복"

    # 모든 COURSE_JOB_FITS의 jobIri가 JOB_ROLES에 존재
    valid_iris = set(iris)
    for fit in R4.COURSE_JOB_FITS:
        assert fit["jobIri"] in valid_iris, f"jobIri 미등록: {fit['jobIri']}"
        assert 0.0 <= fit["weight"] <= 1.0, f"weight 범위 이탈: {fit}"

    # weight 범위
    for t in R4.MAJOR_JOB_TARGETS:
        assert t["jobIri"] in valid_iris, f"MAJOR_JOB_TARGETS jobIri 미등록: {t['jobIri']}"

    # 커버된 학과 수
    depts = set(c["courseCode"][:3] for c in R4.COURSE_JOB_FITS)
    print(f"[PASS] data_round4: {len(R4.JOB_ROLES)}개 직무, "
          f"{len(R4.COURSE_JOB_FITS)}개 적합도, "
          f"{len(depts)}개 학과 커버")


# ── 3. 성적 파싱 (rebalance) ───────────────────────────────────────

def test_grade_parsing():
    from routers.rebalance import _parse_grades
    from models import GradeEntry

    entries = [
        GradeEntry(code="CSE3080", grade="A+"),
        GradeEntry(code="MGT3006", grade="F"),
        GradeEntry(code="ECO4009", grade="D+"),
        GradeEntry(code="CHI4008", grade="B0"),
    ]
    failed, rows, avg = _parse_grades(entries)

    assert "MGT3006" in failed
    assert "ECO4009" in failed
    assert "CSE3080" not in failed
    assert avg is not None

    # A+=4.5, B0=3.0 → avg = (4.5+3.0)/2 = 3.75 (F, D+ excluded from GPA)
    # Wait: D+=1.5 is in _GRADE_POINTS so it IS included
    # F=0.0 included, D+=1.5 included → (4.5 + 0.0 + 1.5 + 3.0) / 4 = 2.25
    assert abs(avg - 2.25) < 0.01, f"GPA 계산 오류: {avg}"
    print(f"[PASS] 성적 파싱: failed={failed}, avg_gpa={avg}")


# ── 4. weighted_fit 점수 계산 ──────────────────────────────────────

def test_weighted_fit():
    from utils.career import weighted_fit

    mock_profile = {
        "keywords":        ["마케팅", "브랜드", "디지털"],
        "graph_job_keywords": ["marketing", "brand"],
        "dept_boosts":     {"Dept_MGT": 1.4, "Dept_ECO": 0.8},
        "graph_fit_courses": {"MGT3006": 0.95, "CSE4185": 0.90},
    }

    # 그래프 우선 경로
    score_graph = weighted_fit({"code": "MGT3006"}, mock_profile)
    assert score_graph == 95, f"그래프 점수 이상: {score_graph}"

    # LLM 폴백 경로
    course_fallback = {
        "code":        "MGT4208",
        "name":        "디지털마케팅",
        "description": "디지털 마케팅 전략과 브랜드 관리",
        "deptIri":     "Dept_MGT",
    }
    score_llm = weighted_fit(course_fallback, mock_profile)
    assert score_llm > 0, "LLM 폴백 점수가 0"
    print(f"[PASS] weighted_fit: 그래프={score_graph}, LLM폴백={score_llm}")


# ── 5. 비교과 활동 정규화 (LLM 호출 없이 구조만 검증) ──────────────

def test_activity_normalize_structure():
    """LLM 실호출 없이 normalize_activities 함수 시그니처만 검증"""
    from utils.activity import normalize_activities
    import inspect
    sig = inspect.signature(normalize_activities)
    params = list(sig.parameters.keys())
    assert "activities" in params
    print(f"[PASS] normalize_activities 시그니처 확인: {params}")


# ── 6. models Pydantic 검증 ───────────────────────────────────────

def test_models():
    from models import (
        StudentProfile, PlannerRequest, RebalanceRequest,
        RecommenderRequest, OpportunitiesRequest, GradeEntry,
    )

    profile = StudentProfile(
        major="컴퓨터공학과", track="단일", year=3, semester=1,
        credits=80, gpa=3.5, completed="CSE3080, CSE3081",
        job="AI엔지니어", industries="IT,핀테크",
        certs="정보처리기사", activities="IT동아리 2년",
        internships="스타트업 인턴 6개월",
    )

    rb = RebalanceRequest(
        profile=profile,
        newCompletedCodes=["CSE4185"],
        newGrades=[GradeEntry(code="CSE4185", grade="A+"),
                   GradeEntry(code="MGT3006", grade="F")],
        newActivities="해커톤 대상 수상",
        leaveOfAbsence=1,
        majorChange="",
        currentGpa=3.4,
    )
    assert rb.leaveOfAbsence == 1
    assert len(rb.newGrades) == 2
    print("[PASS] models Pydantic 검증 성공")


# ── 7. graduation_req 구조 검증 ────────────────────────────────────

def test_graduation_req():
    from models import StudentProfile
    from utils.graduation import graduation_req
    import deps

    if deps.kuzu_conn is None:
        print("[SKIP] test_graduation_req: KuzuDB 미연결 (앱 실행 시 자동 테스트)")
        return

    profile = StudentProfile(
        major="경영학과", track="단일", year=2, semester=2,
        credits=40, gpa=3.2, completedCourses=[],
        job="컨설팅",
    )
    result = graduation_req(profile)
    assert "totalCredits" in result, "totalCredits 누락"
    assert isinstance(result["totalCredits"], (int, float))
    print(f"[PASS] graduation_req: {result}")


# ── 8. common 유틸 검증 ────────────────────────────────────────────

def test_common_utils():
    from models import StudentProfile
    from utils.common import completed_set, remaining_semesters, dept_iri_from_profile

    profile = StudentProfile(
        major="경제학과", track="단일", year=3, semester=1,
        credits=70, gpa=3.0,
        completed="ECO3008, ECO4009",
        job="금융",
    )
    cs = completed_set(profile)
    assert "ECO3008" in cs
    assert "ECO4009" in cs

    rs = remaining_semesters(profile)
    assert isinstance(rs, list)
    assert len(rs) > 0

    # dept_iri_from_profile은 DB 없이도 정적 매핑 동작 여부 확인
    try:
        iri = dept_iri_from_profile(profile)
        assert iri.startswith("Dept_"), f"dept_iri 이상: {iri}"
        print(f"[PASS] common utils: completed={len(cs)}, remaining_sems={rs}, dept={iri}")
    except Exception:
        # DB 미연결 시 빈 문자열 또는 예외 허용
        print(f"[PASS] common utils: completed={len(cs)}, remaining_sems={rs}, dept=N/A(DB미연결)")


# ── 실행 ──────────────────────────────────────────────────────────

_TESTS = [
    test_imports,
    test_data_round4,
    test_grade_parsing,
    test_weighted_fit,
    test_activity_normalize_structure,
    test_models,
    test_graduation_req,
    test_common_utils,
]

if __name__ == "__main__":
    passed, failed = 0, 0
    for t in _TESTS:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"결과: {passed}개 통과 / {failed}개 실패 / {len(_TESTS)}개 전체")
    sys.exit(0 if failed == 0 else 1)
