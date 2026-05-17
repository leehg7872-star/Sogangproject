"""
utils/graduation.py — 졸업요건 계산 유틸리티
"""

from collections import defaultdict
import config
import deps
from models import StudentProfile


# 출처: 서강대학교 2025학년도 요람 공통교양 이수요건
GRAD_CATEGORY_RULES: dict[str, dict] = {
    "공통필수": {
        "min_credits": 11,
        "label":       "공통필수교과",
        "note":        "서강인성·글쓰기·글로벌언어 포함 11학점 필수",
    },
    "공통선택": {
        "min_credits": 12,
        "label":       "공통선택교과",
        "note":        "인간과신앙·사상·사회·과학AI 4개 영역, 12학점 이상",
    },
    "전공필수": {
        "min_credits": None,
        "label":       "전공필수교과",
        "note":        "학과 요람 보강 후 reqMinCredits 활성화",
    },
    "전공선택": {
        "min_credits": None,
        "label":       "전공선택교과",
        "note":        "학과 요람 보강 후 elecMinCredits 활성화",
    },
    "전공입문": {
        "min_credits": None,
        "label":       "전공입문교과",
        "note":        "전공 기초과목, countsTowardMajorCredits 여부 학과별 확인 필요",
    },
}


def graduation_req(profile: StudentProfile) -> dict:
    """전공 이수 시나리오 → creditsJson 키 → 졸업요건 반환"""
    from data_round4_scenario import resolve_scenario_key, ENROLL_SINGLE, ENROLL_MULTI

    primary = None
    if hasattr(profile, 'majors') and profile.majors:
        primary = next((m for m in profile.majors if m.order == 1), profile.majors[0])

    dept_iri = ""
    if primary and primary.deptIri:
        dept_iri = primary.deptIri
    elif hasattr(profile, 'deptIri') and profile.deptIri:
        dept_iri = profile.deptIri
    else:
        dept = config.query_dept_info(deps.kuzu_conn, profile.major)
        dept_iri = dept.get("iri", "") if dept else ""

    if primary:
        enroll_type  = primary.enrollType or (ENROLL_MULTI if profile.secondaryMajor else ENROLL_SINGLE)
        role         = primary.role or None
        track        = primary.track or None
        special_cond = primary.specialCond or None
    else:
        has_secondary = bool(profile.secondaryMajor or profile.thirdMajor)
        enroll_type   = ENROLL_MULTI if has_secondary else ENROLL_SINGLE
        role          = None
        track         = profile.track or None
        special_cond  = None

    if profile.majorIri:
        result = config.query_major_credits(deps.kuzu_conn, profile.majorIri)
        if result:
            return result

    dept_obj = config.query_dept_info(deps.kuzu_conn, profile.major) if not dept_iri else None
    if dept_obj and not dept_iri:
        dept_iri = dept_obj.get("iri", "")

    scenario_key = resolve_scenario_key(dept_iri, enroll_type, role, track, special_cond)

    dept_data = config.query_dept_info(deps.kuzu_conn, profile.major)
    if dept_data and dept_data.get("credits"):
        cj = dept_data["credits"]
        if scenario_key:
            total_key = scenario_key + "_총학점"
            major_key = scenario_key + "_전공학점"
            req_key   = scenario_key + "_필수_최소학점"   # 요람 보강 후 채워짐
            elec_key  = scenario_key + "_선택_최소학점"   # 요람 보강 후 채워짐
            if total_key in cj and major_key in cj:
                return {
                    "totalCredits":   cj[total_key],
                    "majorCredits":   cj[major_key],
                    "reqMinCredits":  cj.get(req_key),
                    "elecMinCredits": cj.get(elec_key),
                    "variant":        scenario_key,
                }
        candidates = {k: v for k, v in cj.items()
                      if "전공학점" in k and "다전공" not in k and "교직" not in k
                      and "필수" not in k and "선택" not in k}
        if candidates:
            best = max(candidates, key=lambda k: candidates[k])
            return {
                "totalCredits":   cj.get(best.replace("전공학점", "총학점"), 130),
                "majorCredits":   candidates[best],
                "reqMinCredits":  cj.get(best.replace("전공학점", "필수_최소학점")),
                "elecMinCredits": cj.get(best.replace("전공학점", "선택_최소학점")),
                "variant":        best.replace("_전공학점", "") + "(폴백)",
            }

    return {"totalCredits": 130, "majorCredits": 36,
            "reqMinCredits": None, "elecMinCredits": None, "variant": "기본값"}


