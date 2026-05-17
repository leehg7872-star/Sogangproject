#!/usr/bin/env python3
"""apply_patches4.py — Apply BIO (생명과학과) patch."""

# ── helpers ──────────────────────────────────────────────────────────
def py_repr(obj):
    if obj is None: return 'None'
    if obj is True: return 'True'
    if obj is False: return 'False'
    if isinstance(obj, str):
        s = obj.replace('\\', '\\\\').replace("'", "\\'")
        return f"'{s}'"
    if isinstance(obj, (int, float)): return repr(obj)
    if isinstance(obj, list):
        return '[' + ', '.join(py_repr(v) for v in obj) + ']'
    if isinstance(obj, dict):
        items = ', '.join(f"{py_repr(k)}: {py_repr(v)}" for k, v in obj.items())
        return '{' + items + '}'
    return repr(obj)


def replace_credits(content, iri, new_credits_dict):
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if f"'iri': '{iri}'" not in line:
            continue
        start = line.find("'credits': {")
        if start == -1:
            print(f"  WARNING: no 'credits' for {iri}")
            continue
        credits_start = start + len("'credits': ")
        depth, j = 0, credits_start
        while j < len(line):
            if line[j] == '{': depth += 1
            elif line[j] == '}':
                depth -= 1
                if depth == 0:
                    credits_end = j + 1; break
            j += 1
        lines[i] = line[:credits_start] + py_repr(new_credits_dict) + line[credits_end:]
        print(f"  [OK] Replaced credits for {iri}")
        break
    return '\n'.join(lines)


def fix_bool_field_by_code(content, code, field, old_val, new_val):
    old_str = f"'{field}': {old_val}"
    new_str = f"'{field}': {new_val}"
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if f"'courseCode': '{code}'" in line:
            if old_str in line:
                lines[i] = line.replace(old_str, new_str, 1)
                return '\n'.join(lines), True
            else:
                print(f"  WARNING: {code} – '{old_str}' not found in line")
                return '\n'.join(lines), False
    print(f"  WARNING: courseCode '{code}' not found")
    return content, False


def add_job_fits(content, fits, label):
    lines = content.split('\n')
    in_list = False
    for i, line in enumerate(lines):
        if 'COURSE_JOB_FITS' in line and '= [' in line:
            in_list = True
        if in_list and line.strip() == ']':
            inserts = []
            for fit in fits:
                cc = fit['courseCode']
                ji = fit['jobIri']
                wt = fit['weight']
                inserts.append(f"    {{'courseCode': '{cc}', 'jobIri': '{ji}', 'weight': {wt}}},")
            lines[i:i] = inserts
            print(f"  [OK] Added {len(fits)} {label} job fits")
            return '\n'.join(lines)
    print("  WARNING: COURSE_JOB_FITS closing ']' not found")
    return content


# ── BIO patch data ───────────────────────────────────────────────────

