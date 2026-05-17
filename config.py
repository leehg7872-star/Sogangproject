"""
config.py — KUZU 기반 그래프 DB 설정 모듈
─────────────────────────────────────────────────────────────────
역할:
  1. KUZU 노드·엣지 테이블 스키마 정의 (OWL 온톨로지 파생)
  2. build_kuzu_db() : data_round 파일 → KUZU DB 최초 적재
  3. get_connection() : app.py 에서 쿼리용 커넥션 반환
  4. OWL ObjectProperty → KUZU 관계 매핑 상수 보존

사용:
  from config import build_kuzu_db, get_connection, DB_PATH
  build_kuzu_db(DB_PATH)          # 최초 1회 (또는 force_rebuild=True)
  conn = get_connection(DB_PATH)  # app 시작 시
"""

import os, json
import kuzu

# ── DB 경로 ─────────────────────────────────────────────────────
DB_PATH = os.getenv("KUZU_DB_PATH", "./sogang_kuzu_db")

# ── OWL ObjectProperty → KUZU 관계 타입 매핑 (참조용) ──────────
REL_MAP: dict[str, str] = {
    "enrollsIn":           "ENROLLS_IN",
    "hasPrimaryMajor":     "HAS_PRIMARY_MAJOR",
    "hasAdditionalMajor":  "HAS_ADDITIONAL_MAJOR",
    "belongsToDept":       "BELONGS_TO_DEPT_STU",
    "takes":               "TAKES",
    "hasTaken":            "HAS_TAKEN",
    "acquires":            "ACQUIRES",
    "targetsJobRole":      "TARGETS_JOB_ROLE",
    "participatesIn":      "PARTICIPATES_IN",
    "appliesTo":           "APPLIES_TO",
    "belongsTo":           "BELONGS_TO",
    "inCluster":           "IN_CLUSTER",
    "hasTrack":            "HAS_TRACK",
    "offeredBy":           "OFFERED_BY",
    "includes":            "INCLUDES",
    "constitutedBy":       "CONSTITUTED_BY",
    "partOfCurriculum":    "PART_OF_CURRICULUM",
    "offeredByDept":       "OFFERED_BY_DEPT",
    "hasPrerequisite":     "HAS_PREREQUISITE",
    "codeSharesWith":      "CODE_SHARES_WITH",
    "equivalentTo":        "EQUIVALENT_TO",
    "coversConcept":       "COVERS_CONCEPT",
    "develops":            "DEVELOPS",
    "composedOf":          "COMPOSED_OF",
    "enablesCareer":       "ENABLES_CAREER",
    "requiresCompetency":  "REQUIRES_COMPETENCY",
    "jobRequiresCompetency": "JOB_REQUIRES_COMPETENCY",
    "governedBy":          "GOVERNED_BY",
    "satisfies":           "SATISFIES",
    "hasOpportunity":      "HAS_OPPORTUNITY",
    "matchedWith":         "MATCHED_WITH",
}

# OWL 특수 공리 분류
SYMMETRIC_RELS  = {"CODE_SHARES_WITH", "EQUIVALENT_TO"}
TRANSITIVE_RELS = {"HAS_PREREQUISITE"}
FUNCTIONAL_RELS = {"HAS_PRIMARY_MAJOR", "BELONGS_TO"}

# ════════════════════════════════════════════════════════════════
# §1. 스키마 DDL
# ════════════════════════════════════════════════════════════════