def category_credits_done(all_courses: list[dict], completed: set[str]) -> dict[str, int]:
    code_map: dict[str, dict] = {c["code"].upper(): c for c in all_courses}
    totals: dict[str, int] = defaultdict(int)
    for code in completed:
        course = code_map.get(code.upper())
        if course:
            cat = course.get("graduationCategory") or "기타"
            totals[cat] += course.get("credits") or 0
    return dict(totals)


def category_remain(
    category_done: dict[str, int],
    grad: dict,
    grad_category_rules: dict | None = None,
) -> dict[str, dict]:
    rules = grad_category_rules or GRAD_CATEGORY_RULES
    result: dict[str, dict] = {}
    for cat, rule in rules.items():
        if cat == "전공필수":
            min_cr = grad.get("reqMinCredits")
        elif cat == "전공선택":
            min_cr = grad.get("elecMinCredits")
        else:
            min_cr = rule.get("min_credits")

        done   = category_done.get(cat, 0)
        remain = max(0, (min_cr or 0) - done) if min_cr is not None else None
        ok     = (done >= min_cr) if min_cr is not None else None

        result[cat] = {
            "label":  rule["label"],
            "done":   done,
            "min":    min_cr,
            "remain": remain,
            "ok":     ok,
            "note":   rule.get("note", ""),
        }
    return result


def calc_graduation_scenario(
    profile: StudentProfile,
    all_courses: list[dict],
    completed: set[str],
    grad: dict,
    extra_grad_reqs: list[dict],
) -> dict:
    total_req    = grad.get("totalCredits", 130)
    total_done   = profile.credits
    total_remain = max(0, total_req - total_done)

    code_to_tag: dict[str, str] = {}
    for c in all_courses:
        code_to_tag[c["code"].upper()] = c.get("major_tag", "primary")

    def _done_credits_for_tag(tag: str) -> int:
        return sum(
            next((c.get("credits") or 3 for c in all_courses if c["code"].upper() == code), 3)
            for code in completed
            if code_to_tag.get(code, "primary") == tag
        )

    primary_done    = _done_credits_for_tag("primary")
    primary_req     = grad.get("majorCredits", 36)
    primary_remain  = max(0, primary_req - primary_done)
    primary_req_pool = [c for c in all_courses
                        if c["code"].upper() not in completed
                        and c.get("major_tag") == "primary"
                        and c.get("type") == "RequiredCourse"
                        and (c.get("credits") or 0) > 0]

    result = {
        "total_req":    total_req,
        "total_done":   total_done,
        "total_remain": total_remain,
        "primary": {
            "label":         profile.major,
            "major_req":     primary_req,
            "done":          primary_done,
            "remain":        primary_remain,
            "req_pool_size": len(primary_req_pool),
        },
        "secondary":  None,
        "free_remain": max(0, total_remain - primary_remain),
    }

    if extra_grad_reqs:
        req_info       = extra_grad_reqs[0]
        secondary_done = _done_credits_for_tag("secondary")
        sec_req        = req_info["majorCredits"]
        sec_remain     = max(0, sec_req - secondary_done)
        sec_req_pool   = [c for c in all_courses
                          if c["code"].upper() not in completed
                          and c.get("major_tag") == "secondary"
                          and c.get("type") == "RequiredCourse"
                          and (c.get("credits") or 0) > 0]
        result["secondary"] = {
            "label":         req_info["major"],
            "major_req":     sec_req,
            "done":          secondary_done,
            "remain":        sec_remain,
            "req_pool_size": len(sec_req_pool),
        }
        result["free_remain"] = max(0, total_remain - primary_remain - sec_remain)

    cat_done = category_credits_done(all_courses, completed)
    result["category_breakdown"] = category_remain(cat_done, grad)
    return result


def graduation_feasibility(
    credits_done: int,
    credits_req: int,
    major_credits_done: int,
    major_credits_req: int,
    remaining_sems: int,
) -> dict:
    max_earnable   = remaining_sems * 18
    credits_needed = max(0, credits_req - credits_done)
    major_needed   = max(0, major_credits_req - major_credits_done)

    feasible       = max_earnable >= credits_needed
    sem_needed_min = -(-credits_needed // 18)
    avg_per_sem    = round(credits_needed / remaining_sems, 1) if remaining_sems else 0

    return {
        "feasible":        feasible,
        "credits_needed":  credits_needed,
        "major_needed":    major_needed,
        "max_earnable":    max_earnable,
        "avg_per_sem":     avg_per_sem,
        "min_sems_needed": sem_needed_min,
        "alert":           "⚠ 졸업학점 충족 불가능" if not feasible else None,
    }
