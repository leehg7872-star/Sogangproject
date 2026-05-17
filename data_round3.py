"""
data_round3.py — 3라운드 추출 데이터
  - 코드쉐어 관계 (codeSharesWith / SymmetricProperty)
  - 대체인정 관계 (equivalentTo / SymmetricProperty)
  - 학·석사 공통과목 (GraduateBridgeCourse)
출처: 서강대학교 2025학년도 요람
생성일: 2026-04-27
"""

# ════════════════════════════════════════════════════════════════
# 코드쉐어 (CodeSharedCourse + codeSharesWith)
# OWL 매핑: SymmetricProperty
# Neo4j 처리: 양방향 관계 [:CODE_SHARES_WITH]
# ════════════════════════════════════════════════════════════════
CODE_SHARES = [
    {"code_a": "AIE2050", "code_b": "CSE2003"},
    {"code_a": "AIE2051", "code_b": "CSE2035"},
    {"code_a": "AIE2070", "code_b": "CSE3006"},
    {"code_a": "AIE3010", "code_b": "CSE4130"},
    {"code_a": "AIE3050", "code_b": "CSE3080"},
    {"code_a": "AIE3051", "code_b": "CSE3081"},
    {"code_a": "AIE3052", "code_b": "CSE3040"},
    {"code_a": "AIE3053", "code_b": "CSE3015"},
    {"code_a": "AIE3054", "code_b": "CSE3030"},
    {"code_a": "AIE3091", "code_b": "CSE3013"},
    {"code_a": "AIE3092", "code_b": "CSE3016"},
    {"code_a": "AIE4010", "code_b": "CSE4185"},
    {"code_a": "AIE4012", "code_b": "CSE4170"},
    {"code_a": "AIE4014", "code_b": "CSE4014"},
    {"code_a": "AIE4050", "code_b": "CSE4100"},
    {"code_a": "AIE4051", "code_b": "CSE4010"},
    {"code_a": "AIE4052", "code_b": "CSE4175"},
    {"code_a": "AIE4053", "code_b": "CSE4070"},
    {"code_a": "AIE4054", "code_b": "CSE4060"},
    {"code_a": "AIE4055", "code_b": "CSE4110"},
    {"code_a": "AIE4056", "code_b": "CSE4085"},
    {"code_a": "AIEG101", "code_b": "CSEG516"},
    {"code_a": "AIEG102", "code_b": "CSEG416"},
    {"code_a": "AIEG105", "code_b": "CSEG418"},
    {"code_a": "AIEG107", "code_b": "CSEG311"},
    {"code_a": "AIEG108", "code_b": "CSEG450"},
    {"code_a": "AIEG114", "code_b": "CSEG312"},
    {"code_a": "AIEG115", "code_b": "CSEG437"},
    {"code_a": "AIEG116", "code_b": "CSEG414"},
    {'code_a': 'ECO2003', 'code_b': 'TIS1005', 'note': '경제수리기초 ↔ Mathematical Methods for International Commerce (전공입문)'},
    {'code_a': 'ECO2004', 'code_b': 'TIC2001', 'note': '경제통계학 ↔ Statistics for International Commerce (전공필수)'},
    {'code_a': 'MGT2002', 'code_b': 'TIC2001', 'note': '경영통계학 ↔ Statistics for International Commerce (전공필수)'},
    {'code_a': 'ECO2006', 'code_b': 'TIC2002', 'note': '미시경제학 ↔ Microeconomics for International Commerce (전공필수)'},
    {'code_a': 'ECO2007', 'code_b': 'TIC2003', 'note': '거시경제학 ↔ Macroeconomics for International Commerce (전공필수선택)'},
    {'code_a': 'ECO3017', 'code_b': 'TIC2005', 'note': '국제경제학 ↔ International Economics (전공필수선택)'},
    {'code_a': 'MGT2003', 'code_b': 'TIC2006', 'note': '회계학원론 ↔ Principles of Accounting for International Commerce (전공필수선택)'},
    {'code_a': 'MGT3006', 'code_b': 'TIC2007', 'note': '마케팅원론 ↔ Principles of Marketing for International Commerce (전공필수선택)'},
    {'code_a': 'MGT3004', 'code_b': 'TIC2008', 'note': '재무관리 ↔ Financial Management (전공필수선택)'},
    {'code_a': 'ECO2009', 'code_b': 'TIC3002', 'note': '계량경제학I ↔ Research Method of Data Science (전공필수선택)'},
    {'code_a': 'MGT3007', 'code_b': 'TIC3004', 'note': '국제경영론 ↔ International Business (전공필수선택)'},
    {'code_a': 'MGT4301', 'code_b': 'TIC3005', 'note': '투자론 ↔ Investment Analysis (전공필수선택)'},
    {'code_a': 'MGT4302', 'code_b': 'TIC3006', 'note': '기업재무론 ↔ Corporate Finance (전공필수선택)'},
    {'code_a': 'ECO3010', 'code_b': 'TIC4003', 'note': '국제무역론 ↔ International Trade Theory and Policy (전공선택)'},
    {'code_a': 'ECO3011', 'code_b': 'TIC4004', 'note': '국제금융론 ↔ International Finance Theory and Policy (전공선택)'},
    {'code_a': 'MGT4510', 'code_b': 'TIC4015', 'note': '국제마케팅론 ↔ International Marketing (전공선택)'},
]

