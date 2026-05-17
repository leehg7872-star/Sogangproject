"""
routers/planner.py — MODULE 01: 졸업 역산 플래너

엔드포인트:
  POST /api/planner  강화된 Python 추론(위상정렬·TOPSIS·스케줄러) + LLM 요약
"""

from fastapi import APIRouter

import config
import deps
from models import PlannerRequest
from utils.common import (
    completed_set, remaining_semesters,
    dept_iri_from_profile, effective_completed,
)
from utils.graduation import (
    graduation_req, calc_graduation_scenario, graduation_feasibility,
)
from utils.career import get_career_profile, weighted_fit
from utils.inference import (
    sanitize_prereq_map, topological_sort,
    schedule_with_backtracking, topsis_rank,
)
from utils.llm import llm_json

router = APIRouter()

LLM_SYSTEM = (
    "서강대 학사 플래너 AI.\n"
    "Python이 계산한 3가지 플랜의 트레이드오프를 한 줄로 서술하고 점수를 부여하세요.\n\n"
    "플랜 의미:\n"
    "  A(최소요건 충족형): 각 전공 졸업필수 학점을 정확히 채우고 여백을 선택과목으로 효율적 활용\n"
    "  B(전문성 강화형): 희망 직무 관련 과목 집중 + 선수과목 이수 흐름 안정 보장\n"
    "  C(융합 강화형): 두 전공의 시너지를 극대화하는 균형 배분\n\n"
    'JSON 배열: [{"id":"A","summary":"트레이드오프 한 줄","fit":85,"gpa":3.7,"recommended":true},'
    ' {"id":"B",...}, {"id":"C",...}]\n'
    "recommended는 학생의 직무 목표와 졸업 상황을 고려해 1개만 true."
)


