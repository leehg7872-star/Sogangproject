"""
utils/inference.py — 추론 엔진 v2
  Step 1: 데이터 정제 (사이클 제거)
  Step 2: 위상 정렬 (Kahn's Algorithm)
  Step 3: 백트래킹 스케줄러 (Forward Checking CSP)
  Step 4: TOPSIS 다기준 의사결정
"""

import math
import config
import deps


# ── Step 1 ──────────────────────────────────────────────────────

def sanitize_prereq_map(prereq_map: dict[str, set[str]]) -> dict[str, set[str]]:
    """자기참조 제거 + 존재하지 않는 과목 참조 제거"""
    all_codes = set(prereq_map.keys())
    return {
        code: {p for p in prereqs if p != code and p in all_codes}
        for code, prereqs in prereq_map.items()
    }


# ── Step 2 ──────────────────────────────────────────────────────

def topological_sort(
    courses: list[dict],
    prereq_map: dict[str, set[str]],
    completed: set[str],
) -> list[dict]:
    """Kahn's Algorithm으로 선수과목 의존성 순서로 과목 정렬"""
    code_to_course = {c["code"]: c for c in courses}
    codes = [c["code"] for c in courses]

    in_degree: dict[str, int] = {}
    dependents: dict[str, list[str]] = {c: [] for c in codes}

    for code in codes:
        prereqs = prereq_map.get(code, set())
        unsatisfied = prereqs - completed
        in_degree[code] = len(unsatisfied)
        for p in unsatisfied:
            if p in dependents:
                dependents[p].append(code)

    ready = sorted(
        [c for c in codes if in_degree[c] == 0],
        key=lambda c: (
            0 if code_to_course[c].get("type") == "RequiredCourse" else 1,
            -code_to_course[c].get("_fit", 50),
        )
    )

    sorted_courses: list[dict] = []
    while ready:
        code = ready.pop(0)
        sorted_courses.append(code_to_course[code])

        for dep in dependents.get(code, []):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                dep_key = (
                    0 if code_to_course[dep].get("type") == "RequiredCourse" else 1,
                    -code_to_course[dep].get("_fit", 50),
                )
                insert_pos = len(ready)
                for i, r in enumerate(ready):
                    r_key = (
                        0 if code_to_course[r].get("type") == "RequiredCourse" else 1,
                        -code_to_course[r].get("_fit", 50),
                    )
                    if dep_key < r_key:
                        insert_pos = i
                        break
                ready.insert(insert_pos, dep)

    remaining_codes = set(codes) - {c["code"] for c in sorted_courses}
    if remaining_codes:
        print(f"[TOPO] ⚠ 사이클로 미처리 과목 {len(remaining_codes)}개 — 뒤에 추가")
        for code in remaining_codes:
            sorted_courses.append(code_to_course[code])

    return sorted_courses


# ── Step 3 ──────────────────────────────────────────────────────

