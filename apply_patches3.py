#!/usr/bin/env python3
"""apply_patches3.py — Apply CHM (화학과) patch."""

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


def fix_str_field_by_code(content, code, field, old_val, new_val):
    old_str = f"'{field}': '{old_val}'"
    new_str = f"'{field}': '{new_val}'"
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


# ── CHM patch data ───────────────────────────────────────────────────

DEPT_CHM_CREDITS_FULL = {
    # ── 전인교육 (공통) ──
    '교양_공통필수': 11,
    '교양_공통선택_①': 3,
    '교양_공통선택_②': 3,
    '교양_공통선택_③': 3,
    '교양_공통선택_④': 3,
    '교양_전인교육_합계': 23,

    # ── 단일전공 ──
    '단일전공_총학점': 130,
    '단일전공_전공학점': 64,
    '단일전공_전공입문_최소학점': 22,
    '단일전공_필수_최소학점': 26,
    '단일전공_필수선택_최소학점': 4,
    '단일전공_선택_최소학점': 34,

    # ── 다전공 ──
    '다전공_총학점': 130,
    '다전공_전공학점': 45,
    '다전공_전공입문_최소학점': 22,
    '다전공_필수_최소학점': 26,
    '다전공_필수선택_최소학점': 4,
    '다전공_선택_최소학점': 15,

    # ── 교직과정 ──
    '교직과정_총학점': 130,
    '교직과정_전공학점': 54,
    '교직과정_전공입문_최소학점': 22,
    '교직과정_필수_최소학점': 26,
    '교직과정_필수선택_최소학점': 4,
    '교직과정_선택_최소학점': 24,

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

    # ── 전공입문 구성 ──
    '전공입문_구성': {
        '공통필수_11학점': {
            '과목': [
                'CHM1001 일반화학Ⅰ (3학점)', 'CHM1002 일반화학Ⅱ (3학점)',
                'CHM1051 일반화학실험Ⅰ (1학점)', 'CHM1052 일반화학실험Ⅱ (1학점)',
                'STS2006 미적분학Ⅱ (3학점)',
            ],
            '비고': '모든 전공 시나리오 공통 필수 이수',
        },
        '공통선택_단일전공_11학점': {
            '과목': [
                'PHY1001 일반물리Ⅰ', 'PHY1002 일반물리Ⅱ',
                'PHY1101 일반물리실험Ⅰ', 'PHY1102 일반물리실험Ⅱ',
                'BIO1101 일반생물학Ⅰ', 'BIO1102 일반생물학Ⅱ',
                'BIO1105 일반생물학실험Ⅰ', 'BIO1106 일반생물학실험Ⅱ',
            ],
            '타전공과목_인정한도': '최대 3학점 (자연과학부 및 공학부 전공 과목)',
            '비고': '단일전공: 공통필수 11학점 + 공통선택 11학점 = 22학점',
        },
        '공통선택_다전공_교직_11학점': {
            '과목': [
                'PHY1001 일반물리Ⅰ', 'PHY1002 일반물리Ⅱ',
                'PHY1101 일반물리실험Ⅰ', 'PHY1102 일반물리실험Ⅱ',
                'BIO1101 일반생물학Ⅰ', 'BIO1102 일반생물학Ⅱ',
                'BIO1105 일반생물학실험Ⅰ', 'BIO1106 일반생물학실험Ⅱ',
            ],
            '타전공과목_인정한도': '최대 9학점 (자연과학부 및 공학부 전공 과목)',
            '비고': '다전공/교직: 공통필수 11학점 + 공통선택 11학점 = 22학점',
        },
    },

    # ── 전공필수 구성 ──
    '전공필수_구성': {
        '필수_10과목_26학점': {
            'CHM2101': '분석화학 (3학점)',
            'CHM2151': '분석화학실험 (2학점)',
            'CHM2201': '물리화학Ⅰ (3학점)',
            'CHM2202': '물리화학Ⅱ (3학점)',
            'CHM2251': '물리화학실험Ⅰ (2학점)',
            'CHM2301': '유기화학Ⅰ (3학점)',
            'CHM2302': '유기화학Ⅱ (3학점)',
            'CHM2351': '유기화학실험Ⅰ (2학점)',
            'CHM2401': '무기화학Ⅰ (3학점)',
            'CHM2451': '무기화학실험 (2학점)',
        },
        '필수선택_4과목중_2과목이상_최소4학점': {
            '후보_4과목': {
                'CHM2152': '첨단화학기기분석실험 (2학점)',
                'CHM2252': '물리화학실험Ⅱ (2학점)',
                'CHM2352': '유기화학실험Ⅱ (2학점)',
                'CHM2651': '생화학실험 (2학점)',
            },
            '최소_이수_과목수': 2,
            '최소_이수_학점': 4,
            '비고': '다전공·단일전공·교직과정 모두 해당. 필수선택 실험과목은 모두 화학과 전공과목으로 인정.',
        },
        '필수_합계_최소': 30,
    },

    # ── 기타이수요건 ──
    '기타이수요건': {
        '전공학점_미포함_과목': [
            'CHM4051 연구프로젝트Ⅰ',
            'CHM4052 창의적 연구 프로젝트 설계',
            'CHM4203 화학 특허와 기술이전',
        ],
        '비고_CHM4203_동일과목': '화학 특허와 기술이전(CHM4203)은 PHY4203·BIO4203 등 타학과 동일과목과 동일하게 처리.',
        '교직_추가의무': ['EDUS981 교육학개론', 'EDUS982 교육심리', 'EDUS983 교육과정'],
    },

    # ── 로드맵 ──
    'Road_Map': {
        '구조_주석': '요람 전공교육과정 이수 로드맵 — 학년별 권장 과목',
        '1학년': {
            '공통': [
                '일반화학 Ⅰ (CHM1001)', '일반화학실험 Ⅰ (CHM1051)',
                '일반화학 Ⅱ (CHM1002)', '일반화학실험 Ⅱ (CHM1052)',
            ],
            '물리화학': ['물리화학 Ⅰ (CHM2201)'],
        },
        '2학년': {
            '공통': [
                '일반물리 Ⅰ,Ⅱ (PHY1001, PHY1002)', '일반물리실험 Ⅰ,Ⅱ (PHY1101, PHY1102)',
                '일반생물학 Ⅰ,Ⅱ (BIO1101, BIO1102)', '일반생물학실험 Ⅰ,Ⅱ (BIO1105, BIO1106)',
            ],
            '분석화학': ['분석화학 (CHM2101)', '분석화학실험 (CHM2151)'],
            '물리화학': ['물리화학 Ⅰ,Ⅱ (CHM2201, CHM2202)', '물리화학실험 Ⅰ (CHM2251)'],
            '유기화학': ['유기화학 Ⅰ,Ⅱ (CHM2301, CHM2302)', '유기화학실험 Ⅰ (CHM2351)'],
            '무기화학': ['무기화학 Ⅰ (CHM2401)', '무기화학실험 (CHM2451)', '무기화학 Ⅱ (CHM2402)'],
            '생화학': ['생화학 Ⅰ (CHM2601)'],
        },
        '3학년': {
            '공통': [
                '산업기술속 화학 (CHM3100)', '화학 현장실습 Ⅰ (CHM4056)',
                '화학 현장실습 Ⅱ (CHM4057)', '화학 특허와 기술이전 (CHM4203)',
            ],
            '분석화학': ['기기분석 (CHM2102)', '첨단화학기기분석실험 (CHM2152)'],
            '물리화학': ['물리화학특론 (CHM2231)', '고급물리화학 Ⅰ,Ⅱ (CHMG201, CHMG202)'],
            '유기화학': ['유기화학특론 Ⅰ,Ⅱ (CHM2331, CHM2332)', '고급유기화학 Ⅰ,Ⅱ (CHMG301, CHMG302)'],
            '무기화학': ['고급무기화학 (CHMG401)', '무기재료화학 (CHMG402)'],
            '고분자화학': ['고분자화학 (CHM2501)'],
            '생화학': ['생화학 Ⅱ (CHM2602)', '고급생화학 Ⅰ (CHMG501)'],
        },
        '4학년': {
            '연구_프로젝트': [
                '연구프로젝트 Ⅰ (CHM4051)', '창의적 연구 프로젝트 설계 (CHM4052)',
                '첨단화학캡스톤디자인 (CHM4055)',
            ],
            '유기화학': ['유기화학실험 Ⅱ (CHM2352)'],
            '생화학': ['생화학실험 (CHM2651)', '고급생화학 Ⅱ (CHMG502)'],
            '기타': [
                '화학 인공지능 기초 (CHM4053)', '화학기기 종합설계 (CHM4054)',
                '자연과학논문작성 및 발표법 (CHMG601)',
            ],
        },
        '비고': '위 로드맵은 권장 학기일 뿐 강제 규칙 아님. 필수 10과목 26학점 + 필수선택 2과목 이상 4학점은 반드시 충족.',
    },
}