@router.post("/api/planner")
async def planner(req: PlannerRequest):
    """MODULE 01: 강화된 Python 룰엔진 + LLM 요약"""
    p              = req.profile
    dept_iri       = dept_iri_from_profile(p)
    completed_raw  = completed_set(p)
    grad           = graduation_req(p)
    remaining_sems = remaining_semesters(p)

    # ── 1. 코드쉐어/대체인정 반영 실질 이수 집합 ───────────────
    completed       = effective_completed(completed_raw, dept_iri)
    newly_effective = completed - completed_raw
    if newly_effective:
        print(f"[PLANNER] 코드쉐어 추가 인정: {newly_effective}")

    # ── 2. KUZU: 미이수 과목 수집 ──────────────────────────────
    primary_courses = config.query_dept_courses(deps.kuzu_conn, dept_iri) if dept_iri else []
    if not primary_courses:
        print(f"[PLANNER] ⚠ 본전공 과목 없음 — dept_iri='{dept_iri}', major='{p.major}'")
    for c in primary_courses:
        c["major_tag"]   = "primary"
        c["major_label"] = p.major

    extra_courses: list[dict]    = []
    extra_grad_reqs: list[dict] = []
    for tag, extra_name in [("secondary", p.secondaryMajor), ("third", p.thirdMajor)]:
        if not extra_name:
            continue
        extra_dept = config.query_dept_info(deps.kuzu_conn, extra_name)
        if not extra_dept:
            continue
        courses = config.query_dept_courses(deps.kuzu_conn, extra_dept["iri"])
        for c in courses:
            c["major_tag"]   = tag
            c["major_label"] = extra_name
        extra_courses += courses

        cj = extra_dept.get("credits", {})
        req_credits = (
            cj.get("다전공_타전공주전공_전공학점")
            or cj.get("다전공_전공학점")
            or 36
        )
        extra_grad_reqs.append({
            "major": extra_name, "tag": tag, "majorCredits": req_credits
        })
        print(f"[PLANNER] {tag} 전공 '{extra_name}': {len(courses)}개 과목, 전공학점 {req_credits}학점 필요")

    all_courses = primary_courses + extra_courses
    unfinished  = [
        c for c in all_courses
        if c["code"].upper() not in completed and (c["credits"] or 0) > 0
    ]

    # ── 3. Career Profile 기반 fit 점수 계산 ────────────────────
    career = await get_career_profile(p)
    for c in unfinished:
        c["_fit"] = weighted_fit(c, career)

    # ── 4. 추론 엔진: 정제 → 위상정렬 → TOPSIS ─────────────────
    all_codes      = [c["code"] for c in unfinished]
    prereq_map     = sanitize_prereq_map(
        config.query_prereq_map_bulk(deps.kuzu_conn, all_codes)
    )
    topo_sorted    = topological_sort(unfinished, prereq_map, completed)

    try:
        current_year = int(p.currentYS.split("-")[0]) if p.currentYS else 3
    except (IndexError, ValueError):
        current_year = 3

    topo_topsis = topsis_rank(topo_sorted, completed, current_year, prereq_map=prereq_map)

    # ── 4d. 졸업요건 세부 추적 ─────────────────────────────────
    major_credits_done = sum(
        c.get("credits") or 0
        for c in all_courses
        if c["code"].upper() in completed
        and c.get("type") in ("RequiredCourse", "ElectiveCourse")
    )
    feasibility = graduation_feasibility(
        credits_done       = p.credits,
        credits_req        = grad.get("totalCredits", 130),
        major_credits_done = major_credits_done,
        major_credits_req  = grad.get("majorCredits", 36),
        remaining_sems     = len(remaining_sems),
    )

    # ── 5. 졸업 역산 + 3가지 전략 풀 구성 ───────────────────────
    grad_scenario = calc_graduation_scenario(
        p, all_courses, completed, grad, extra_grad_reqs
    )
    pri_sc = grad_scenario["primary"]
    sec_sc = grad_scenario.get("secondary")

    pri_req_uf = [c for c in topo_topsis
                  if c.get("major_tag") == "primary" and c.get("type") == "RequiredCourse"]
    pri_elc_uf = [c for c in topo_topsis
                  if c.get("major_tag") == "primary" and c.get("type") != "RequiredCourse"]
    sec_req_uf = [c for c in topo_topsis
                  if c.get("major_tag") != "primary" and c.get("type") == "RequiredCourse"]
    sec_elc_uf = [c for c in topo_topsis
                  if c.get("major_tag") != "primary" and c.get("type") != "RequiredCourse"]

    # 안정적 이수 점수: 선수충족도·체인·필수·학년 경향 기반
    in_chain: set[str] = set()
    for _c in topo_topsis:
        for _prereq in prereq_map.get(_c["code"], set()):
            in_chain.add(_prereq)

    def _stable_score(c: dict) -> float:
        code    = c["code"]
        prereqs = prereq_map.get(code, set())
        unmet   = prereqs - completed
        if not prereqs:   prereq_score = 50
        elif not unmet:   prereq_score = 50
        else:             prereq_score = max(0, 50 - len(unmet) * 15)
        chain_score  = 15 if code in in_chain else 0
        req_score    = 20 if c.get("type") == "RequiredCourse" else 0
        yr_min = c.get("yearMin") or 1
        if yr_min <= current_year:
            yr_score = max(0, 10 - (current_year - yr_min) * 3)
        else:
            yr_score = max(-5, -(yr_min - current_year) * 2)
        return prereq_score + chain_score + req_score + yr_score + c.get("_topsis", 50) * 0.2

    def _fusion_score(c: dict) -> float:
        gpa       = min(c.get("avgGpa") or 0.0, 4.5) / 4.5
        fit       = c.get("_fit", 50) / 100.0
        req       = 0.3 if c.get("type") == "RequiredCourse" else 0.0
        sec_bonus = 0.2 if c.get("major_tag") != "primary" and sec_sc is not None else 0.0
        return gpa * 0.35 + fit * 0.30 + req + sec_bonus

    pri_remain = pri_sc["remain"]
    sec_remain = sec_sc["remain"] if sec_sc else 0
    print(f"[PLAN] 본전공 잔여: {pri_remain}학점, 제2전공 잔여: {sec_remain}학점")
    print(f"[PLAN] 남은학기 수용: {len(remaining_sems)}학기×18={len(remaining_sems)*18}학점")

    # [A] 최소 이수형
    strategy_a = (
        sorted(pri_req_uf + sec_req_uf, key=lambda x: -_stable_score(x)) +
        sorted(pri_elc_uf + sec_elc_uf, key=lambda x: -_stable_score(x))
    )

    # [B] 전문성 강화형
    strategy_b = sorted(
        pri_req_uf + pri_elc_uf + sec_req_uf + sec_elc_uf,
        key=lambda x: -x.get("_topsis", 0)
    )

    # [C] 융합 강화형
    def _interleave_ratio(pool_a: list, pool_b: list) -> list:
        if not pool_b:
            return pool_a
        ratio  = pri_remain / max(1, sec_remain)
        result, ia, ib = [], 0, 0
        while ia < len(pool_a) or ib < len(pool_b):
            for _ in range(max(1, round(ratio))):
                if ia < len(pool_a): result.append(pool_a[ia]); ia += 1
            if ib < len(pool_b): result.append(pool_b[ib]); ib += 1
        return result

    c_pri      = sorted(pri_req_uf + pri_elc_uf, key=lambda x: -_fusion_score(x))
    c_sec      = sorted(sec_req_uf + sec_elc_uf, key=lambda x: -_fusion_score(x))
    strategy_c = _interleave_ratio(c_pri, c_sec)

    strategies   = [
        ("A", "최소 이수형",   strategy_a),
        ("B", "전문성 강화형", strategy_b),
        ("C", "융합 강화형",   strategy_c),
    ]
    min_major_cr: dict[str, int] | None = None
    if sec_sc:
        min_major_cr = {
            p.major:         pri_sc["remain"],
            sec_sc["label"]: sec_sc["remain"],
        }

    # ── 스케줄러 실행 ───────────────────────────────────────────
    scheduled_plans = []
    for plan_id, plan_label, course_pool in strategies:
        sems = schedule_with_backtracking(
            course_pool, remaining_sems, completed,
            max_credits=18,
            prereq_map=prereq_map,
            strict_prereq=(plan_id == "B"),
            min_major_credits=min_major_cr if plan_id in ("A", "C") else None,
        )
        req_count = sum(1 for s in sems for c in s["courses"] if c["type"] == "RequiredCourse")
        avg_fit   = round(
            sum(c.get("fit", 50) for s in sems for c in s["courses"])
            / max(1, sum(len(s["courses"]) for s in sems)), 1
        )
        major_dist: dict[str, int] = {}
        for s in sems:
            for c in s["courses"]:
                label = c.get("major_label", p.major)
                major_dist[label] = major_dist.get(label, 0) + (c.get("credits") or 3)
        scheduled_plans.append({
            "id":            plan_id,
            "label":         plan_label,
            "semesters":     sems,
            "total_courses": sum(len(s["courses"]) for s in sems),
            "total_credits": sum(s["totalCredits"] for s in sems),
            "req_count":     req_count,
            "avg_fit":       avg_fit,
            "major_dist":    major_dist,
        })

    # ── 6. LLM: 플랜 요약 + 점수 ───────────────────────────────
    major_info = f"{p.major}(본전공)"
    if p.secondaryMajor: major_info += f" + {p.secondaryMajor}(제2전공)"
    if p.thirdMajor:     major_info += f" + {p.thirdMajor}(제3전공)"

    plans_info = "\n".join(
        f'{pl["id"]}안({pl["label"]}): 전공필수 {pl["req_count"]}개, '
        f'총 {pl["total_courses"]}개/{pl["total_credits"]}학점, '
        f'직무적합도 {pl["avg_fit"]}점, '
        f'전공별학점배분={pl["major_dist"]}'
        for pl in scheduled_plans
    )
    pri_info = (f"{pri_sc['label']} 전공 {pri_sc['remain']}학점 미이수"
                if pri_sc['remain'] > 0 else f"{pri_sc['label']} 전공 충족")
    sec_info = (f" | {sec_sc['label']} 다전공 {sec_sc['remain']}학점 미이수"
                if sec_sc and sec_sc['remain'] > 0 else "")

    llm_prompt = (
        f"직무: {p.job} | 전공: {major_info}\n"
        f"요람 이수요건: 총 {grad_scenario['total_req']}학점 "
        f"(현재 {grad_scenario['total_done']}학점 이수, 잔여 {grad_scenario['total_remain']}학점)\n"
        f"전공별 현황: {pri_info}{sec_info}\n"
        f"남은 학기: {len(remaining_sems)}개\n\n"
        + plans_info
    )
    llm_raw  = await llm_json(LLM_SYSTEM, llm_prompt, max_tokens=400)
    summaries: dict = {}
    if isinstance(llm_raw, list):
        for item in llm_raw:
            if isinstance(item, dict) and "id" in item:
                summaries[item["id"]] = item

    # ── 7. 최종 응답 병합 ──────────────────────────────────────
    final_plans = []
    for i, pl in enumerate(scheduled_plans):
        meta = summaries.get(pl["id"], {})
        final_plans.append({
            "id":          pl["id"],
            "label":       pl["label"],
            "recommended": meta.get("recommended", i == 0),
            "fit":         meta.get("fit", pl["avg_fit"]),
            "gpa":         meta.get("gpa", 3.5),
            "summary":     meta.get("summary", f"{pl['label']} 기반 계획"),
            "semesters":   pl["semesters"],
        })

    return {
        "plans":       final_plans,
        "feasibility": feasibility,
        "scenario":    grad_scenario,
        "stats": {
            "credits_done":       p.credits,
            "credits_remaining":  grad_scenario["total_remain"],
            "primary_remain":     pri_sc["remain"],
            "secondary_remain":   sec_sc["remain"] if sec_sc else 0,
            "free_remain":        grad_scenario["free_remain"],
            "major_credits_req":  grad.get("majorCredits", 36),
            "req_min_credits":    grad.get("reqMinCredits"),
            "elec_min_credits":   grad.get("elecMinCredits"),
            "semesters_left":     len(remaining_sems),
            "courses_left":       len(unfinished),
            "avg_per_sem_needed": feasibility["avg_per_sem"],
            "category_breakdown": grad_scenario.get("category_breakdown", {}),
        },
    }