def schedule_with_backtracking(
    courses: list[dict],
    remaining_sems: list[dict],
    completed: set[str],
    max_credits: int = 18,
    req_ratio: float = 1.0,
    min_major_credits: dict | None = None,
    strict_prereq: bool = False,
    prereq_map: dict | None = None,
    max_total_credits: int | None = None,
) -> list[dict]:
    """균형 배치 스케줄러 (Balanced Required/Elective Placement)"""
    sems = [
        {"label": s["label"], "year": s["year"], "sem": s["sem"],
         "courses": [], "totalCredits": 0, "reqCredits": 0}
        for s in remaining_sems
    ]
    if not sems or not courses:
        return sems

    max_req_per_sem = int(max_credits * req_ratio)

    def _eligible(course: dict, check_req_cap: bool = False) -> list[int]:
        cr     = course.get("credits") or 3
        s1     = course.get("semOpen1") if course.get("semOpen1") is not None else True
        s2     = course.get("semOpen2") if course.get("semOpen2") is not None else True
        is_req = course.get("type") == "RequiredCourse"
        return [
            i for i, s in enumerate(sems)
            if not (s["sem"] == 1 and not s1)
            and not (s["sem"] == 2 and not s2)
            and s["totalCredits"] + cr <= max_credits
            and (not (check_req_cap and is_req)
                 or s["reqCredits"] + cr <= max_req_per_sem)
        ]

    def _best_slot(slots: list[int], course: dict) -> int:
        yr = course.get("yearMin") or 1
        return min(
            slots,
            key=lambda i: (
                0 if sems[i]["year"] >= yr else 1,
                sems[i]["totalCredits"],
            )
        )

    _total_placed_credits: list[int] = [0]

    def _can_place_more(cr: int) -> bool:
        if max_total_credits is None:
            return True
        return _total_placed_credits[0] + cr <= max_total_credits

    def _place(course: dict, si: int) -> None:
        cr     = course.get("credits") or 3
        is_req = course.get("type") == "RequiredCourse"
        sems[si]["courses"].append({
            "code":        course.get("code", ""),
            "name":        course.get("name", ""),
            "credits":     cr,
            "type":        course.get("type", ""),
            "typeLabel":   "전공필수" if is_req else "전공선택",
            "fit":         course.get("_fit", 50),
            "topsis":      course.get("_topsis", 50),
            "major_label": course.get("major_label", ""),
            "prereq_ok":   True,
        })
        sems[si]["totalCredits"]      += cr
        _total_placed_credits[0]      += cr
        if is_req:
            sems[si]["reqCredits"] += cr

    def _pop(si: int, code: str) -> dict | None:
        for idx, c in enumerate(sems[si]["courses"]):
            if c["code"] == code:
                sems[si]["courses"].pop(idx)
                sems[si]["totalCredits"] -= c["credits"]
                if c["type"] == "RequiredCourse":
                    sems[si]["reqCredits"] -= c["credits"]
                return c
        return None

    placed_codes: set[str] = set()

    def _prereq_now_ok(course: dict) -> bool:
        if not strict_prereq or prereq_map is None:
            return True
        for p in prereq_map.get(course["code"], set()):
            if p not in completed and p not in placed_codes:
                return False
        return True

    def _filter_prereq(pool: list[dict]) -> list[dict]:
        if not strict_prereq or prereq_map is None:
            return pool
        ok  = [c for c in pool if _prereq_now_ok(c)]
        skp = [c for c in pool if not _prereq_now_ok(c)]
        if skp:
            print(f"[SCH] strict_prereq: {len(skp)}개 선수미충족 과목 후순위 이동")
        return ok + skp

    required = [c for c in _filter_prereq(courses) if c.get("type") == "RequiredCourse"]
    optional  = [c for c in courses if c.get("type") != "RequiredCourse"]
    opt_map   = {c["code"]: c for c in optional}

    # Phase 1: 필수과목 배치
    for req in required:
        slots = _eligible(req, check_req_cap=True)
        if slots and _can_place_more(req.get("credits") or 3):
            _place(req, _best_slot(slots, req))
            placed_codes.add(req["code"])
            continue

        req_cr = req.get("credits") or 3
        req_s1 = req.get("semOpen1") if req.get("semOpen1") is not None else True
        req_s2 = req.get("semOpen2") if req.get("semOpen2") is not None else True

        swapped = False
        for i, s in enumerate(sems):
            if s["sem"] == 1 and not req_s1: continue
            if s["sem"] == 2 and not req_s2: continue

            elective_in_sem = sorted(
                [c for c in s["courses"] if c["type"] != "RequiredCourse"],
                key=lambda c: c.get("topsis", 50)
            )
            for opt_c in elective_in_sem:
                orig = opt_map.get(opt_c["code"])
                if orig is None: continue
                opt_slots = [j for j in _eligible(orig) if j != i]
                if not opt_slots: continue

                removed = _pop(i, opt_c["code"])
                if removed is None: continue

                can_fit_req = (
                    s["totalCredits"] + req_cr <= max_credits
                    and s["reqCredits"] + req_cr <= max_req_per_sem
                )
                if can_fit_req:
                    _place(req, i)
                    placed_codes.add(req["code"])
                    _place(orig, _best_slot(opt_slots, orig))
                    placed_codes.add(orig["code"])
                    swapped = True
                    break
                else:
                    sems[i]["courses"].append(removed)
                    sems[i]["totalCredits"] += removed["credits"]

            if swapped: break

        if not swapped and req["code"] not in placed_codes:
            print(f"[SCH] ⚠ 필수 배치 불가: {req.get('code')} {req.get('name','')[:20]}")

    # Phase 2: 선택과목 그리디
    opt_sorted = sorted(
        [c for c in optional if c["code"] not in placed_codes],
        key=lambda c: -c.get("_topsis", c.get("_fit", 50))
    )
    for opt in opt_sorted:
        if not _can_place_more(opt.get("credits") or 3):
            break
        slots = _eligible(opt)
        if not slots: continue
        _place(opt, _best_slot(slots, opt))
        placed_codes.add(opt["code"])

    # Phase 3: 전공별 최소 학점 보장
    if min_major_credits:
        major_placed_cr: dict[str, int] = {}
        for s in sems:
            for c in s["courses"]:
                ml = c.get("major_label", "")
                major_placed_cr[ml] = major_placed_cr.get(ml, 0) + (c.get("credits") or 3)

        for major_label, min_cr in min_major_credits.items():
            current_cr = major_placed_cr.get(major_label, 0)
            if current_cr >= min_cr:
                continue
            gap = min_cr - current_cr
            candidates = sorted(
                [c for c in courses
                 if c.get("major_label") == major_label
                 and c["code"] not in placed_codes],
                key=lambda c: -c.get("_topsis", c.get("_fit", 50))
            )
            extra_placed = 0
            for cand in candidates:
                if gap <= 0: break
                slots = _eligible(cand)
                if not slots: continue
                si = min(slots, key=lambda i: sems[i]["totalCredits"])
                _place(cand, si)
                placed_codes.add(cand["code"])
                gap -= cand.get("credits") or 3
                extra_placed += 1
            if extra_placed:
                print(f"[SCH] min_major: '{major_label}' +{extra_placed}과목 추가 (목표{min_cr}학점)")

    req_placed = sum(1 for s in sems for c in s["courses"] if c["type"] == "RequiredCourse")
    opt_placed = sum(1 for s in sems for c in s["courses"] if c["type"] != "RequiredCourse")
    print(f"[SCH] 배치: {req_placed + opt_placed}/{len(courses)}개 (필수={req_placed}, 선택={opt_placed})")
    return [s for s in sems if s["courses"]]


