"""
data_round4_scenario.py
서강대학교 전공 이수 시나리오 구조화 매핑 테이블

8개 학사제도 문서 + 37개 학과 creditsJson 기반으로 작성.

핵심 개념:
  enrollType   : 이수 유형   (단일전공 | 심화전공 | 실용전공 | 다전공 | 연계전공 | 학생설계전공 | 마이크로전공)
  role         : 전공 내 역할 (주전공 | 타전공주전공)  — 다전공에서만 의미 있음
  track        : 세부 트랙   (지역학전공 | 문화학전공 | 영어트랙_국내 | 영어트랙_국제 | 지융미 | None)
  specialCond  : 특수 조건   (취업 | 미취업 | 자격증취득 | 자격증미취득 | None)

KEY 형식:  (dept_iri, enrollType, role, track, specialCond)
VALUE     :  creditsJson에서 사용할 시나리오 키
"""

# ── 이수유형 상수 ─────────────────────────────────────────────
ENROLL_SINGLE      = "단일전공"
ENROLL_INTENSIVE   = "심화전공"
ENROLL_PRACTICAL   = "실용전공"
ENROLL_MULTI       = "다전공"
ENROLL_COMBINED    = "연계전공"
ENROLL_DESIGNED    = "학생설계전공"
ENROLL_MICRO       = "마이크로전공"
ENROLL_FREE        = "자유전공"

# ── 역할 상수 ─────────────────────────────────────────────────
ROLE_PRIMARY   = "주전공"        # 본인 입학 학과
ROLE_SECONDARY = "타전공주전공"   # 타 학과 입학 학생이 추가

# ── 부가 과정 (전공과 독립) ───────────────────────────────────
ADDON_TEACHER  = "교직과정"
ADDON_BSMS     = "학석사연계"