# 노드 테이블 DDL — OWL 클래스 파생
_NODE_DDL = [
    # A. Organization
    """CREATE NODE TABLE IF NOT EXISTS AcademicCluster(
        iri   STRING PRIMARY KEY,
        name  STRING
    )""",
    """CREATE NODE TABLE IF NOT EXISTS College(
        iri   STRING PRIMARY KEY,
        name  STRING
    )""",
    """CREATE NODE TABLE IF NOT EXISTS Department(
        iri          STRING PRIMARY KEY,
        name         STRING,
        codePrefix   STRING,
        yearbookPage INT64,
        creditsJson  STRING
    )""",

    # C. Major — majorType 필드로 FirstMajor/CombinedMajor/MicroMajor 구분
    """CREATE NODE TABLE IF NOT EXISTS Major(
        iri          STRING PRIMARY KEY,
        name         STRING,
        majorType    STRING,
        majorVariant STRING,
        deptIri      STRING,
        majorCredits INT64,
        totalCredits INT64,
        minCredits   INT64,
        yearbookPage INT64,
        notes        STRING
    )""",

    # E. Course — courseType으로 Required/Elective/Capstone 구분
    # sem_open_1/2 : 1학기/2학기 개설 여부 (data_round2 보완 시 활용)
    # graduationCategory : 전공필수|전공선택|전공입문|공통필수|공통선택
    # countsTowardMajorCredits : 전공학점 산입 여부 (공통필수 등 False)
    # subArea : 공통선택 세부영역 (인간과신앙|인간과사상|인간과사회|인간과과학AI 등)
    """CREATE NODE TABLE IF NOT EXISTS Course(
        courseCode              STRING PRIMARY KEY,
        courseName              STRING,
        credits                 INT64,
        courseType              STRING,
        deptIri                 STRING,
        semOpen1                BOOLEAN,
        semOpen2                BOOLEAN,
        yearMin                 INT64,
        avgGpa                  DOUBLE,
        description             STRING,
        hoursInfo               STRING,
        isGraduateBridge        BOOLEAN,
        isCodeShared            BOOLEAN,
        graduationCategory      STRING,
        countsTowardMajorCredits BOOLEAN,
        subArea                 STRING
    )""",

    # I. AcademicPolicy
    """CREATE NODE TABLE IF NOT EXISTS AcademicPolicy(
        iri            STRING PRIMARY KEY,
        name           STRING,
        policyType     STRING,
        effectiveYear  INT64,
        minSemester    INT64,
        minCgpa        DOUBLE,
        minCredits     INT64,
        totalCredits   INT64,
        notes          STRING,
        contactOffice  STRING
    )""",

    # H. JobRole — 추후 data_round4에서 인스턴스 추가
    """CREATE NODE TABLE IF NOT EXISTS JobRole(
        iri      STRING PRIMARY KEY,
        name     STRING,
        category STRING,
        keywords STRING
    )""",
]

# 엣지 테이블 DDL — OWL ObjectProperty 파생
_REL_DDL = [
    "CREATE REL TABLE IF NOT EXISTS IN_CLUSTER(FROM College TO AcademicCluster)",
    "CREATE REL TABLE IF NOT EXISTS BELONGS_TO(FROM Department TO College)",
    "CREATE REL TABLE IF NOT EXISTS OFFERED_BY(FROM Major TO Department)",
    "CREATE REL TABLE IF NOT EXISTS CONSTITUTED_BY(FROM Major TO Department)",
    "CREATE REL TABLE IF NOT EXISTS OFFERED_BY_DEPT(FROM Course TO Department)",
    # TransitiveProperty: 직접 관계만 저장, 추이 추론은 Cypher [:HAS_PREREQUISITE*] 경로로
    "CREATE REL TABLE IF NOT EXISTS HAS_PREREQUISITE(FROM Course TO Course)",
    # SymmetricProperty: 양방향 엣지 각각 저장
    "CREATE REL TABLE IF NOT EXISTS CODE_SHARES_WITH(FROM Course TO Course)",
    # EQUIVALENT_TO: 대체인정 — 컨텍스트 학과 IRI 보존
    "CREATE REL TABLE IF NOT EXISTS EQUIVALENT_TO(FROM Course TO Course, deptIri STRING)",
    # 학사 정책 연결 (미래 확장용)
    "CREATE REL TABLE IF NOT EXISTS GOVERNED_BY(FROM Department TO AcademicPolicy)",
    # 진로 연결
    "CREATE REL TABLE IF NOT EXISTS TARGETS_JOB_ROLE(FROM Major TO JobRole)",
    # 과목-직무 적합도 (data_round4)
    "CREATE REL TABLE IF NOT EXISTS FITS_JOB(FROM Course TO JobRole, weight DOUBLE)",
]


# ════════════════════════════════════════════════════════════════
# §2. DB 적재 로직
# ════════════════════════════════════════════════════════════════

def _exec(conn: kuzu.Connection, q: str, params: dict | None = None):
    """파라미터 바인딩 쿼리 실행 헬퍼"""
    if params:
        conn.execute(q, params)
    else:
        conn.execute(q)


def _try(conn, q, p=None):
    """모든 쿼리를 try/except로 감싸 중복 시 skip"""
    try:
        conn.execute(q, p) if p else conn.execute(q)
    except RuntimeError:
        pass


