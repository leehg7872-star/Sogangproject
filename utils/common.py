"""
utils/common.py — 여러 라우터에서 공유하는 헬퍼 함수
"""

import config
import deps
from models import StudentProfile


def major_display(profile: StudentProfile) -> str:
    parts = [p for p in [profile.major, profile.secondaryMajor, profile.thirdMajor] if p]
    return " + ".join(parts) if parts else ""


def completed_set(profile: StudentProfile) -> set[str]:
    return set(
        c.strip().upper()
        for c in profile.completed.split(",")
        if c.strip()
    )


def remaining_semesters(profile: StudentProfile) -> list[dict]:
    y, s = map(int, profile.currentYS.split("-"))
    sems = []
    for yr in range(y, 5):
        for sm in range(s if yr == y else 1, 3):
            sems.append({"year": yr, "sem": sm, "label": f"{yr}학년 {sm}학기"})
    return sems


def dept_iri_from_profile(profile: StudentProfile) -> str:
    if profile.deptIri:
        return profile.deptIri
    dept = config.query_dept_info(deps.kuzu_conn, profile.major)
    return dept["iri"] if dept else ""


def effective_completed(completed: set[str], dept_iri: str) -> set[str]:
    """코드쉐어·대체인정 반영한 실질 이수 집합"""
    effective = set(completed)
    seen_prefixes: set[str] = set()
    for code in list(completed):
        prefix = code[:3]
        if prefix in seen_prefixes:
            continue
        seen_prefixes.add(prefix)
        shares = config.query_code_shares(deps.kuzu_conn, prefix)
        for pair in shares:
            a, b = pair["a"].upper(), pair["b"].upper()
            if a in completed:
                effective.add(b)
            if b in completed:
                effective.add(a)
    return effective