# ══ 시나리오 매핑 테이블 ════════════════════════════════════════
# (dept_iri, enrollType, role, track, specialCond) → creditsJson 시나리오 키
SCENARIO_KEY: dict[tuple, str] = {

    # ── 국어국문학과 / 사학과 / 철학과 / 종교학과 / 영미어문전공 / 유럽문화학과 ──
    **{(d, ENROLL_MULTI,      ROLE_SECONDARY, None,   None): "다전공"
       for d in ["Dept_KOR","Dept_HIS","Dept_PHI","Dept_REL","Dept_ENG","Dept_EUR",
                 "Dept_SOC","Dept_POL","Dept_PSY","Dept_PHY","Dept_CHM","Dept_BIO",
                 "Dept_CBE","Dept_ECO"]},
    **{(d, ENROLL_MULTI,      ROLE_PRIMARY,   None,   None): "다전공"
       for d in ["Dept_KOR","Dept_HIS","Dept_PHI","Dept_REL","Dept_ENG","Dept_EUR",
                 "Dept_SOC","Dept_POL","Dept_PSY","Dept_PHY","Dept_CHM","Dept_BIO",
                 "Dept_CBE","Dept_ECO"]},
    **{(d, ENROLL_INTENSIVE,  None,           None,   None): "심화전공"
       for d in ["Dept_KOR","Dept_HIS","Dept_PHI","Dept_REL","Dept_ENG","Dept_EUR",
                 "Dept_CBE"]},
    **{(d, ENROLL_PRACTICAL,  None,           None,   None): "실용전공"
       for d in ["Dept_KOR","Dept_HIS","Dept_PHI","Dept_REL","Dept_ENG"]},
    **{(d, ADDON_TEACHER,     None,           None,   None): "교직과정"
       for d in ["Dept_KOR","Dept_HIS","Dept_PHI","Dept_REL","Dept_ENG","Dept_EUR",
                 "Dept_CHI","Dept_AMC","Dept_PSY","Dept_MAT","Dept_PHY","Dept_CHM",
                 "Dept_BIO","Dept_CSE"]},

    # ── 단일전공 보유 학과 ─────────────────────────────────────
    **{(d, ENROLL_SINGLE, None, None, None): "단일전공"
       for d in ["Dept_SOC","Dept_POL","Dept_PSY","Dept_MAT","Dept_PHY","Dept_CHM",
                 "Dept_BIO","Dept_SSE","Dept_AIE","Dept_ECO","Dept_MGT","Dept_JAS",
                 "Dept_MAE","Dept_AAT","Dept_GIS","Dept_GMT","Dept_GME"]},

    # ── 미국문화전공 / 중국문화학과 (트랙 분기) ────────────────
    **{(d, ENROLL_MULTI,    ROLE_SECONDARY, None,       None): "다전공"
       for d in ["Dept_AMC","Dept_CHI"]},
    **{(d, ENROLL_MULTI,    ROLE_PRIMARY,   "문화학",   None): "문화학전공"
       for d in ["Dept_AMC","Dept_CHI"]},
    **{(d, ENROLL_MULTI,    ROLE_PRIMARY,   "지역학",   None): "지역학전공"
       for d in ["Dept_AMC","Dept_CHI"]},
    **{(d, ENROLL_SINGLE,   None,           "문화학",   None): "문화학전공"
       for d in ["Dept_AMC","Dept_CHI"]},
    **{(d, ENROLL_SINGLE,   None,           "지역학",   None): "지역학전공"
       for d in ["Dept_AMC","Dept_CHI"]},

    # ── 수학과 ────────────────────────────────────────────────
    ("Dept_MAT", ENROLL_MULTI, ROLE_PRIMARY,   None, None): "다전공_수학주전공",
    ("Dept_MAT", ENROLL_MULTI, ROLE_SECONDARY, None, None): "다전공_타전공주전공",

    # ── 전자공학과 ────────────────────────────────────────────
    ("Dept_EEE", ENROLL_MULTI,    ROLE_PRIMARY,   None, None): "다전공_전자주전공",
    ("Dept_EEE", ENROLL_MULTI,    ROLE_SECONDARY, None, None): "다전공_타전공주전공",
    ("Dept_EEE", ENROLL_INTENSIVE, None,          None, None): "단일전공심화",

    # ── 기계공학과 ────────────────────────────────────────────
    ("Dept_MEE", ENROLL_MULTI,    ROLE_PRIMARY,   None, None): "다전공_기계주전공",
    ("Dept_MEE", ENROLL_MULTI,    ROLE_SECONDARY, None, None): "다전공_타전공주전공",
    ("Dept_MEE", ENROLL_INTENSIVE, None,          None, None): "심화전공",

    # ── 시스템반도체공학과 ────────────────────────────────────
    ("Dept_SSE", ENROLL_MULTI, ROLE_PRIMARY,   None, "취업"):   "다전공_시반공주전공_취업",
    ("Dept_SSE", ENROLL_MULTI, ROLE_PRIMARY,   None, "미취업"): "다전공_시반공주전공_미취업",
    ("Dept_SSE", ENROLL_MULTI, ROLE_SECONDARY, None, None):    "다전공_타전공주전공",
    ("Dept_SSE", ENROLL_MULTI, None,  "전자공학",      None):   "다전공_전자공주전공",

    # ── 컴퓨터공학과 ──────────────────────────────────────────
    ("Dept_CSE", ENROLL_INTENSIVE, None,          None, None): "단일전공심화",
    ("Dept_CSE", ENROLL_MULTI,    ROLE_PRIMARY,   None, None): "다전공_컴공주전공",
    ("Dept_CSE", ENROLL_MULTI,    ROLE_SECONDARY, None, None): "다전공_타전공주전공",
    # CSE 주전공이면서 AI 다전공하는 경우 (AI가 CSE를 바라봄)
    ("Dept_CSE", ENROLL_MULTI, "AI주전공", None, None): "다전공_인공지능주전공",

    # ── 인공지능학과 ──────────────────────────────────────────
    ("Dept_AIE", ENROLL_MULTI, ROLE_PRIMARY,   None, None): "다전공_인공지능주전공",
    ("Dept_AIE", ENROLL_MULTI, ROLE_SECONDARY, None, None): "다전공_타전공주전공",
    # AI 주전공이면서 CSE 다전공하는 경우
    ("Dept_AIE", ENROLL_MULTI, "컴공주전공", None, None): "다전공_컴공주전공",

    # ── 경영학부 ──────────────────────────────────────────────
    ("Dept_MGT", ENROLL_MULTI, ROLE_PRIMARY,   None, None): "다전공_경영주전공",
    ("Dept_MGT", ENROLL_MULTI, ROLE_SECONDARY, None, None): "다전공_타전공주전공",

    # ── 신문방송학과 ──────────────────────────────────────────
    ("Dept_JAS", ENROLL_MULTI, ROLE_PRIMARY,   None, None): "다전공_신방주전공",
    ("Dept_JAS", ENROLL_MULTI, ROLE_SECONDARY, None, None): "다전공_타전공주전공",

    # ── 미디어&엔터테인먼트학과 ───────────────────────────────
    ("Dept_MAE", ENROLL_MULTI, ROLE_PRIMARY,   None, None): "다전공_미엔주전공",
    ("Dept_MAE", ENROLL_MULTI, ROLE_SECONDARY, None, None): "다전공_타전공주전공",

    # ── Art & Technology ──────────────────────────────────────
    ("Dept_AAT", ENROLL_MULTI, ROLE_PRIMARY,   None, None): "다전공_아텍주전공",
    ("Dept_AAT", ENROLL_MULTI, ROLE_SECONDARY, None, None): "다전공_타전공주전공",

    # ── 한국어교육전공 ────────────────────────────────────────
    ("Dept_GKE", ENROLL_SINGLE, None,           None, "자격증취득"):   "단일전공_자격증취득",
    ("Dept_GKE", ENROLL_MULTI,  ROLE_PRIMARY,   None, "자격증취득"):   "다전공_자격증취득",
    ("Dept_GKE", ENROLL_MULTI,  ROLE_PRIMARY,   None, "자격증미취득"): "다전공_자격증미취득",
    ("Dept_GKE", ENROLL_MULTI,  ROLE_SECONDARY, None, "자격증취득"):   "다전공_자격증취득",
    ("Dept_GKE", ENROLL_MULTI,  ROLE_SECONDARY, None, "자격증미취득"): "다전공_자격증미취득",

    # ── Global Korean Studies ─────────────────────────────────
    ("Dept_GKS", ENROLL_SINGLE, None, "지융미",   None): "지융미_글로벌한국학_단일전공",
    ("Dept_GKS", ENROLL_MULTI,  None, "지융미",   None): "지융미_글로벌한국학_다전공",
    ("Dept_GKS", ENROLL_SINGLE, None, "국내",     None): "영어트랙_국내_단일전공",
    ("Dept_GKS", ENROLL_MULTI,  None, "국내",     None): "영어트랙_국내_다전공",
    ("Dept_GKS", ENROLL_SINGLE, None, "국제",     None): "영어트랙_국제_단일전공",
    ("Dept_GKS", ENROLL_MULTI,  None, "국제",     None): "영어트랙_국제_다전공",

    # ── International Relations / Asian Studies ───────────────
    **{(d, ENROLL_SINGLE, None, "국내", None): "영어트랙_국내_단일전공"
       for d in ["Dept_TIR","Dept_AAS"]},
    **{(d, ENROLL_MULTI,  None, "국내", None): "영어트랙_국내_다전공"
       for d in ["Dept_TIR","Dept_AAS"]},
    **{(d, ENROLL_SINGLE, None, "국제", None): "영어트랙_국제_단일전공"
       for d in ["Dept_TIR","Dept_AAS"]},
    **{(d, ENROLL_MULTI,  None, "국제", None): "영어트랙_국제_다전공"
       for d in ["Dept_TIR","Dept_AAS"]},

    # ── International Commerce (다전공 상대방 학과별 분기) ────
    ("Dept_TIC", ENROLL_SINGLE, None, "국내",       None): "영어트랙_국내_단일전공",
    ("Dept_TIC", ENROLL_MULTI,  None, "국내_경제",  None): "영어트랙_국내_다전공_경제",
    ("Dept_TIC", ENROLL_MULTI,  None, "국내_경영",  None): "영어트랙_국내_다전공_경영",
    ("Dept_TIC", ENROLL_MULTI,  None, "국내_경영경제", None): "영어트랙_국내_다전공_경영경제",
    ("Dept_TIC", ENROLL_MULTI,  None, "국내_타과",  None): "영어트랙_국내_다전공_타과",
    ("Dept_TIC", ENROLL_SINGLE, None, "국제",       None): "영어트랙_국제_단일전공",
    ("Dept_TIC", ENROLL_MULTI,  None, "국제",       None): "영어트랙_국제_다전공",
}