# ── graduationCategory corrections ──────────────────────────────────
# CHM2351/CHM2401/CHM2451: 전공선택 → 전공필수
# CHM2152/CHM2252/CHM2352/CHM2651: 전공선택 → 전공필수선택
CAT_TO_REQUIRED = ['CHM2351', 'CHM2401', 'CHM2451']
CAT_TO_ELECTIVE_CORE = ['CHM2152', 'CHM2252', 'CHM2352', 'CHM2651']

# ── countsTowardMajorCredits True → False ────────────────────────────
# 전공입문: CHM1001/1002/1051/1052 (입문과목은 전공학점 미포함)
# 기타이수요건 제외: CHM4051/4052/4203 (전공학점 미포함)
COUNTS_FALSE = ['CHM1001', 'CHM1002', 'CHM1051', 'CHM1052',
                'CHM4051', 'CHM4052', 'CHM4203']

# ── COURSE_JOB_FITS ──────────────────────────────────────────────────
CHM_COURSE_JOB_FITS = [
    # 분석화학 계열
    {"courseCode": "CHM2101", "jobIri": "Job_반도체",    "weight": 0.75},
    {"courseCode": "CHM2101", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "CHM2151", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "CHM2151", "jobIri": "Job_PM",        "weight": 0.55},
    {"courseCode": "CHM2102", "jobIri": "Job_반도체",    "weight": 0.80},
    {"courseCode": "CHM2102", "jobIri": "Job_데이터분석", "weight": 0.70},
    {"courseCode": "CHM2152", "jobIri": "Job_반도체",    "weight": 0.75},
    {"courseCode": "CHM2152", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "CHMG101", "jobIri": "Job_반도체",    "weight": 0.80},
    {"courseCode": "CHMG101", "jobIri": "Job_데이터분석", "weight": 0.70},

    # 물리화학 계열
    {"courseCode": "CHM2201", "jobIri": "Job_반도체",    "weight": 0.80},
    {"courseCode": "CHM2201", "jobIri": "Job_AI엔지니어", "weight": 0.60},
    {"courseCode": "CHM2202", "jobIri": "Job_반도체",    "weight": 0.80},
    {"courseCode": "CHM2202", "jobIri": "Job_AI엔지니어", "weight": 0.60},
    {"courseCode": "CHM2203", "jobIri": "Job_반도체",    "weight": 0.75},
    {"courseCode": "CHM2203", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "CHM2231", "jobIri": "Job_반도체",    "weight": 0.75},
    {"courseCode": "CHM2231", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "CHM2251", "jobIri": "Job_반도체",    "weight": 0.75},
    {"courseCode": "CHM2252", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "CHMG201", "jobIri": "Job_반도체",    "weight": 0.80},
    {"courseCode": "CHMG201", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "CHMG202", "jobIri": "Job_반도체",    "weight": 0.80},
    {"courseCode": "CHMG202", "jobIri": "Job_데이터분석", "weight": 0.65},

    # 유기화학 계열
    {"courseCode": "CHM2301", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "CHM2302", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "CHM2303", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "CHM2351", "jobIri": "Job_반도체",    "weight": 0.65},
    {"courseCode": "CHM2352", "jobIri": "Job_반도체",    "weight": 0.65},
    {"courseCode": "CHM2331", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "CHM2332", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "CHMG301", "jobIri": "Job_반도체",    "weight": 0.75},
    {"courseCode": "CHMG302", "jobIri": "Job_반도체",    "weight": 0.75},

    # 무기화학 계열
    {"courseCode": "CHM2401", "jobIri": "Job_반도체",    "weight": 0.85},
    {"courseCode": "CHM2402", "jobIri": "Job_반도체",    "weight": 0.85},
    {"courseCode": "CHM2451", "jobIri": "Job_반도체",    "weight": 0.80},
    {"courseCode": "CHMG401", "jobIri": "Job_반도체",    "weight": 0.90},
    {"courseCode": "CHMG402", "jobIri": "Job_반도체",    "weight": 0.90},
    {"courseCode": "CHMG402", "jobIri": "Job_PM",        "weight": 0.60},

    # 고분자화학
    {"courseCode": "CHM2501", "jobIri": "Job_반도체",    "weight": 0.80},
    {"courseCode": "CHM2501", "jobIri": "Job_컨설팅",    "weight": 0.55},

    # 생화학 계열
    {"courseCode": "CHM2601", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "CHM2601", "jobIri": "Job_AI엔지니어", "weight": 0.55},
    {"courseCode": "CHM2602", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "CHM2651", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "CHMG501", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "CHMG501", "jobIri": "Job_AI엔지니어", "weight": 0.60},
    {"courseCode": "CHMG502", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "CHMG502", "jobIri": "Job_AI엔지니어", "weight": 0.60},

    # 연구/프로젝트/캡스톤
    {"courseCode": "CHM4051", "jobIri": "Job_PM",        "weight": 0.80},
    {"courseCode": "CHM4051", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "CHM4052", "jobIri": "Job_PM",        "weight": 0.80},
    {"courseCode": "CHM4052", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "CHM4055", "jobIri": "Job_PM",        "weight": 0.85},
    {"courseCode": "CHM4055", "jobIri": "Job_반도체",    "weight": 0.75},

    # 화학 AI / 데이터
    {"courseCode": "CHM4053", "jobIri": "Job_AI엔지니어", "weight": 0.90},
    {"courseCode": "CHM4053", "jobIri": "Job_데이터분석", "weight": 0.85},
    {"courseCode": "CHM4053", "jobIri": "Job_반도체",    "weight": 0.70},

    # 화학기기 종합설계
    {"courseCode": "CHM4054", "jobIri": "Job_반도체",    "weight": 0.80},
    {"courseCode": "CHM4054", "jobIri": "Job_PM",        "weight": 0.70},

    # 현장실습 / 특허
    {"courseCode": "CHM4056", "jobIri": "Job_기획",      "weight": 0.70},
    {"courseCode": "CHM4056", "jobIri": "Job_PM",        "weight": 0.65},
    {"courseCode": "CHM4057", "jobIri": "Job_기획",      "weight": 0.70},
    {"courseCode": "CHM4057", "jobIri": "Job_PM",        "weight": 0.65},
    {"courseCode": "CHM4203", "jobIri": "Job_컨설팅",    "weight": 0.70},
    {"courseCode": "CHM4203", "jobIri": "Job_기획",      "weight": 0.65},

    # 진로설계 / 논문작성
    {"courseCode": "CHM3100", "jobIri": "Job_기획",      "weight": 0.65},
    {"courseCode": "CHM3100", "jobIri": "Job_교육",      "weight": 0.60},
    {"courseCode": "CHMG601", "jobIri": "Job_교육",      "weight": 0.70},
    {"courseCode": "CHMG601", "jobIri": "Job_PR언론",    "weight": 0.55},
]


