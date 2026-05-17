"""
routers/rebalance.py — MODULE 02: 학기 동적 재설계

엔드포인트:
  POST /api/rebalance  Python delta 계산 → LLM 시나리오 서술

트리거 처리:
  - 학점 미달 (F/D): 해당 과목 미이수로 분류, 재수강 우선 배치
  - 전공 변경:       새 전공 과목 풀로 교체
  - 휴학:            남은 학기 수 재산정
  - 신규 활동:       activity 정규화 후 맥락 반영
"""

from fastapi import APIRouter

import config
import deps
from models import RebalanceRequest
from utils.common import completed_set, remaining_semesters, dept_iri_from_profile
from utils.graduation import graduation_req
from utils.activity import normalize_activities
from utils.llm import llm_json

router = APIRouter()

# ── GPA 변환표 ────────────────────────────────────────────────────
_GRADE_POINTS: dict[str, float] = {
    "A+": 4.5, "A0": 4.0, "A": 4.0,
    "B+": 3.5, "B0": 3.0, "B": 3.0,
    "C+": 2.5, "C0": 2.0, "C": 2.0,
    "D+": 1.5, "D0": 1.0, "D": 1.0,
    "F":  0.0, "P":  None,             # P는 GPA 산정 제외
}

# F 또는 D0 이하 → 학점 미달 (재수강 권고)
_FAIL_GRADES = {"F", "D+", "D0", "D"}


def _parse_grades(new_grades) -> tuple[set[str], list[dict], float | None]:
    """
    newGrades 파싱.
    반환: (failed_codes, grade_rows, avg_gpa_this_sem)
    """
    failed_codes: set[str] = set()
    grade_rows: list[dict] = []
    gpa_sum, gpa_cnt = 0.0, 0

    for entry in new_grades:
        code  = entry.code.upper()
        grade = entry.grade.strip().upper()
        pts   = _GRADE_POINTS.get(grade)

        is_fail = grade in _FAIL_GRADES
        if is_fail:
            failed_codes.add(code)

        grade_rows.append({
            "code":    code,
            "grade":   grade,
            "points":  pts,
            "is_fail": is_fail,
        })

        if pts is not None:
            gpa_sum += pts
            gpa_cnt += 1

    avg_gpa = round(gpa_sum / gpa_cnt, 2) if gpa_cnt else None
    return failed_codes, grade_rows, avg_gpa


REBALANCE_SYSTEM = """당신은 서강대학교 학기 재설계 AI입니다.
Python이 계산한 변경 데이터(delta)를 받아 자연어 시나리오 서술만 작성합니다.

트리거별 시나리오 작성 방식:
- 학점 미달(F/D): 해당 과목 재수강을 우선 배치하고, 그로 인한 다음 학기 조정 서술
- 전공 변경: 새 전공 필수과목 중심으로 잔여 계획 재배치 서술
- 휴학: 늘어난 학기를 활용한 부하 분산 전략 서술
- 신규 활동: 학기 부하 증가분 반영 후 과목 수 조정 서술

출력 JSON 구조:
{
  "trajectory": [
    {"period": "~현재", "title": "현재 이수 궤적", "detail": "한두 줄 서술"}
  ],
  "scenarios": [
    {
      "title": "시나리오 제목 (트리거 명시)",
      "trigger": "학점미달|전공변경|휴학|신규활동|복합",
      "before_label": "재설계 전",
      "before_courses": ["과목명1", "과목명2"],
      "after_label": "재설계 후",
      "after_courses": ["과목명1", "과목명2"],
      "reason": "변경 이유 한 줄"
    }
  ],
  "triggers": "이번 재설계를 촉발한 트리거 목록과 설명"
}"""