DEPT_BIO_CREDITS_FULL = {
    # ── 전인교육 (공통) ──
    '교양_공통필수': 11,
    '교양_공통선택_①': 3,
    '교양_공통선택_②': 3,
    '교양_공통선택_③': 3,
    '교양_공통선택_④': 3,
    '교양_전인교육_합계': 23,

    # ── 단일전공 ──
    '단일전공_총학점': 130,
    '단일전공_전공학점': 62,
    '단일전공_전공입문_최소학점': 22,
    '단일전공_필수_최소학점': 18,
    '단일전공_선택_최소학점': 44,
    '단일전공_선택_주석': '※ 단일전공 전공선택 44학점에는 세부 이수 조건 관련 주석 있음 (요람 참조).',

    # ── 다전공 ──
    '다전공_총학점': 130,
    '다전공_전공학점': 36,
    '다전공_전공입문_최소학점': 22,
    '다전공_필수_최소학점': 18,
    '다전공_선택_최소학점': 18,

    # ── 교직과정 ──
    '교직과정_총학점': 130,
    '교직과정_전공학점': 65,
    '교직과정_전공입문_최소학점': 22,
    '교직과정_필수_최소학점': 18,
    '교직과정_선택_최소학점': 47,
    '교직과정_선택_주석': '※ 교직과정 전공선택 47학점에는 EDUS981·EDUS982·EDUS983 교직교육 3과목 포함.',

    # ── SCIENCE기반 자유전공학부 ──
    'SCIENCE자유전공_전공입문_합계': 18,
    'SCIENCE자유전공_입문_구성': {
        'SCI_필수_5과목_15학점': [
            'SCI1011 과학수학', 'SCI1012 통합물리', 'SCI1013 통합화학',
            'SCI1014 통합생물학', 'SCI1021 과학도를 위한 선형대수',
        ],
        '일반실험_택3_3학점': [
            'PHY1101 일반물리실험Ⅰ', 'PHY1102 일반물리실험Ⅱ',
            'CHM1051 일반화학실험Ⅰ', 'CHM1052 일반화학실험Ⅱ',
            'BIO1105 일반생물학실험Ⅰ', 'BIO1106 일반생물학실험Ⅱ',
        ],
        '비고': 'SCIENCE기반 자유전공학부 학생은 위 구성으로 전공입문 18학점 이수.',
    },

    # ── 규정 주석 ──
    '총학점_130_규정': '본 전공의 졸업 총학점은 130학점으로, 본 프로젝트의 다른 학과(126)와 다름.',
    'PreMajor_미포함규정': '※ 전공입문교과목은 필수로 이수해야 하나, 전공 학점에는 포함되지 않음.',
    '공통선택_④STS2005_의무규정': '※ 공통선택 ④ 인간과 과학 & AI 영역 중 미적분학(STS2005)을 필수 선택. (SCIENCE기반 자유전공학부 학생 제외)',

    # ── 전공입문 구성 (22학점) ──
    '전공입문_구성': {
        '공통필수_11학점': {
            '과목': [
                'BIO1101 일반생물학Ⅰ (3학점)', 'BIO1102 일반생물학Ⅱ (3학점)',
                'BIO1105 일반생물학실험Ⅰ (1학점)', 'BIO1106 일반생물학실험Ⅱ (1학점)',
                'STS2006 미적분학Ⅱ (3학점)',
            ],
            '비고': '모든 전공 시나리오 공통 필수 이수',
        },
        '공통선택_11학점_옵션A': {
            '구성': 'PHY 4과목(8학점) + CHM 1과목 택1(3학점) = 11학점',
            'PHY_필수_4과목_8학점': [
                'PHY1001 일반물리Ⅰ (3학점)', 'PHY1002 일반물리Ⅱ (3학점)',
                'PHY1101 일반물리실험Ⅰ (1학점)', 'PHY1102 일반물리실험Ⅱ (1학점)',
            ],
            'CHM_택1_3학점': ['CHM1001 일반화학Ⅰ', 'CHM1002 일반화학Ⅱ'],
            '비고': '물리 중심 선택: 일반물리Ⅰ·Ⅱ·실험Ⅰ·Ⅱ 전체 + 일반화학Ⅰ 또는 Ⅱ 중 1과목',
        },
        '공통선택_11학점_옵션B': {
            '구성': 'CHM 4과목(8학점) + PHY 1과목 택1(3학점) = 11학점',
            'CHM_필수_4과목_8학점': [
                'CHM1001 일반화학Ⅰ (3학점)', 'CHM1002 일반화학Ⅱ (3학점)',
                'CHM1051 일반화학실험Ⅰ (1학점)', 'CHM1052 일반화학실험Ⅱ (1학점)',
            ],
            'PHY_택1_3학점': ['PHY1001 일반물리Ⅰ', 'PHY1002 일반물리Ⅱ'],
            '비고': '화학 중심 선택: 일반화학Ⅰ·Ⅱ·실험Ⅰ·Ⅱ 전체 + 일반물리Ⅰ 또는 Ⅱ 중 1과목',
        },
        '합계_주석': '공통필수 11학점 + 공통선택(옵션A 또는 B) 11학점 = 22학점. 둘 중 하나 선택',
    },

    # ── 전공필수 구성 (18학점) ──
    '전공필수_구성': {
        '필수_6과목_18학점': {
            'BIO2121': '현대생물학실험Ⅰ (3학점)',
            'BIO2122': '현대생물학실험Ⅱ (3학점)',
            'BIO2131': '생화학Ⅰ (3학점)',
            'BIO2132': '생화학Ⅱ (3학점)',
            'BIO3123': '현대생물학실험Ⅲ (3학점)',
            'BIO3124': '현대생물학실험Ⅳ (3학점)',
        },
        '비고': '다전공·단일전공·교직과정 모두 해당. 2018년 이후 입학자 적용 기준.',
        '필수_합계': 18,
    },

    # ── 기타이수요건 ──
    '기타이수요건': {
        '전공학점_미포함_과목': ['BIO4203 생명과학 특허와 기술이전'],
        '비고_BIO4203_동일과목': '생명과학 특허와 기술이전(BIO4203)은 PHY4023·CHM4203 등 타학과 동일과목과 동일하게 처리.',
        '특수연구_응용바이오_규정': {
            'BIO4921': '특수연구 — 전공학점으로 인정',
            'BIO4931': '응용바이오기술실험 — 전공학점으로 인정',
            '비고': 'BIO4921(특수연구)과 BIO4931(응용바이오기술실험) 중복 이수 시 1과목만 졸업학점 인정.',
        },
        '교직_추가의무': ['EDUS981 교육학개론', 'EDUS982 교육심리', 'EDUS983 교육과정'],
        '교직_전공학점_25학점_주석': '교직 이수자는 위 EDUS 3과목 포함 전공선택 47학점 이수.',
    },

    # ── 로드맵 ──
    'Road_Map': {
        '구조_주석': '요람 전공교육과정 이수 로드맵 — 학년별 권장 과목',
        '1학년': {
            '전공입문교과': [
                '일반화학Ⅰ (CHM1001) 또는 일반물리학Ⅰ (PHY1001)',
                '일반화학실험Ⅰ (CHM1051) 또는 일반물리학실험Ⅰ (PHY1101)',
                '일반생물학Ⅰ (BIO1101)', '일반생물학실험Ⅰ (BIO1105)',
            ],
            '전공필수': ['생화학Ⅰ (BIO2131)', '현대생물학실험Ⅰ (BIO2121)'],
            '전공선택': ['세포학 (BIO2141)', '생명유기화학 (BIO2311)', '숙주미생물 상호작용 (BIO2350)', '식물생명과학 (BIO2522)'],
        },
        '2학년': {
            '전공입문교과': [
                '일반화학Ⅱ (CHM1002) 또는 일반물리학Ⅱ (PHY1002)',
                '일반화학실험Ⅱ (CHM1052) 또는 일반물리학실험Ⅱ (PHY1102)',
                '일반생물학Ⅱ (BIO1102)', '일반생물학실험Ⅱ (BIO1106)',
                '미적분학Ⅱ (STS2006)',
            ],
            '전공필수': ['생화학Ⅱ (BIO2132)', '현대생물학실험Ⅱ (BIO2122)'],
            '전공선택': ['분자생물학 (BIO2151)', '환경과학론 (BIO2701)', '첨단 생명과학기술(탐구공동체) (BIO2111)'],
        },
        '3학년': {
            '전공필수': ['현대생물학실험Ⅲ (BIO3123)'],
            '전공선택': [
                '유전자클로닝개론 (BIO2601)', '생명공학개론 (BIO3212)',
                '발생학 (BIO3311)', '식물발달생물학 (BIO4521)',
            ],
        },
        '4학년': {
            '전공필수': ['현대생물학실험Ⅳ (BIO3124)'],
            '전공선택': [
                '면역학 (BIO4351)', '환경과학론 (BIO2701)', '유전학 (BIO3161)',
                '미생물학 (BIO3711)', '생물통계학 (BIO4251)',
                '생명과학특허와기술이전 (BIO4203)', '식물분자생리학 (BIOG511)',
                '동물대사학 (BIOG322)', '미생물생리학 (BIO3712)',
                '생명과학현장실습 (BIO4100)', '인체생리학 (BIO4321)',
                '암생물학 (BIO4252)', '응용바이오기술실험 (BIO4931)',
                '구조생물학 (BIOG241)', '생물리학 (BIOG232)',
                '식물유전공학 (BIO4911)', '산업미생물학 (BIO2511)',
                '신경생물학 (BIO4331)', '고급분자생물학 (BIOG153)',
                '분자세포생물학 (BIO4441)', '분자세포종양학 (BIO4721)',
                '바이오텍의기술사업화 종합설계 (BIOG001)', '특수연구 (BIO4921)',
            ],
        },
        '비고': '위 로드맵은 권장 학기일 뿐 강제 규칙 아님. 필수 6과목 18학점은 반드시 충족.',
    },
}