def _load_organizations(conn: kuzu.Connection, R1) -> None:
    """계열 → 대학 → 학과 적재"""
    for c in R1.CLUSTERS:
        _try(conn,
            "CREATE (:AcademicCluster {iri: $iri, name: $name})",
            {"iri": c["iri"], "name": c["name"]})

    cluster_map = {c["name"]: c["iri"] for c in R1.CLUSTERS}

    for col in R1.COLLEGES:
        _try(conn,
            "CREATE (:College {iri: $iri, name: $name})",
            {"iri": col["iri"], "name": col["name"]})
        cls_iri = cluster_map.get(col["cluster"])
        if cls_iri:
            _try(conn,
                "MATCH (a:College {iri: $col}), (b:AcademicCluster {iri: $cls}) "
                "CREATE (a)-[:IN_CLUSTER]->(b)",
                {"col": col["iri"], "cls": cls_iri})

    for dept in R1.DEPARTMENTS:
        _try(conn,
            "CREATE (:Department {iri: $iri, name: $name, codePrefix: $cp, "
            "yearbookPage: $yp, creditsJson: $cj})",
            {
                "iri": dept["iri"],
                "name": dept["name"],
                "cp":  dept.get("code_prefix", ""),
                "yp":  dept.get("yearbook_page", 0),
                "cj":  json.dumps(dept.get("credits", {}), ensure_ascii=False),
            })
        _try(conn,
            "MATCH (d:Department {iri: $di}), (c:College {iri: $ci}) "
            "CREATE (d)-[:BELONGS_TO]->(c)",
            {"di": dept["iri"], "ci": dept["college_iri"]})


def _load_majors(conn: kuzu.Connection, R1) -> None:
    """1전공 + 연계전공 + 마이크로전공 적재"""
    def _insert_major(m: dict):
        _try(conn,
            "CREATE (:Major {iri: $iri, name: $name, majorType: $mt, "
            "majorVariant: $mv, deptIri: $di, majorCredits: $mc, "
            "totalCredits: $tc, minCredits: $mn, yearbookPage: $yp, notes: $no})",
            {
                "iri": m["iri"],
                "name": m["name"],
                "mt":  m.get("majorType", ""),
                "mv":  m.get("majorVariant", ""),
                "di":  m.get("dept_iri", ""),
                "mc":  m.get("majorCredits", 0),
                "tc":  m.get("totalCredits", 130),
                "mn":  m.get("minCredits", 0),
                "yp":  m.get("yearbook_page", 0),
                "no":  m.get("notes", ""),
            })
        # OFFERED_BY 엣지
        if m.get("dept_iri"):
            _try(conn,
                "MATCH (maj:Major {iri: $mi}), (d:Department {iri: $di}) "
                "CREATE (maj)-[:OFFERED_BY]->(d)",
                {"mi": m["iri"], "di": m["dept_iri"]})

    for m in R1.FIRST_MAJORS:
        _insert_major(m)

    for m in R1.COMBINED_MAJORS:
        _insert_major(m)
        for dept_iri in m.get("constituent_dept_iris", []):
            _try(conn,
                "MATCH (maj:Major {iri: $mi}), (d:Department {iri: $di}) "
                "CREATE (maj)-[:CONSTITUTED_BY]->(d)",
                {"mi": m["iri"], "di": dept_iri})

    for m in R1.MICRO_MAJORS:
        _insert_major(m)


def _load_policies(conn: kuzu.Connection, R1) -> None:
    """학사 정책 적재"""
    for p in R1.ACADEMIC_POLICIES:
        _try(conn,
            "CREATE (:AcademicPolicy {iri: $iri, name: $name, policyType: $pt, "
            "effectiveYear: $ey, minSemester: $ms, minCgpa: $mc, "
            "minCredits: $mn, totalCredits: $tc, notes: $no, contactOffice: $co})",
            {
                "iri": p["iri"],
                "name": p["name"],
                "pt":  p.get("policyType", ""),
                "ey":  p.get("effectiveYear", 0),
                "ms":  p.get("minSemester", 0),
                "mc":  p.get("minCgpa", 0.0),
                "mn":  p.get("minCredits", 0),
                "tc":  p.get("totalCredits", 0),
                "no":  p.get("notes", ""),
                "co":  p.get("contactOffice", ""),
            })


