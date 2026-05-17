"""
utils/career.py — Career profile 생성 및 과목 fit 점수 계산
"""

import config
import deps
from utils.llm import llm_json
from utils.activity import normalize_activities

# 세션 내 캐시 (key: "job|industries|certs|activities|internships|secondaryMajor|thirdMajor")
_career_profile_cache: dict[str, dict] = {}


async def get_career_profile(profile) -> dict:
    cache_key = (
        f"{profile.job}|{profile.industries}|{profile.certs}"
        f"|{profile.activities}|{profile.internships}"
        f"|{profile.secondaryMajor}|{profile.thirdMajor}"
    )
    if cache_key in _career_profile_cache:
        return _career_profile_cache[cache_key]

    # 비교과 활동 정규화
    act = await normalize_activities(profile.activities or "", profile.internships or "")
    act_summary  = act.get("category_summary", "없음")
    act_skills   = ", ".join(act.get("skill_tags", [])[:8]) or "없음"

    # ── 그래프 기반 직무 조회 (data_round4 JobRole) ──────────────
    graph_job    = config.query_job_role(deps.kuzu_conn, profile.job) if deps.kuzu_conn else None
    graph_kws    = graph_job["keywords"].split(",") if graph_job else []
    graph_kw_str = ", ".join(kw.strip() for kw in graph_kws[:10]) if graph_kws else "없음"
    if graph_job:
        print(f"[CAREER] 그래프 직무 매칭: {graph_job['name']} ({graph_job['iri']})")

    system = (
        "학생의 진로 정보를 분석해 과목 추천에 사용할 career profile을 JSON으로 반환하세요.\n\n"
        "출력 JSON 형식 (정확히 이 구조만):\n"
        '{"keywords":["키워드1","키워드2",...],'
        '"skill_tags":["스킬분류1","스킬분류2",...],'
        '"dept_boosts":{"Dept_CHI":1.4,"Dept_MGT":1.2},'
        '"rationale":"근거 한 줄"}\n\n'
        "규칙:\n"
        "- keywords: 직무+산업군+활동 경험에서 파생되는 핵심 과목 관련 단어 10~15개\n"
        "- skill_tags: 어학/프로그래밍/경영/분석/설계/커뮤니케이션 등 스킬 분류 3~5개\n"
        "- dept_boosts: 관련 학과 IRI와 가중치 (1.0=기준, 최대 1.5, 최소 0.5)\n"
        "  사용 가능한 dept IRI: Dept_CHI,Dept_ENG,Dept_EUR,Dept_AMC,Dept_KOR,"
        "Dept_HIS,Dept_PHI,Dept_SOC,Dept_POL,Dept_PSY,Dept_ECO,Dept_MGT,"
        "Dept_CSE,Dept_EEE,Dept_MEE,Dept_CBE,Dept_MAT,Dept_BIO,Dept_JAS,"
        "Dept_MAE,Dept_GKS,Dept_AIE,Dept_SSE"
    )
    prompt = (
        f"직무: {profile.job}\n"
        f"희망 산업군: {profile.industries or '미입력'}\n"
        f"보유 자격증: {profile.certs or '없음'}\n"
        f"비교과 활동 요약: {act_summary}\n"
        f"활동 역량 태그: {act_skills}\n"
        f"그래프DB 직무 키워드(우선 반영): {graph_kw_str}\n"
        f"본전공: {profile.major} / 제2전공: {profile.secondaryMajor or '없음'}"
    )

    result = await llm_json(system, prompt, max_tokens=500)

    if not isinstance(result, dict):
        result = {}
    result.setdefault("keywords",   [profile.job])
    result.setdefault("skill_tags", [])
    result.setdefault("dept_boosts", {})
    result.setdefault("rationale",  "")

    # 정규화된 활동 정보
    result["normalized_activities"] = act

    # 그래프 직무 정보 (있는 경우) — weighted_fit에서 우선 활용
    if graph_job:
        result["graph_job_iri"]      = graph_job["iri"]
        result["graph_job_keywords"] = [kw.strip() for kw in graph_kws]
        # 그래프에서 직무 적합 과목 상위 30개 캐싱 (fit_weight 내림차순)
        result["graph_fit_courses"] = {
            row["code"]: row["fit_weight"]
            for row in config.query_courses_by_job(deps.kuzu_conn, graph_job["iri"], limit=30)
        }
    else:
        result.setdefault("graph_job_iri",      "")
        result.setdefault("graph_job_keywords", [])
        result.setdefault("graph_fit_courses",  {})

    _career_profile_cache[cache_key] = result
    print(f"[CAREER] profile 생성: job={profile.job}, "
          f"graph_match={graph_job['name'] if graph_job else 'N/A'}, "
          f"keywords={result['keywords'][:4]}")
    return result


def weighted_fit(course: dict, career_profile: dict) -> int:
    """
    career profile 기반 과목 fit 점수 계산 (0~100).
    그래프 FITS_JOB weight 우선 → LLM 키워드 매칭 보완.
    """
    code = (course.get("code") or course.get("courseCode") or "").upper()

    # ── 1순위: 그래프 기반 fit_weight (data_round4 FITS_JOB) ──────
    graph_fits = career_profile.get("graph_fit_courses", {})
    if code in graph_fits:
        return min(100, int(graph_fits[code] * 100))

    # ── 2순위: 그래프 직무 키워드 + LLM 키워드 결합 매칭 ──────────
    graph_kws   = [kw.lower() for kw in career_profile.get("graph_job_keywords", [])]
    llm_kws     = [kw.lower() for kw in career_profile.get("keywords", [])]
    keywords    = list(dict.fromkeys(graph_kws + llm_kws))  # 중복 제거, 그래프 우선
    dept_boosts = career_profile.get("dept_boosts", {})

    description = (course.get("description") or "").lower()
    name        = (course.get("name") or "").lower()
    full_text   = description + " " + name
    dept_iri    = course.get("deptIri") or course.get("dept_iri") or ""

    kw_hits  = sum(1 for kw in keywords if kw in full_text)
    kw_score = min(45, kw_hits * 10 + sum(
        0.5 for kw in keywords if len(kw) >= 2 and kw[:2] in full_text
    ))

    boost      = dept_boosts.get(dept_iri, 1.0)
    dept_score = max(0, min(25, int((boost - 0.5) * 50)))

    name_hits  = sum(1 for kw in keywords if kw in name)
    name_bonus = min(15, name_hits * 8)

    return min(100, int(kw_score) + dept_score + name_bonus + 15)