@router.post("/api/rebalance")
async def rebalance(req: RebalanceRequest):
    """MODULE 02: Python delta 계산 → LLM 시나리오 서술"""
    p = req.profile

    # ── 1. 성적 파싱: 학점 미달 과목 분리 ────────────────────────
    failed_codes, grade_rows, sem_gpa = _parse_grades(req.newGrades)

    # 이수 완료 = 신규이수 중 F/D 아닌 것
    newly_passed = [
        c.upper() for c in req.newCompletedCodes
        if c.upper() not in failed_codes
    ]
    all_completed = completed_set(p)
    # 학점 미달 과목은 이수 집합에서도 제거
    all_completed -= failed_codes

    # ── 2. 전공 변경 처리 ─────────────────────────────────────────
    effective_major   = req.majorChange.strip() or p.major
    major_changed     = bool(req.majorChange.strip())
    if major_changed:
        # 새 전공의 dept_iri 조회
        new_dept = config.query_dept_info(deps.kuzu_conn, effective_major)
        dept_iri  = new_dept["iri"] if new_dept else dept_iri_from_profile(p)
        print(f"[REBALANCE] 전공 변경: {p.major} → {effective_major}")
    else:
        dept_iri = dept_iri_from_profile(p)

    # ── 3. 휴학 반영: 남은 학기 재산정 ───────────────────────────
    remaining_sems = remaining_semesters(p)
    sems_left      = len(remaining_sems) + req.leaveOfAbsence
    if req.leaveOfAbsence:
        print(f"[REBALANCE] 휴학 {req.leaveOfAbsence}학기 추가 → 총 {sems_left}학기")

    # ── 4. 잔여 과목 계산 ─────────────────────────────────────────
    grad        = graduation_req(p)
    all_courses = config.query_dept_courses(deps.kuzu_conn, dept_iri) if dept_iri else []

    remaining_courses = [
        c for c in all_courses
        if c["code"].upper() not in all_completed and (c["credits"] or 0) > 0
    ]
    required_remaining = [c for c in remaining_courses if c.get("type") == "RequiredCourse"]

    # 재수강 필요 과목 (학점 미달 + DB에 존재하는 경우)
    retake_needed = [
        c for c in all_courses
        if c["code"].upper() in failed_codes
    ]

    credits_remaining = max(0, grad.get("totalCredits", 130) - p.credits)
    avg_needed        = round(credits_remaining / sems_left, 1) if sems_left else 0

    # ── 5. 신규 활동 정규화 ───────────────────────────────────────
    act = await normalize_activities(req.newActivities or "")
    act_summary = act.get("category_summary", "없음")

    # ── 6. 트리거 목록 구성 ───────────────────────────────────────
    triggers_detected: list[str] = []
    if failed_codes:
        triggers_detected.append(
            f"학점미달: {', '.join(failed_codes)} — 재수강 필요"
        )
    if major_changed:
        triggers_detected.append(f"전공변경: {p.major} → {effective_major}")
    if req.leaveOfAbsence:
        triggers_detected.append(f"휴학 {req.leaveOfAbsence}학기 추가")
    if req.newActivities.strip():
        triggers_detected.append(f"신규활동: {act_summary}")

    # ── 7. Delta 구성 ──────────────────────────────────────────────
    delta = {
        "triggers":              triggers_detected or ["변경사항 없음"],
        "newly_passed":          newly_passed,
        "failed_courses":        [{"code": c["code"], "name": c.get("name", "")} for c in retake_needed],
        "grade_summary":         grade_rows,
        "sem_gpa":               sem_gpa,
        "current_gpa":           req.currentGpa or None,
        "major_changed":         major_changed,
        "effective_major":       effective_major,
        "leave_added":           req.leaveOfAbsence,
        "new_activities":        act_summary,
        "credits_remaining":     credits_remaining,
        "semesters_left":        sems_left,
        "avg_credits_per_sem":   avg_needed,
        "required_remaining":    [{"code": c["code"], "name": c["name"]} for c in required_remaining[:10]],
        "retake_priority":       [{"code": c["code"], "name": c.get("name", "")} for c in retake_needed[:5]],
        "total_remaining_count": len(remaining_courses),
    }

    # ── 8. LLM: 시나리오 서술 ─────────────────────────────────────
    trigger_str = " / ".join(triggers_detected) if triggers_detected else "일반 업데이트"
    context_text = (
        f"학생: {effective_major} {p.track} / 목표직무: {p.job}\n"
        f"트리거: {trigger_str}\n"
        f"이번 학기 이수(통과): {', '.join(newly_passed) or '없음'}\n"
        f"학점 미달(재수강 필요): {', '.join(failed_codes) or '없음'}\n"
        f"이번 학기 GPA: {sem_gpa if sem_gpa is not None else '미입력'} "
        f"/ 누적 GPA: {req.currentGpa or '미입력'}\n"
        f"전공 변경: {'있음 (' + p.major + ' → ' + effective_major + ')' if major_changed else '없음'}\n"
        f"휴학 추가: {req.leaveOfAbsence}학기\n"
        f"신규 활동: {act_summary}\n"
        f"남은 학점: {credits_remaining} / 남은 학기: {sems_left} "
        f"(학기당 평균 {avg_needed}학점 필요)\n"
        f"미이수 전공필수: {', '.join(c['name'] for c in required_remaining[:5]) or '없음'}\n"
    )

    result = await llm_json(
        REBALANCE_SYSTEM,
        f"아래 변경 현황을 바탕으로 재설계 시나리오를 작성하세요:\n{context_text}",
        max_tokens=1500,
    )

    if not isinstance(result, dict):
        result = {}

    result["delta_stats"] = delta
    return result