def _load_courses(conn: kuzu.Connection, R2, graduate_bridge_set: set,
                  codeshared_set: set, meta: dict) -> None:
    """전공 과목 + 공통 교양 적재 (KUZU 호환: 프로퍼티 분할 CREATE+SET)"""
    all_courses = list(R2.COURSES) + list(R2.COMMON_COURSES)
    seen_codes: set = set()   # data_round2 내 중복 코드 방어
    for c in all_courses:
        code = c["courseCode"]
        if code in seen_codes:
            continue
        seen_codes.add(code)
        m    = meta.get(code, {})
        name = c.get("courseName", "")
        cr   = c.get("credits", 3)
        ct   = c.get("courseType", "ElectiveCourse")
        di   = c.get("dept_iri", "")
        s1   = m.get("sem_open_1", c.get("semOpen1", True))
        s2   = m.get("sem_open_2", c.get("semOpen2", True))
        ym   = m.get("year_min",   c.get("yearMin",  2))
        gpa  = m.get("avg_gpa",    c.get("avgGpa",   0.0))
        desc = (m.get("description") or c.get("description") or name)[:200]
        hi   = (c.get("hoursInfo") or c.get("hours_info") or "")[:100]
        gb   = code in graduate_bridge_set
        cs   = code in codeshared_set
        # ── 신규 필드 ──
        gc   = c.get("graduationCategory", "")        # 전공필수|전공선택|전공입문|공통필수|공통선택
        ctm  = bool(c.get("countsTowardMajorCredits", True))  # 전공학점 산입 여부
        sa   = (c.get("subArea") or "")[:50]          # 공통선택 세부영역

        # KUZU: 프로퍼티를 4개씩 나눠 CREATE + SET으로 분리 (중복 시 skip)
        _try(conn,
            "CREATE (:Course {courseCode: $p1, courseName: $p2, credits: $p3, courseType: $p4})",
            {"p1": code, "p2": name, "p3": cr, "p4": ct}
        )
        _try(conn,
            "MATCH (c:Course {courseCode: $code}) "
            "SET c.deptIri = $p1, c.semOpen1 = $p2, c.semOpen2 = $p3, c.yearMin = $p4",
            {"code": code, "p1": di, "p2": s1, "p3": s2, "p4": ym}
        )
        _try(conn,
            "MATCH (c:Course {courseCode: $code}) "
            "SET c.avgGpa = $p1, c.description = $p2, c.hoursInfo = $p3",
            {"code": code, "p1": gpa, "p2": desc, "p3": hi}
        )
        _try(conn,
            "MATCH (c:Course {courseCode: $code}) "
            "SET c.isGraduateBridge = $p1, c.isCodeShared = $p2",
            {"code": code, "p1": gb, "p2": cs}
        )
        # ── 신규: 졸업 카테고리 필드 적재 ──
        _try(conn,
            "MATCH (c:Course {courseCode: $code}) "
            "SET c.graduationCategory = $p1, c.countsTowardMajorCredits = $p2, c.subArea = $p3",
            {"code": code, "p1": gc, "p2": ctm, "p3": sa}
        )
        # OFFERED_BY_DEPT 엣지
        if c.get("dept_iri"):
            _try(conn,
                "MATCH (co:Course {courseCode: $code}), (d:Department {iri: $di}) "
                "CREATE (co)-[:OFFERED_BY_DEPT]->(d)",
                {"code": code, "di": c["dept_iri"]})
        # HAS_PREREQUISITE 엣지
        for pre in c.get("prerequisites", []):
            try:
                conn.execute(
                    "CREATE (:Course {courseCode: $p1, courseName: $p2, credits: $p3, courseType: $p4})",
                    {"p1": pre, "p2": pre, "p3": 0, "p4": "Unknown"}
                )
                conn.execute(
                    "MATCH (c:Course {courseCode: $code}) "
                    "SET c.deptIri=$p1,c.semOpen1=$p2,c.semOpen2=$p3,"
                    "c.yearMin=$p4,c.avgGpa=$p5,c.description=$p6,"
                    "c.hoursInfo=$p7,c.isGraduateBridge=$p8,c.isCodeShared=$p9",
                    {"code":pre,"p1":"","p2":True,"p3":True,
                     "p4":0,"p5":0.0,"p6":"","p7":"","p8":False,"p9":False}
                )
            except RuntimeError:
                pass
            try:
                conn.execute(
                    "MATCH (a:Course {courseCode: $a}), (b:Course {courseCode: $b}) "
                    "CREATE (a)-[:HAS_PREREQUISITE]->(b)",
                    {"a": code, "b": pre}
                )
            except RuntimeError:
                pass