# ── MAIN ─────────────────────────────────────────────────────────────
BASE = '/home/user/Sogangproject'

# STEP 1: data_round1.py — expand Dept_CHM credits
print("=== STEP 1: data_round1.py ===")
with open(f'{BASE}/data_round1.py', encoding='utf-8') as f:
    r1 = f.read()
r1 = replace_credits(r1, 'Dept_CHM', DEPT_CHM_CREDITS_FULL)
with open(f'{BASE}/data_round1.py', 'w', encoding='utf-8') as f:
    f.write(r1)
print("data_round1.py written.\n")

# STEP 2: data_round2.py — fix course classifications
print("=== STEP 2: data_round2.py ===")
with open(f'{BASE}/data_round2.py', encoding='utf-8') as f:
    r2 = f.read()

print("  Fixing graduationCategory: 전공선택 → 전공필수 (3 courses)...")
for code in CAT_TO_REQUIRED:
    r2, ok = fix_str_field_by_code(r2, code, 'graduationCategory', '전공선택', '전공필수')
    if ok:
        print(f"    {code}: 전공선택 → 전공필수")

print("  Fixing graduationCategory: 전공선택 → 전공필수선택 (4 courses)...")
for code in CAT_TO_ELECTIVE_CORE:
    r2, ok = fix_str_field_by_code(r2, code, 'graduationCategory', '전공선택', '전공필수선택')
    if ok:
        print(f"    {code}: 전공선택 → 전공필수선택")

print("  Fixing countsTowardMajorCredits: True → False (7 courses)...")
for code in COUNTS_FALSE:
    r2, ok = fix_bool_field_by_code(r2, code, 'countsTowardMajorCredits', 'True', 'False')
    if ok:
        print(f"    {code}: countsTowardMajorCredits True → False")

with open(f'{BASE}/data_round2.py', 'w', encoding='utf-8') as f:
    f.write(r2)
print("data_round2.py written.\n")

# STEP 3: data_round4.py — add CHM job fits
print("=== STEP 3: data_round4.py ===")
with open(f'{BASE}/data_round4.py', encoding='utf-8') as f:
    r4 = f.read()
r4 = add_job_fits(r4, CHM_COURSE_JOB_FITS, 'CHM')
with open(f'{BASE}/data_round4.py', 'w', encoding='utf-8') as f:
    f.write(r4)
print("data_round4.py written.\n")

print("=== ALL CHM PATCHES APPLIED ===")