def resolve_scenario_key(
    dept_iri: str,
    enroll_type: str,
    role: str | None = None,
    track: str | None = None,
    special_cond: str | None = None,
) -> str | None:
    """
    주어진 조건으로 creditsJson 시나리오 키 반환.
    매칭 실패 시 None 반환 (호출부에서 폴백 처리).

    탐색 순서 (구체 → 일반):
    1. (dept, enrollType, role, track, specialCond) 완전 일치
    2. (dept, enrollType, role, track, None)       specialCond 무시
    3. (dept, enrollType, role, None, None)        track도 무시
    4. (dept, enrollType, None, None, None)        role도 무시
    """
    candidates = [
        (dept_iri, enroll_type, role,  track, special_cond),
        (dept_iri, enroll_type, role,  track, None),
        (dept_iri, enroll_type, role,  None,  None),
        (dept_iri, enroll_type, None,  None,  None),
    ]
    for key in candidates:
        if key in SCENARIO_KEY:
            return SCENARIO_KEY[key]
    return None


# ── 자유전공학부 기반 유형 ────────────────────────────────────
FREE_MAJOR_DEPT_IRIS = {
    "Dept_FREE_HUM": "인문학기반 자유전공학부",
    "Dept_FREE_SCI": "SCIENCE기반 자유전공학부",
    "Dept_FREE_AI":  "AI기반 자유전공학부",
}

# ── 졸업 카테고리 분류 기준 ───────────────────────────────────
# (courseType → graduationCategory 자동 부여 기준)
COURSE_TYPE_TO_GRAD_CATEGORY: dict[str, str] = {
    "RequiredCourse":    "전공필수",
    "ElectiveCourse":    "전공선택",
    "CapstoneCourse":    "전공선택",   # 캡스톤도 전공선택으로 집계
    "IntroductoryCourse": None,        # 개별 확인 필요 (교양 vs 전공입문 혼재)
}

# GKS 계열 코드 = 전인교육(교양) 계열
LIBERAL_ARTS_CODE_PREFIXES = ("GKS", "ENG1001", "ENG1002")