# 코드쉐어 관계 수: 29쌍
# 주요 패턴: 인공지능학과(AIE) ↔ 컴퓨터공학과(CSE)
# 적재 시 [:CODE_SHARES_WITH] 관계를 양방향으로 생성하면
# OWL SymmetricProperty 의미를 보존할 수 있음

# ════════════════════════════════════════════════════════════════
# 대체인정 (equivalentTo)
# OWL 매핑: SymmetricProperty equivalentTo
# Neo4j 처리: 양방향 관계 [:EQUIVALENT_TO]
# ════════════════════════════════════════════════════════════════
SUBSTITUTIONS = [
    {
        "dept_iri":      "Dept_HIS",
        "outside_code":  "REL3022",
        "our_code":      "HIS3041",
        "category":      "전공일반",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_HIS",
        "outside_code":  "PHI3034",
        "our_code":      "HIS3056",
        "category":      "전공일반",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_HIS",
        "outside_code":  "PHI3035",
        "our_code":      "HIS3056",
        "category":      "전공일반",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_HIS",
        "outside_code":  "PHI3036",
        "our_code":      "HIS3056",
        "category":      "전공일반",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_HIS",
        "outside_code":  "PHI3003",
        "our_code":      "HIS3065",
        "category":      "전공일반",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_HIS",
        "outside_code":  "EUR3106",
        "our_code":      "HIS3036",
        "category":      "전공일반",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_HIS",
        "outside_code":  "ECO2011",
        "our_code":      "HIS3063",
        "category":      "전공일반",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_CHI",
        "outside_code":  "POL4146",
        "our_code":      "CHI3036",
        "category":      "전공일반",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_CHI",
        "outside_code":  "MGT4613",
        "our_code":      "CHI3039",
        "category":      "전공일반",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_EEE",
        "outside_code":  "PHY2004",
        "our_code":      "EEE2101",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_EEE",
        "outside_code":  "CSE4010",
        "our_code":      "EEE2135",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_EEE",
        "outside_code":  "PHY1102",
        "our_code":      "EEE1002",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_EEE",
        "outside_code":  "STS2006",
        "our_code":      "EEE1002",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_EEE",
        "outside_code":  "MAT2110",
        "our_code":      "EEE1002",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_EEE",
        "outside_code":  "SSE3201",
        "our_code":      "EEE3201",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_CSE",
        "outside_code":  "EEE2135",
        "our_code":      "CSE3015",
        "category":      "전공일반",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_CSE",
        "outside_code":  "EEE3178",
        "our_code":      "CSE4010",
        "category":      "전공심화­",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "ECO2004",
        "our_code":      "TIC2001",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "ECO2006",
        "our_code":      "TIC2002",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "ECO2007",
        "our_code":      "TIC2003",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "ECO3017",
        "our_code":      "TIC2005",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "ECO2009",
        "our_code":      "TIC3002",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "ECO3010",
        "our_code":      "TIC4003",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "ECO3011",
        "our_code":      "TIC4004",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "MGT2002",
        "our_code":      "TIC2001",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "MGT2003",
        "our_code":      "TIC2006",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "MGT3006",
        "our_code":      "TIC2007",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "MGT3004",
        "our_code":      "TIC2008",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "MGT3007",
        "our_code":      "TIC3004",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "MGT4301",
        "our_code":      "TIC3005",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "MGT4302",
        "our_code":      "TIC3006",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_TIC",
        "outside_code":  "MGT4510",
        "our_code":      "TIC4015",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_AAS",
        "outside_code":  "GKS3001",
        "our_code":      "AAS2010",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_AAS",
        "outside_code":  "GKS4006",
        "our_code":      "AAS4002",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_AAS",
        "outside_code":  "CHI4009",
        "our_code":      "AAS4016",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
    {
        "dept_iri":      "Dept_AAS",
        "outside_code":  "CHI4014",
        "our_code":      "AAS2007",
        "category":      "Unknown",  # 전공일반/전공심화 등
    },
]

# 대체인정 관계 수: 36개
# 적재 의미: 학과 IRI에서 our_code를 outside_code로 대체 인정 가능

# ════════════════════════════════════════════════════════════════
# 학·석사 공통과목 (GraduateBridgeCourse)
# OWL 매핑: Course 하위 클래스 GraduateBridgeCourse
# Neo4j 처리: 노드 라벨 :GraduateBridgeCourse 추가 부여
# ════════════════════════════════════════════════════════════════
GRADUATE_BRIDGE_COURSES = {
    "Dept_AAT": ["AATG001", "AATG009", "AATG010", "AATG013", "AATG015", "AATG100", "AATG102", "AATG104", "AATG106", "AATG800"],
    "Dept_AIE": ["AIEG101", "AIEG102", "AIEG103", "AIEG104", "AIEG105", "AIEG106", "AIEG107", "AIEG108", "AIEG109", "AIEG110", "AIEG111", "AIEG112", "AIEG113", "AIEG114", "AIEG115", "AIEG116"],
    "Dept_AMC": ["AMCG001"],
    "Dept_BIO": ["BIOG001", "BIOG153", "BIOG232", "BIOG241", "BIOG322", "BIOG511"],
    "Dept_CBE": ["CBEG001", "CBEG002", "CBEG004", "CBEG006", "CBEG007", "CBEG008", "CBEG009", "CBEG010", "CBEG011", "CBEG012", "CBEG013", "CBEG014", "CBEG015", "CBEG016", "CBEG017"],
    "Dept_CHI": ["CHIG001", "CHIG002", "CHIG003", "CHIG004", "CHIG005", "CHIG006", "CHIG007", "CHIG008", "CHIG009"],
    "Dept_CHM": ["CHMG101", "CHMG201", "CHMG202", "CHMG301", "CHMG302", "CHMG401", "CHMG402", "CHMG501", "CHMG502", "CHMG601"],
    "Dept_CSE": ["CSEG109", "CSEG311", "CSEG312", "CSEG321", "CSEG414", "CSEG416", "CSEG418", "CSEG437", "CSEG450", "CSEG463", "CSEG483", "CSEG494", "CSEG501", "CSEG516", "CSEG601"],
    "Dept_ECO": ["ECOG010", "ECOG011", "ECOG020", "ECOG021", "ECOG030", "ECOG040", "ECOG050", "ECOG051"],
    "Dept_EEE": ["EEEG272", "EEEG273", "EEEG274", "EEEG275", "EEEG477"],
    "Dept_ENG": ["ENGG002", "ENGG003", "ENGG004", "ENGG005", "ENGG006", "ENGG007", "ENGG008", "ENGG204", "ENGG205", "ENGG215", "ENGG230", "ENGG231", "ENGG235", "ENGG236", "ENGG282", "ENGG284"],
    "Dept_EUR": ["EURG201", "EURG202", "EURG203", "EURG208", "EURG211", "EURG212", "EURG301", "EURG302", "EURG303", "EURG304", "EURG305", "EURG307", "EURG308"],
    "Dept_GKE": ["GKEG001"],
    "Dept_GKS": ["GKSG002", "GKSG003", "GKSG004", "GKSG005", "GKSG007", "GKSG008", "GKSG009", "GKSG010", "GKSG011", "GKSG012"],
    "Dept_HIS": ["HISG001", "HISG002", "HISG003", "HISG004", "HISG104", "HISG105", "HISG106", "HISG202", "HISG205", "HISG305"],
    "Dept_JAS": ["JASG101", "JASG102", "JASG201", "JASG202", "JASG203", "JASG204"],
    "Dept_KOR": ["KORG001", "KORG002", "KORG011", "KORG012", "KORG021", "KORG022"],
    "Dept_MAE": ["MAEG302", "MAEG401", "MAEG402", "MAEG403", "MAEG404"],
    "Dept_MAT": ["MATG110", "MATG210"],
    "Dept_MEE": ["MEEG005", "MEEG006", "MEEG007", "MEEG008", "MEEG009", "MEEG017", "MEEG018", "MEEG019", "MEEG022", "MEEG032", "MEEG041", "MEEG042", "MEEG052", "MEEG062", "MEEG103", "MEEG104", "MEEG111", "MEEG112", "MEEG114", "MEEG121"],
    "Dept_MGT": ["MGTG011", "MGTG014", "MGTG109", "MGTG205", "MGTG244", "MGTG313", "MGTG315", "MGTG505", "MGTG509", "MGTG603", "MGTG610", "MGTG613", "MGTG704", "MGTG705", "MGTG706", "MGTG707", "MGTG807"],
    "Dept_PHI": ["PHIG081", "PHIG082", "PHIG083", "PHIG084", "PHIG085", "PHIG086", "PHIG087"],
    "Dept_PHY": ["PHYG001", "PHYG003", "PHYG004", "PHYG005", "PHYG006"],
    "Dept_POL": ["POLG224", "POLG301", "POLG302", "POLG532"],
    "Dept_PSY": ["PSYG001", "PSYG002", "PSYG003", "PSYG004", "PSYG006"],
    "Dept_REL": ["RELG001", "RELG002", "RELG004", "RELG005", "RELG006"],
    "Dept_SOC": ["SOCG005", "SOCG007", "SOCG009", "SOCG010", "SOCG011", "SOCG012", "SOCG013", "SOCG015", "SOCG016", "SOCG017", "SOCG018"],
}

# 학·석사 공통과목 총 238개 (27개 학과)
# data_round2.py의 COURSES에 이미 포함된 코드들의 라벨을 강화하는 데 사용
# Neo4j 적재 시: data_round2의 Course 노드에 :GraduateBridgeCourse 추가 라벨 부여

# ════════════════════════════════════════════════════════════════
# 메타 정보
# ════════════════════════════════════════════════════════════════
METADATA = {
    "codeshare_pairs":     29,
    "substitution_pairs":  36,
    "graduate_bridges":    238,
    "bridge_departments":  27,
    "source": "서강대학교 2025학년도 요람",
    "extracted_at": "2026-04-27",
    "owl_mapping": {
        "CODE_SHARES":            "codeSharesWith (SymmetricProperty)",
        "SUBSTITUTIONS":          "equivalentTo (SymmetricProperty)",
        "GRADUATE_BRIDGE_COURSES": "GraduateBridgeCourse (Course 하위 클래스)",
    },
}