def _safe_stub(conn, code: str, ctype: str) -> None:
    """더미 Course 노드 생성 — 이미 존재하면 skip"""
    try:
        conn.execute(
            "CREATE (:Course {courseCode: $p1, courseName: $p2, credits: $p3, courseType: $p4})",
            {"p1": code, "p2": code, "p3": 0, "p4": ctype}
        )
        is_cs = ctype == "CodeSharedCourse"
        conn.execute(
            "MATCH (c:Course {courseCode: $code}) "
            "SET c.deptIri=$p1,c.semOpen1=$p2,c.semOpen2=$p3,"
            "c.yearMin=$p4,c.avgGpa=$p5,c.description=$p6,"
            "c.hoursInfo=$p7,c.isGraduateBridge=$p8,c.isCodeShared=$p9",
            {"code":code,"p1":"","p2":True,"p3":True,
             "p4":0,"p5":0.0,"p6":"","p7":"","p8":False,"p9":is_cs}
        )
    except RuntimeError:
        pass


def _load_relations_r3(conn: kuzu.Connection, R3) -> None:
    """코드쉐어 + 대체인정 관계 적재 (R3)"""
    for cs in R3.CODE_SHARES:
        a, b = cs["code_a"], cs["code_b"]
        for code in [a, b]:
            _safe_stub(conn, code, "CodeSharedCourse")
        try:
            conn.execute(
                "MATCH (x:Course {courseCode: $a}), (y:Course {courseCode: $b}) "
                "CREATE (x)-[:CODE_SHARES_WITH]->(y)",
                {"a": a, "b": b}
            )
            conn.execute(
                "MATCH (x:Course {courseCode: $b}), (y:Course {courseCode: $a}) "
                "CREATE (x)-[:CODE_SHARES_WITH]->(y)",
                {"a": a, "b": b}
            )
        except RuntimeError:
            pass

    for s in R3.SUBSTITUTIONS:
        oc, mc, di = s["outside_code"], s["our_code"], s.get("dept_iri", "")
        for code in [oc, mc]:
            _safe_stub(conn, code, "ElectiveCourse")
        try:
            conn.execute(
                "MATCH (a:Course {courseCode: $a}), (b:Course {courseCode: $b}) "
                "CREATE (a)-[:EQUIVALENT_TO {deptIri: $di}]->(b)",
                {"a": oc, "b": mc, "di": di}
            )
            conn.execute(
                "MATCH (a:Course {courseCode: $b}), (b:Course {courseCode: $a}) "
                "CREATE (a)-[:EQUIVALENT_TO {deptIri: $di}]->(b)",
                {"a": oc, "b": mc, "di": di}
            )
        except RuntimeError:
            pass


# ════════════════════════════════════════════════════════════════
# §3. 공개 인터페이스
# ════════════════════════════════════════════════════════════════