# ── Step 4 ──────────────────────────────────────────────────────

TOPSIS_WEIGHTS = {
    "fit":       0.35,
    "gpa":       0.25,
    "required":  0.20,
    "prereq_ok": 0.15,
    "year_prox": 0.05,
}


def prereq_ok(course_code: str, completed: set[str]) -> bool:
    """선수과목 이수 여부 확인 (KUZU HAS_PREREQUISITE 엣지 기반)"""
    chain = config.query_prereq_chain(deps.kuzu_conn, course_code)
    return all(r["code"].upper() in completed for r in chain)


def topsis_rank(
    courses: list[dict],
    completed: set[str],
    current_year: int = 3,
    prereq_map: dict | None = None,
) -> list[dict]:
    """TOPSIS — 5개 기준 다기준 의사결정"""
    if not courses:
        return courses

    n = len(courses)

    def _prereq_satisfied(code: str) -> bool:
        if prereq_map is not None:
            unsatisfied = prereq_map.get(code, set()) - completed
            return len(unsatisfied) == 0
        return prereq_ok(code, completed)

    matrix: list[dict] = []
    for c in courses:
        yr_min = c.get("yearMin") or 1
        matrix.append({
            "fit":       c.get("_fit", 50) / 100.0,
            "gpa":       min(c.get("avgGpa") or 0.0, 4.5) / 4.5,
            "required":  1.0 if c.get("type") == "RequiredCourse" else 0.0,
            "prereq_ok": 1.0 if _prereq_satisfied(c.get("code", "")) else 0.3,
            "year_prox": 1.0 if yr_min <= current_year else 0.0,
        })

    criteria = list(TOPSIS_WEIGHTS.keys())
    weights  = [TOPSIS_WEIGHTS[k] for k in criteria]

    norms = []
    for k in criteria:
        sq_sum = sum(row[k] ** 2 for row in matrix)
        norms.append(math.sqrt(sq_sum) if sq_sum > 0 else 1.0)

    norm_matrix = [
        {k: row[k] / norms[i] for i, k in enumerate(criteria)}
        for row in matrix
    ]
    weighted = [
        {k: norm_matrix[j][k] * weights[i] for i, k in enumerate(criteria)}
        for j in range(n)
    ]

    ideal_pos = {k: max(weighted[j][k] for j in range(n)) for k in criteria}
    ideal_neg = {k: min(weighted[j][k] for j in range(n)) for k in criteria}

    scores = []
    for j in range(n):
        d_pos = math.sqrt(sum((weighted[j][k] - ideal_pos[k]) ** 2 for k in criteria))
        d_neg = math.sqrt(sum((weighted[j][k] - ideal_neg[k]) ** 2 for k in criteria))
        closeness = d_neg / (d_pos + d_neg) if (d_pos + d_neg) > 0 else 0.0
        scores.append(closeness)

    ranked = []
    for i, c in enumerate(courses):
        c_copy = dict(c)
        c_copy["_topsis"] = round(scores[i] * 100, 1)
        ranked.append(c_copy)

    ranked.sort(key=lambda x: -x["_topsis"])
    return ranked