# ── countsTowardMajorCredits True → False ────────────────────────────
# 전공입문: BIO1101/1102/1105/1106 (입문과목은 전공학점 미포함)
# 기타이수요건 제외: BIO4203 (전공학점 미포함)
COUNTS_FALSE = ['BIO1101', 'BIO1102', 'BIO1105', 'BIO1106', 'BIO4203']

# ── COURSE_JOB_FITS ──────────────────────────────────────────────────
BIO_COURSE_JOB_FITS = [
    # 전공필수 — 현대생물학실험 계열
    {"courseCode": "BIO2121", "jobIri": "Job_PM",        "weight": 0.60},
    {"courseCode": "BIO2121", "jobIri": "Job_데이터분석", "weight": 0.55},
    {"courseCode": "BIO2122", "jobIri": "Job_PM",        "weight": 0.60},
    {"courseCode": "BIO2122", "jobIri": "Job_데이터분석", "weight": 0.55},
    {"courseCode": "BIO3123", "jobIri": "Job_PM",        "weight": 0.65},
    {"courseCode": "BIO3123", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "BIO3124", "jobIri": "Job_PM",        "weight": 0.65},
    {"courseCode": "BIO3124", "jobIri": "Job_데이터분석", "weight": 0.60},

    # 전공필수 — 생화학
    {"courseCode": "BIO2131", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "BIO2131", "jobIri": "Job_AI엔지니어", "weight": 0.60},
    {"courseCode": "BIO2132", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "BIO2132", "jobIri": "Job_AI엔지니어", "weight": 0.60},

    # 분자·세포·유전 계열
    {"courseCode": "BIO2111", "jobIri": "Job_AI엔지니어", "weight": 0.65},
    {"courseCode": "BIO2111", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "BIO2141", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "BIO2141", "jobIri": "Job_AI엔지니어", "weight": 0.60},
    {"courseCode": "BIO2151", "jobIri": "Job_AI엔지니어", "weight": 0.75},
    {"courseCode": "BIO2151", "jobIri": "Job_데이터분석", "weight": 0.70},
    {"courseCode": "BIO2601", "jobIri": "Job_AI엔지니어", "weight": 0.75},
    {"courseCode": "BIO2601", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "BIO3161", "jobIri": "Job_AI엔지니어", "weight": 0.80},
    {"courseCode": "BIO3161", "jobIri": "Job_데이터분석", "weight": 0.75},
    {"courseCode": "BIO4441", "jobIri": "Job_AI엔지니어", "weight": 0.80},
    {"courseCode": "BIO4441", "jobIri": "Job_데이터분석", "weight": 0.75},
    {"courseCode": "BIO4721", "jobIri": "Job_AI엔지니어", "weight": 0.75},
    {"courseCode": "BIO4721", "jobIri": "Job_데이터분석", "weight": 0.70},
    {"courseCode": "BIOG153", "jobIri": "Job_AI엔지니어", "weight": 0.85},
    {"courseCode": "BIOG153", "jobIri": "Job_데이터분석", "weight": 0.80},

    # 생화학·생리학 계열
    {"courseCode": "BIO2311", "jobIri": "Job_반도체",    "weight": 0.60},
    {"courseCode": "BIO2311", "jobIri": "Job_데이터분석", "weight": 0.55},
    {"courseCode": "BIO4321", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "BIO4321", "jobIri": "Job_AI엔지니어", "weight": 0.60},
    {"courseCode": "BIO4331", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "BIO4331", "jobIri": "Job_AI엔지니어", "weight": 0.65},
    {"courseCode": "BIOG322", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "BIOG322", "jobIri": "Job_AI엔지니어", "weight": 0.60},

    # 미생물학 계열
    {"courseCode": "BIO2350", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "BIO2350", "jobIri": "Job_AI엔지니어", "weight": 0.55},
    {"courseCode": "BIO2511", "jobIri": "Job_기획",      "weight": 0.70},
    {"courseCode": "BIO2511", "jobIri": "Job_컨설팅",    "weight": 0.60},
    {"courseCode": "BIO3711", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "BIO3711", "jobIri": "Job_AI엔지니어", "weight": 0.60},
    {"courseCode": "BIO3712", "jobIri": "Job_데이터분석", "weight": 0.65},

    # 면역·종양학
    {"courseCode": "BIO4351", "jobIri": "Job_데이터분석", "weight": 0.70},
    {"courseCode": "BIO4351", "jobIri": "Job_AI엔지니어", "weight": 0.70},
    {"courseCode": "BIO4252", "jobIri": "Job_데이터분석", "weight": 0.70},
    {"courseCode": "BIO4252", "jobIri": "Job_AI엔지니어", "weight": 0.70},

    # 생물통계학 — 데이터 분석 핵심
    {"courseCode": "BIO4251", "jobIri": "Job_데이터분석", "weight": 0.95},
    {"courseCode": "BIO4251", "jobIri": "Job_AI엔지니어", "weight": 0.80},

    # 구조생물학·생물리학
    {"courseCode": "BIOG241", "jobIri": "Job_반도체",    "weight": 0.65},
    {"courseCode": "BIOG241", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "BIOG241", "jobIri": "Job_AI엔지니어", "weight": 0.65},
    {"courseCode": "BIOG232", "jobIri": "Job_반도체",    "weight": 0.75},
    {"courseCode": "BIOG232", "jobIri": "Job_데이터분석", "weight": 0.65},

    # 식물생명과학 계열
    {"courseCode": "BIO2522", "jobIri": "Job_데이터분석", "weight": 0.55},
    {"courseCode": "BIO3311", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "BIO4521", "jobIri": "Job_데이터분석", "weight": 0.55},
    {"courseCode": "BIO4911", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "BIO4911", "jobIri": "Job_AI엔지니어", "weight": 0.65},
    {"courseCode": "BIOG511", "jobIri": "Job_데이터분석", "weight": 0.60},

    # 환경·발생
    {"courseCode": "BIO2701", "jobIri": "Job_컨설팅",    "weight": 0.60},
    {"courseCode": "BIO2701", "jobIri": "Job_기획",      "weight": 0.55},

    # 생명공학개론 / 기술사업화
    {"courseCode": "BIO3212", "jobIri": "Job_기획",      "weight": 0.75},
    {"courseCode": "BIO3212", "jobIri": "Job_컨설팅",    "weight": 0.65},
    {"courseCode": "BIOG001", "jobIri": "Job_기획",      "weight": 0.85},
    {"courseCode": "BIOG001", "jobIri": "Job_컨설팅",    "weight": 0.80},
    {"courseCode": "BIOG001", "jobIri": "Job_PM",        "weight": 0.75},

    # 현장실습 / 특수연구 / 응용바이오
    {"courseCode": "BIO4100", "jobIri": "Job_기획",      "weight": 0.70},
    {"courseCode": "BIO4100", "jobIri": "Job_PM",        "weight": 0.65},
    {"courseCode": "BIO4921", "jobIri": "Job_PM",        "weight": 0.85},
    {"courseCode": "BIO4921", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "BIO4931", "jobIri": "Job_PM",        "weight": 0.80},
    {"courseCode": "BIO4931", "jobIri": "Job_반도체",    "weight": 0.60},

    # 특허·기술이전 / 진로설계
    {"courseCode": "BIO4203", "jobIri": "Job_컨설팅",    "weight": 0.70},
    {"courseCode": "BIO4203", "jobIri": "Job_기획",      "weight": 0.65},
    {"courseCode": "BIO3100", "jobIri": "Job_기획",      "weight": 0.65},
    {"courseCode": "BIO3100", "jobIri": "Job_교육",      "weight": 0.60},
]