def build_kuzu_db(db_path: str = DB_PATH, *, force_rebuild: bool = False) -> None:
    """
    KUZU 데이터베이스 구축 (최초 실행 또는 연간 업데이트 시).
    force_rebuild=True 이면 기존 DB를 삭제하고 재구축.

    사용 예:
        python -c "from config import build_kuzu_db; build_kuzu_db(force_rebuild=True)"
    """
    import shutil, time

    if force_rebuild and os.path.exists(db_path):
        shutil.rmtree(db_path)
        print(f"[KUZU] 기존 DB 삭제: {db_path}")

    already_exists = os.path.exists(db_path)

    db   = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    # ── DDL ─────────────────────────────────────────────────────
    print("[KUZU] 스키마 생성 중...")
    for ddl in _NODE_DDL + _REL_DDL:
        conn.execute(ddl)

    if already_exists and not force_rebuild:
        print("[KUZU] DB 이미 존재 — 스키마만 확인, 데이터 적재 생략.")
        print("[KUZU] 재구축이 필요하면 force_rebuild=True 로 호출하세요.")
        return

    # ── 데이터 모듈 import ──────────────────────────────────────
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import data_round1 as R1
    import data_round2 as R2
    import data_round3 as R3

    # data_round2_meta: sem_open / year_min / avg_gpa / description 보완
    try:
        import data_round2_meta as R2M
        course_meta = R2M.COURSE_META
        print(f"[KUZU] data_round2_meta 로드 완료 ({len(course_meta):,}개 과목 메타)")
    except ImportError:
        course_meta = {}
        print("[KUZU] ⚠ data_round2_meta 없음 — 기본값 사용 (sem_open=양학기, year_min=2, avg_gpa=0.0)")

    t0 = time.time()
    print("[KUZU] 조직 계층 적재 중...")
    _load_organizations(conn, R1)

    print("[KUZU] 전공 적재 중...")
    _load_majors(conn, R1)

    print("[KUZU] 학사 정책 적재 중...")
    _load_policies(conn, R1)

    # R3 보조 집합 미리 구성
    gb_set = {
        code
        for codes in R3.GRADUATE_BRIDGE_COURSES.values()
        for code in codes
    }
    cs_set = {cs["code_a"] for cs in R3.CODE_SHARES} | {cs["code_b"] for cs in R3.CODE_SHARES}

    print("[KUZU] 과목 적재 중 (약 2,400개)...")
    _load_courses(conn, R2, gb_set, cs_set, course_meta)

    print("[KUZU] 코드쉐어·대체인정 관계 적재 중...")
    _load_relations_r3(conn, R3)

    print("[KUZU] 직무(JobRole) 데이터 적재 중...")
    try:
        import data_round4 as R4
        _load_job_roles(conn, R4)
    except ImportError:
        print("[KUZU] ⚠ data_round4 없음 — JobRole 적재 생략")

    elapsed = time.time() - t0
    # 통계 출력
    for tbl in ["AcademicCluster", "College", "Department", "Major", "Course", "AcademicPolicy", "JobRole"]:
        result = conn.execute(f"MATCH (n:{tbl}) RETURN count(n) AS cnt")
        cnt = result.get_next()[0]
        print(f"  {tbl}: {cnt:,}개")
    print(f"[KUZU] 완료 ({elapsed:.1f}초) — DB 경로: {db_path}")


def get_connection(db_path: str = DB_PATH) -> kuzu.Connection:
    """
    app.py 에서 KUZU 쿼리용 커넥션 반환.
    DB가 없으면 자동으로 build_kuzu_db() 호출.
    """
    if not os.path.exists(db_path):
        print(f"[KUZU] DB 없음 — 자동 구축 시작: {db_path}")
        build_kuzu_db(db_path)
    db = kuzu.Database(db_path)
    return kuzu.Connection(db)


# ════════════════════════════════════════════════════════════════
# §4. 쿼리 헬퍼 — app.py 가 사용하는 주요 쿼리 함수
# ════════════════════════════════════════════════════════════════

def query_dept_courses(conn: kuzu.Connection, dept_iri: str) -> list[dict]:
    """학과 전체 과목 목록 조회"""
    result = conn.execute(
        "MATCH (c:Course)-[:OFFERED_BY_DEPT]->(d:Department {iri: $di}) "
        "RETURN c.courseCode, c.courseName, c.credits, c.courseType, "
        "c.semOpen1, c.semOpen2, c.yearMin, c.avgGpa, c.description, "
        "c.isGraduateBridge, c.deptIri, "
        "c.graduationCategory, c.countsTowardMajorCredits, c.subArea",
        {"di": dept_iri}
    )
    rows = []
    while result.has_next():
        r = result.get_next()
        rows.append({
            "code": r[0], "name": r[1], "credits": r[2], "type": r[3],
            "semOpen1": r[4], "semOpen2": r[5], "yearMin": r[6],
            "avgGpa": r[7], "description": r[8], "isGraduateBridge": r[9],
            "deptIri": r[10] or dept_iri,
            "graduationCategory":       r[11] or "",
            "countsTowardMajorCredits": r[12] if r[12] is not None else True,
            "subArea":                  r[13] or "",
        })
    return rows


def query_prereq_chain(conn: kuzu.Connection, course_code: str) -> list[dict]:
    """선수과목 전체 체인 (TransitiveProperty 구현 — 1→2→3홉)"""
    result = conn.execute(
        "MATCH (a:Course {courseCode: $code})-[:HAS_PREREQUISITE*1..5]->(p:Course) "
        "RETURN DISTINCT p.courseCode, p.courseName",
        {"code": course_code}
    )
    chain = []
    while result.has_next():
        r = result.get_next()
        chain.append({"code": r[0], "name": r[1]})
    return chain


def query_dept_info(conn: kuzu.Connection, dept_name: str) -> dict | None:
    """학과명으로 학과 정보 조회 (정확 매칭 우선, 없으면 CONTAINS)"""
    # 1순위: 정확 매칭
    result = conn.execute(
        "MATCH (d:Department) WHERE d.name = $name "
        "RETURN d.iri, d.name, d.codePrefix, d.creditsJson LIMIT 1",
        {"name": dept_name}
    )
    if result.has_next():
        r = result.get_next()
        return {
            "iri": r[0], "name": r[1], "codePrefix": r[2],
            "credits": json.loads(r[3]) if r[3] else {},
        }
    # 2순위: CONTAINS (이름 길이 오름차순 → 가장 짧은 = 가장 정확한 매칭 선택)
    result = conn.execute(
        "MATCH (d:Department) WHERE d.name CONTAINS $name "
        "RETURN d.iri, d.name, d.codePrefix, d.creditsJson, len(d.name) AS name_len "
        "ORDER BY name_len ASC LIMIT 1",
        {"name": dept_name}
    )
    if result.has_next():
        r = result.get_next()
        return {
            "iri": r[0], "name": r[1], "codePrefix": r[2],
            "credits": json.loads(r[3]) if r[3] else {},
        }
    return None


def query_combined_majors_for_dept(conn: kuzu.Connection, dept_iri: str) -> list[dict]:
    """특정 학과가 구성 학과인 연계전공 목록"""
    result = conn.execute(
        "MATCH (m:Major)-[:CONSTITUTED_BY]->(d:Department {iri: $di}) "
        "WHERE m.majorType = 'CombinedMajor' "
        "RETURN m.iri, m.name, m.minCredits",
        {"di": dept_iri}
    )
    rows = []
    while result.has_next():
        r = result.get_next()
        rows.append({"iri": r[0], "name": r[1], "minCredits": r[2]})
    return rows


def query_major_credits(conn: kuzu.Connection, major_iri: str) -> dict | None:
    """전공 이수학점 조회"""
    result = conn.execute(
        "MATCH (m:Major {iri: $iri}) "
        "RETURN m.name, m.majorCredits, m.totalCredits, m.majorVariant",
        {"iri": major_iri}
    )
    if result.has_next():
        r = result.get_next()
        return {"name": r[0], "majorCredits": r[1], "totalCredits": r[2], "variant": r[3]}
    return None


def query_code_shares(conn: kuzu.Connection, prefix: str) -> list[dict]:
    """코드쉐어 과목 조회 (SymmetricProperty)"""
    result = conn.execute(
        "MATCH (a:Course)-[:CODE_SHARES_WITH]->(b:Course) "
        "WHERE a.courseCode STARTS WITH $prefix "
        "RETURN a.courseCode, a.courseName, b.courseCode, b.courseName",
        {"prefix": prefix}
    )
    rows, seen = [], set()
    while result.has_next():
        r = result.get_next()
        pair = tuple(sorted([r[0], r[2]]))
        if pair not in seen:
            seen.add(pair)
            rows.append({"a": r[0], "a_name": r[1], "b": r[2], "b_name": r[3]})
    return rows


def query_policy(conn: kuzu.Connection, policy_name: str) -> list[dict]:
    """학사 정책 키워드 조회"""
    result = conn.execute(
        "MATCH (p:AcademicPolicy) WHERE p.name CONTAINS $kw "
        "RETURN p.iri, p.name, p.notes, p.minSemester, p.minCgpa, p.policyType",
        {"kw": policy_name}
    )
    rows = []
    while result.has_next():
        r = result.get_next()
        rows.append({
            "iri": r[0], "name": r[1], "notes": r[2],
            "minSemester": r[3], "minCgpa": r[4], "type": r[5],
        })
    return rows



def query_prereq_map_bulk(conn: kuzu.Connection, course_codes: list[str]) -> dict[str, set[str]]:
    """
    여러 과목의 직접 선수과목을 한 번에 조회.
    자기참조 사이클(code → code) 자동 제거.
    반환: {과목코드: {선수과목코드, ...}}
    """
    if not course_codes:
        return {}
    prereq_map: dict[str, set[str]] = {c: set() for c in course_codes}
    try:
        result = conn.execute(
            "MATCH (a:Course)-[:HAS_PREREQUISITE]->(b:Course) "
            "WHERE a.courseCode IN $codes "
            "RETURN a.courseCode, b.courseCode",
            {"codes": course_codes}
        )
        while result.has_next():
            r = result.get_next()
            src, pre = r[0], r[1]
            if src and pre and src != pre:   # 자기참조 제거
                prereq_map.setdefault(src, set()).add(pre)
    except Exception as e:
        print(f"[PREREQ_BULK] 오류: {e}")
    return prereq_map