# ── MAIN ─────────────────────────────────────────────────────────────
BASE = '/home/user/Sogangproject'

# STEP 1: data_round1.py — expand Dept_BIO credits
print("=== STEP 1: data_round1.py ===")
with open(f'{BASE}/data_round1.py', encoding='utf-8') as f:
    r1 = f.read()
r1 = replace_credits(r1, 'Dept_BIO', DEPT_BIO_CREDITS_FULL)
with open(f'{BASE}/data_round1.py', 'w', encoding='utf-8') as f:
    f.write(r1)
print("data_round1.py written.\n")

# STEP 2: data_round2.py — fix countsTowardMajorCredits
print("=== STEP 2: data_round2.py ===")
with open(f'{BASE}/data_round2.py', encoding='utf-8') as f:
    r2 = f.read()

print("  Fixing countsTowardMajorCredits: True → False (5 courses)...")
for code in COUNTS_FALSE:
    r2, ok = fix_bool_field_by_code(r2, code, 'countsTowardMajorCredits', 'True', 'False')
    if ok:
        print(f"    {code}: countsTowardMajorCredits True → False")

with open(f'{BASE}/data_round2.py', 'w', encoding='utf-8') as f:
    f.write(r2)
print("data_round2.py written.\n")

# STEP 3: data_round4.py — add BIO job fits
print("=== STEP 3: data_round4.py ===")
with open(f'{BASE}/data_round4.py', encoding='utf-8') as f:
    r4 = f.read()
r4 = add_job_fits(r4, BIO_COURSE_JOB_FITS, 'BIO')
with open(f'{BASE}/data_round4.py', 'w', encoding='utf-8') as f:
    f.write(r4)
print("data_round4.py written.\n")

print("=== ALL BIO PATCHES APPLIED ===")