# ════════════════════════════════════════════════════════════════
# §4. data_round4 적재 함수
# ════════════════════════════════════════════════════════════════

def _load_job_roles(conn: kuzu.Connection, R4) -> None:
    """JobRole 노드 + FITS_JOB 엣지 + TARGETS_JOB_ROLE 엣지 적재"""
    # JobRole 노드
    for jr in R4.JOB_ROLES:
        _try(conn,
            "MERGE (j:JobRole {iri: $iri}) "
            "SET j.name=$name, j.category=$category, j.keywords=$keywords",
            {"iri": jr["iri"], "name": jr["name"],
             "category": jr["category"], "keywords": jr["keywords"]})
    print(f"[KUZU] JobRole 노드: {len(R4.JOB_ROLES)}개")

    # FITS_JOB 엣지 (Course → JobRole)
    fit_ok = 0
    for fit in R4.COURSE_JOB_FITS:
        _try(conn,
            "MATCH (c:Course {courseCode: $code}), (j:JobRole {iri: $jiri}) "
            "MERGE (c)-[r:FITS_JOB]->(j) SET r.weight=$w",
            {"code": fit["courseCode"], "jiri": fit["jobIri"], "w": fit["weight"]})
        fit_ok += 1
    print(f"[KUZU] FITS_JOB 엣지: {fit_ok}개")

    # TARGETS_JOB_ROLE 엣지 (Major → JobRole)
    for mjt in getattr(R4, "MAJOR_JOB_TARGETS", []):
        _try(conn,
            "MATCH (m:Major {iri: $miri}), (j:JobRole {iri: $jiri}) "
            "MERGE (m)-[:TARGETS_JOB_ROLE]->(j)",
            {"miri": mjt["majorIri"], "jiri": mjt["jobIri"]})


# ════════════════════════════════════════════════════════════════
# §5. 직무 관련 쿼리 함수
# ════════════════════════════════════════════════════════════════

def query_job_role(conn: kuzu.Connection, job_name: str) -> dict | None:
    """
    직무명 키워드로 JobRole 노드 조회.
    이름 완전 일치 → 이름 부분 일치 → keywords 부분 일치 순으로 시도.
    """
    for field, pattern in [
        ("j.name = $q",          job_name),
        ("j.name CONTAINS $q",   job_name),
        ("j.keywords CONTAINS $q", job_name),
    ]:
        try:
            result = conn.execute(
                f"MATCH (j:JobRole) WHERE {field} "
                "RETURN j.iri, j.name, j.category, j.keywords LIMIT 1",
                {"q": pattern}
            )
            if result.has_next():
                r = result.get_next()
                return {"iri": r[0], "name": r[1], "category": r[2], "keywords": r[3]}
        except Exception:
            pass
    return None


def query_courses_by_job(
    conn: kuzu.Connection,
    job_iri: str,
    limit: int = 30,
) -> list[dict]:
    """
    FITS_JOB 엣지를 따라 해당 직무에 적합한 과목을 weight 내림차순으로 반환.
    반환: [{"code", "name", "credits", "type", "dept_iri", "fit_weight"}]
    """
    try:
        result = conn.execute(
            "MATCH (c:Course)-[r:FITS_JOB]->(j:JobRole {iri: $jiri}) "
            "RETURN c.courseCode, c.courseName, c.credits, c.courseType, "
            "       c.dept_iri, r.weight "
            "ORDER BY r.weight DESC LIMIT $lim",
            {"jiri": job_iri, "lim": limit}
        )
        rows = []
        while result.has_next():
            r = result.get_next()
            rows.append({
                "code":       r[0], "name":     r[1],
                "credits":    r[2], "type":     r[3],
                "dept_iri":   r[4], "fit_weight": r[5],
            })
        return rows
    except Exception as e:
        print(f"[QUERY_JOB_COURSES] 오류: {e}")
        return []


# ── CLI: python config.py build ─────────────────────────────────
if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build_kuzu_db(force_rebuild="--force" in sys.argv or "force" in sys.argv)
    elif cmd == "check":
        conn = get_connection()
        for tbl in ["AcademicCluster", "College", "Department", "Major", "Course", "AcademicPolicy"]:
            r = conn.execute(f"MATCH (n:{tbl}) RETURN count(n)").get_next()
            print(f"  {tbl}: {r[0]:,}개")
    else:
        print("Usage: python config.py [build [--force] | check]")
