#!/usr/bin/env python3
"""apply_patches5.py — Apply PHY (물리학과) patch."""

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


def fix_int_field_by_code(content, code, field, old_val, new_val):
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


# ── PHY patch data ───────────────────────────────────────────────────

DEPT_PHY_CREDITS_FULL = {
    # ── 전인교육 (공통) ──
    '교양_공통필수': 11,
    '교양_공통선택_①': 3,
    '교양_공통선택_②': 3,
    '교양_공통선택_③': 3,
    '교양_공통선택_④': 3,
    '교양_전인교육_합계': 23,

    # ── 단일전공 ──
    '단일전공_총학점': 130,
    '단일전공_전공학점': 60,
    '단일전공_전공입문_최소학점': 22,
    '단일전공_필수_최소학점': 35,
    '단일전공_선택_최소학점': 25,

    # ── 다전공 ──
    '다전공_총학점': 130,
    '다전공_전공학점': 47,
    '다전공_전공입문_최소학점': 11,
    '다전공_필수_최소학점': 35,
    '다전공_선택_최소학점': 12,
    '다전공_전공입문_주석': '다전공자는 공통필수 11학점(PHY1001·1002·1101·1102·STS2006)만 이수. 공통선택 11학점 추가 이수 불필요.',

    # ── 교직과정 ──
    '교직과정_총학점': 130,
    '교직과정_전공학점': 60,
    '교직과정_전공입문_최소학점': 22,
    '교직과정_필수_최소학점': 35,
    '교직과정_선택_최소학점': 25,
    '교직과정_주석': 'EDUS981·EDUS982·EDUS983 교직 3과목 이수 의무. 교직 전공 25학점 이수 필요.',

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

    # ── 전공입문 구성 (단일전공 22학점 / 다전공 11학점) ──
    '전공입문_구성': {
        '공통필수_11학점': {
            '과목': [
                'PHY1001 일반물리Ⅰ (3학점)', 'PHY1002 일반물리Ⅱ (3학점)',
                'PHY1101 일반물리실험Ⅰ (1학점)', 'PHY1102 일반물리실험Ⅱ (1학점)',
                'STS2006 미적분학Ⅱ (3학점)',
            ],
            '비고': '물리학 단일전공자·다전공자 모두 해당. 다전공자는 공통필수 11학점으로 전공입문 완료.',
        },
        '공통선택_11학점_단일전공만': {
            '비고': '물리학 단일전공자만 추가 이수. 아래 두 옵션 중 set으로 택1. 실험과목은 이론과목과 동일 분야에서 선택.',
            '옵션A_화학중심': {
                '구성': 'CHM 4과목(8학점) + BIO 1과목 택1(3학점) = 11학점',
                'CHM_필수_4과목_8학점': [
                    'CHM1001 일반화학Ⅰ (3학점)', 'CHM1002 일반화학Ⅱ (3학점)',
                    'CHM1051 일반화학실험Ⅰ (1학점)', 'CHM1052 일반화학실험Ⅱ (1학점)',
                ],
                'BIO_택1_3학점': ['BIO1001 일반생물학Ⅰ', 'BIO1002 일반생물학Ⅱ'],
            },
            '옵션B_생물중심': {
                '구성': 'BIO 4과목(8학점) + CHM 1과목 택1(3학점) = 11학점',
                'BIO_필수_4과목_8학점': [
                    'BIO1001 일반생물학Ⅰ (3학점)', 'BIO1002 일반생물학Ⅱ (3학점)',
                    'BIO1105 일반생물학실험Ⅰ (1학점)', 'BIO1106 일반생물학실험Ⅱ (1학점)',
                ],
                'CHM_택1_3학점': ['CHM1001 일반화학Ⅰ', 'CHM1002 일반화학Ⅱ'],
            },
        },
        '합계_단일전공': 22,
        '합계_다전공': 11,
    },

    # ── 전공필수 구성 (35학점) ──
    '전공필수_구성': {
        '필수_13과목_35학점': {
            'PHY2001': '역학Ⅰ (3학점)',
            'PHY2003': '전자기학Ⅰ (3학점)',
            'PHY2004': '전자기학Ⅱ (3학점)',
            'PHY2005': '수리물리학Ⅰ (3학점)',
            'PHY2009': '현대물리학 (3학점)',
            'PHY2101': '실험물리학Ⅰ (2학점)',
            'PHY2102': '실험물리학Ⅱ (2학점)',
            'PHY3001': '양자물리학Ⅰ (3학점)',
            'PHY3002': '양자물리학Ⅱ (3학점)',
            'PHY3003': '열역학 (3학점)',
            'PHY3004': '통계물리학 (3학점)',
            'PHY3101': '실험물리학Ⅲ (2학점)',
            'PHY3102': '실험물리학Ⅳ (2학점)',
        },
        '합계': 35,
        '비고': '단일전공·다전공·교직과정 모두 동일 35학점 필수.',
    },

    # ── 전공선택 이수 규정 ──
    '전공선택_이수규정': {
        '단일전공_25학점': 'PHY4201(특수연구)·PHY4203(물리특허와기술이전)·PHY4204(졸업프로젝트) 제외한 전공과목 중 25학점 이수.',
        '다전공_12학점': 'PHY4201·PHY4203·PHY4204 제외한 전공과목 중 12학점 이수.',
        '타학과_전공인정_단일전공': {
            '비고': '물리학 단일전공자만 아래 타학과 과목을 물리전공 학점으로 인정 (최대 6개 분야).',
            '수학전공': ['MAT2110 선형대수학', 'MAT2210 고등미적분학Ⅰ', 'MAT2330 미분방정식'],
            '화학전공': ['CHM2101 분석화학', 'CHM2201 물리화학Ⅰ', 'CHM2301 유기화학Ⅰ', 'CHM2401 무기화학Ⅰ'],
            '생명과학전공': ['BIO2131 생화학Ⅰ', 'BIO2151 분자생물학'],
            '전자공학전공': ['EEE2111 기초회로이론', 'EEE2120 물리전자공학Ⅰ'],
            '기계공학전공': ['MEE2012 유체역학Ⅰ'],
        },
    },

    # ── 기타이수요건 ──
    '기타이수요건': {
        '교직_추가의무': ['EDUS981 교육학개론', 'EDUS982 교육심리', 'EDUS983 교육과정'],
        '대학원연계_권고_PHYG003': 'PHYG003(통계역학)은 3·4학년 수강 권장. 대학원 연계 과목으로 심화 학습에 활용.',
        'PHYG001_성적요건': 'PHYG001(고전물리Ⅰ)은 학점 3.0 이상 취득 권장.',
        '전공학점_미포함_과목': [
            'PHY4201 특수연구',
            'PHY4203 물리 특허와 기술이전',
            'PHY4204 졸업프로젝트',
        ],
        'PHY4201_PHY4204_중복불가': '특수연구(PHY4201)와 졸업프로젝트(PHY4204)는 동시 이수 불가. 둘 중 하나 선택.',
        'PHY4203_동일과목': '물리 특허와 기술이전(PHY4203)은 CHM4203·BIO4203과 동일 과목으로 처리.',
    },

    # ── 로드맵 ──
    'Road_Map': {
        '구조_주석': '요람 전공교육과정 이수 로드맵 — 학년별 권장 과목 및 분야별 트랙',
        '1학년': {
            '전공예비': ['일반물리Ⅰ (PHY1001)', '일반물리실험Ⅰ (PHY1101)'],
            '전공필수': ['역학Ⅰ (PHY2001, 영어강의)', '전자기학Ⅰ (PHY2003, 영어강의)', '수리물리학Ⅰ (PHY2005, 영어강의)', '실험물리학Ⅰ (PHY2101)'],
            '전공선택_일반': ['전자물리학Ⅰ (PHY2007)'],
        },
        '2학년': {
            '전공예비': ['일반물리Ⅱ (PHY1002)', '일반물리실험Ⅱ (PHY1102)', '미적분학Ⅱ (STS2006)'],
            '전공필수': ['전자기학Ⅱ (PHY2004, 영어강의)', '실험물리학Ⅱ (PHY2102)', '현대물리학 (PHY2009)'],
            '전공선택_일반': ['전자물리학Ⅱ (PHY2008)', '역학Ⅱ (PHY2002)', '수리물리학Ⅱ (PHY2006, 영어강의)'],
        },
        '3학년': {
            '전공필수': ['양자물리학Ⅰ (PHY3001)', '열역학 (PHY3003)', '실험물리학Ⅲ (PHY3101)'],
            '전공선택_일반': ['현대광학Ⅰ (PHY4003)', '전산물리학Ⅰ (PHY4007)'],
            '전공선택_심화': ['고체물리학Ⅰ (PHY4001)', '기초입자이론Ⅰ (PHY4005)'],
            '대학원연계': ['고전물리Ⅰ (PHYG001)', '통계역학 (PHYG003)'],
        },
        '4학년': {
            '전공필수': ['양자물리학Ⅱ (PHY3002)', '통계물리학 (PHY3004)', '실험물리학Ⅳ (PHY3102)'],
            '전공선택_일반': ['현대광학Ⅱ (PHY4004)', '전산물리학Ⅱ (PHY4008)'],
            '전공선택_심화': ['고체물리학Ⅱ (PHY4002)', '기초입자이론Ⅱ (PHY4006)'],
            '전공선택_응용': [
                '일반상대성이론 (PHY4010)', '천체물리학 (PHY4011)',
                '디스플레이물리학 (PHY4016)', '나노물리 (PHY4012)',
                '물리학 특강 (PHY4202)', '반도체물리학 (PHY4009)',
                '바이오물리 (PHY4013)', '분광학 (PHY4019)',
                '의학물리 (PHY4015)', '원자물리학 (PHY4017)',
                '기계학습응용 (PHYG004)', '인공지능과 물리 (PHYG005)',
                '양자장이론Ⅰ (PHYG006)',
            ],
            '캡스톤_연구': [
                '물리 캡스톤 디자인Ⅰ (PHY3501)', '물리 캡스톤 디자인Ⅱ (PHY3502)',
                '특수연구 (PHY4201)', '졸업프로젝트 (PHY4204)',
            ],
        },
        '비고': '(영)표시 과목은 영어강의. 위 로드맵은 권장 학기일 뿐 강제 규칙 아님. 전공필수 35학점은 반드시 충족.',
    },
}


# ── graduationCategory 수정: 전공선택 → 전공필수 ──────────────────────
CAT_TO_REQUIRED = ['PHY3003', 'PHY3004', 'PHY3101', 'PHY3102']

# ── countsTowardMajorCredits True → False ────────────────────────────
# 전공입문: PHY1001/1002/1101/1102
# 기타이수요건 제외: PHY4201/4203/4204
COUNTS_FALSE = ['PHY1001', 'PHY1002', 'PHY1101', 'PHY1102',
                'PHY4201', 'PHY4203', 'PHY4204']

# ── PHY4201/4204 데이터 손상 수정 ───────────────────────────────────
# PHY4201: courseName '(특수연구)' → '특수연구', credits 25 → 3
# PHY4204: courseName 오염 → '졸업프로젝트', credits 25 → 3
PHY4201_NAME_FIX = ('(특수연구)', '특수연구')
PHY4204_NAME_FIX = ('(졸업프로젝트)를 제외한 전공과목 중에서 25학점 이수', '졸업프로젝트')
PHY4204_DESC_FIX = ('(졸업프로젝트)를 제외한 전공과목 중에서 25학점 이수', '졸업프로젝트 (강의 3시간)')

# ── COURSE_JOB_FITS ──────────────────────────────────────────────────
PHY_COURSE_JOB_FITS = [
    # 전공필수 — 기초 물리
    {"courseCode": "PHY2001", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "PHY2001", "jobIri": "Job_데이터분석", "weight": 0.55},
    {"courseCode": "PHY2003", "jobIri": "Job_반도체",    "weight": 0.80},
    {"courseCode": "PHY2003", "jobIri": "Job_AI엔지니어", "weight": 0.60},
    {"courseCode": "PHY2004", "jobIri": "Job_반도체",    "weight": 0.80},
    {"courseCode": "PHY2004", "jobIri": "Job_AI엔지니어", "weight": 0.60},
    {"courseCode": "PHY2005", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "PHY2005", "jobIri": "Job_AI엔지니어", "weight": 0.60},
    {"courseCode": "PHY2009", "jobIri": "Job_반도체",    "weight": 0.75},
    {"courseCode": "PHY2009", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "PHY2101", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "PHY2101", "jobIri": "Job_PM",        "weight": 0.55},
    {"courseCode": "PHY2102", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "PHY2102", "jobIri": "Job_PM",        "weight": 0.55},

    # 전공필수 — 양자·열·통계
    {"courseCode": "PHY3001", "jobIri": "Job_반도체",    "weight": 0.85},
    {"courseCode": "PHY3001", "jobIri": "Job_AI엔지니어", "weight": 0.65},
    {"courseCode": "PHY3002", "jobIri": "Job_반도체",    "weight": 0.85},
    {"courseCode": "PHY3002", "jobIri": "Job_AI엔지니어", "weight": 0.65},
    {"courseCode": "PHY3003", "jobIri": "Job_반도체",    "weight": 0.75},
    {"courseCode": "PHY3003", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "PHY3004", "jobIri": "Job_반도체",    "weight": 0.75},
    {"courseCode": "PHY3004", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "PHY3004", "jobIri": "Job_AI엔지니어", "weight": 0.60},
    {"courseCode": "PHY3101", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "PHY3101", "jobIri": "Job_PM",        "weight": 0.60},
    {"courseCode": "PHY3102", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "PHY3102", "jobIri": "Job_PM",        "weight": 0.60},

    # 전공선택 — 역학·수리물리
    {"courseCode": "PHY2002", "jobIri": "Job_반도체",    "weight": 0.65},
    {"courseCode": "PHY2006", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "PHY2006", "jobIri": "Job_AI엔지니어", "weight": 0.60},

    # 전자물리학 — 반도체 직결
    {"courseCode": "PHY2007", "jobIri": "Job_반도체",    "weight": 0.90},
    {"courseCode": "PHY2007", "jobIri": "Job_소프트웨어", "weight": 0.60},
    {"courseCode": "PHY2008", "jobIri": "Job_반도체",    "weight": 0.90},
    {"courseCode": "PHY2008", "jobIri": "Job_소프트웨어", "weight": 0.60},

    # 고체물리학 — 반도체 핵심
    {"courseCode": "PHY4001", "jobIri": "Job_반도체",    "weight": 0.95},
    {"courseCode": "PHY4001", "jobIri": "Job_PM",        "weight": 0.60},
    {"courseCode": "PHY4002", "jobIri": "Job_반도체",    "weight": 0.95},
    {"courseCode": "PHY4002", "jobIri": "Job_PM",        "weight": 0.60},

    # 반도체물리학
    {"courseCode": "PHY4009", "jobIri": "Job_반도체",    "weight": 1.00},
    {"courseCode": "PHY4009", "jobIri": "Job_PM",        "weight": 0.65},

    # 광학
    {"courseCode": "PHY4003", "jobIri": "Job_반도체",    "weight": 0.80},
    {"courseCode": "PHY4003", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "PHY4004", "jobIri": "Job_반도체",    "weight": 0.80},

    # 입자이론
    {"courseCode": "PHY4005", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "PHY4005", "jobIri": "Job_AI엔지니어", "weight": 0.65},
    {"courseCode": "PHY4006", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "PHY4006", "jobIri": "Job_AI엔지니어", "weight": 0.65},

    # 전산물리학 — 데이터·AI 핵심
    {"courseCode": "PHY4007", "jobIri": "Job_데이터분석", "weight": 0.85},
    {"courseCode": "PHY4007", "jobIri": "Job_AI엔지니어", "weight": 0.80},
    {"courseCode": "PHY4007", "jobIri": "Job_소프트웨어", "weight": 0.75},
    {"courseCode": "PHY4008", "jobIri": "Job_데이터분석", "weight": 0.85},
    {"courseCode": "PHY4008", "jobIri": "Job_AI엔지니어", "weight": 0.80},
    {"courseCode": "PHY4008", "jobIri": "Job_소프트웨어", "weight": 0.75},

    # 응용물리 계열
    {"courseCode": "PHY4010", "jobIri": "Job_데이터분석", "weight": 0.55},
    {"courseCode": "PHY4011", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "PHY4012", "jobIri": "Job_반도체",    "weight": 0.90},
    {"courseCode": "PHY4012", "jobIri": "Job_PM",        "weight": 0.65},
    {"courseCode": "PHY4013", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "PHY4013", "jobIri": "Job_AI엔지니어", "weight": 0.65},
    {"courseCode": "PHY4015", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "PHY4015", "jobIri": "Job_AI엔지니어", "weight": 0.60},
    {"courseCode": "PHY4016", "jobIri": "Job_반도체",    "weight": 0.90},
    {"courseCode": "PHY4016", "jobIri": "Job_PM",        "weight": 0.65},
    {"courseCode": "PHY4017", "jobIri": "Job_반도체",    "weight": 0.75},
    {"courseCode": "PHY4019", "jobIri": "Job_반도체",    "weight": 0.80},
    {"courseCode": "PHY4019", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "PHY4101", "jobIri": "Job_반도체",    "weight": 0.75},
    {"courseCode": "PHY4101", "jobIri": "Job_PM",        "weight": 0.65},

    # 물리학 특강 / 특허
    {"courseCode": "PHY4202", "jobIri": "Job_교육",      "weight": 0.70},
    {"courseCode": "PHY4202", "jobIri": "Job_반도체",    "weight": 0.65},
    {"courseCode": "PHY4203", "jobIri": "Job_컨설팅",    "weight": 0.70},
    {"courseCode": "PHY4203", "jobIri": "Job_기획",      "weight": 0.65},

    # 대학원연계 — 고전물리·통계역학·양자장이론
    {"courseCode": "PHYG001", "jobIri": "Job_반도체",    "weight": 0.75},
    {"courseCode": "PHYG001", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "PHYG003", "jobIri": "Job_반도체",    "weight": 0.75},
    {"courseCode": "PHYG003", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "PHYG003", "jobIri": "Job_AI엔지니어", "weight": 0.65},
    {"courseCode": "PHYG006", "jobIri": "Job_데이터분석", "weight": 0.65},
    {"courseCode": "PHYG006", "jobIri": "Job_AI엔지니어", "weight": 0.70},

    # AI·기계학습 — AI/데이터 핵심
    {"courseCode": "PHYG004", "jobIri": "Job_AI엔지니어", "weight": 0.95},
    {"courseCode": "PHYG004", "jobIri": "Job_데이터분석", "weight": 0.90},
    {"courseCode": "PHYG004", "jobIri": "Job_소프트웨어", "weight": 0.75},
    {"courseCode": "PHYG005", "jobIri": "Job_AI엔지니어", "weight": 0.95},
    {"courseCode": "PHYG005", "jobIri": "Job_데이터분석", "weight": 0.85},
    {"courseCode": "PHYG005", "jobIri": "Job_반도체",    "weight": 0.70},

    # 캡스톤 / 연구 / 현장실습
    {"courseCode": "PHY3501", "jobIri": "Job_PM",        "weight": 0.85},
    {"courseCode": "PHY3501", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "PHY3502", "jobIri": "Job_PM",        "weight": 0.85},
    {"courseCode": "PHY3502", "jobIri": "Job_반도체",    "weight": 0.70},
    {"courseCode": "PHY4201", "jobIri": "Job_PM",        "weight": 0.85},
    {"courseCode": "PHY4201", "jobIri": "Job_반도체",    "weight": 0.65},
    {"courseCode": "PHY4204", "jobIri": "Job_PM",        "weight": 0.85},
    {"courseCode": "PHY4204", "jobIri": "Job_반도체",    "weight": 0.65},
    {"courseCode": "PHY3510", "jobIri": "Job_기획",      "weight": 0.70},
    {"courseCode": "PHY3510", "jobIri": "Job_PM",        "weight": 0.65},
    {"courseCode": "PHY3515", "jobIri": "Job_기획",      "weight": 0.65},
    {"courseCode": "PHY3515", "jobIri": "Job_교육",      "weight": 0.60},
]


# ── MAIN ─────────────────────────────────────────────────────────────
BASE = '/home/user/Sogangproject'

# STEP 1: data_round1.py — expand Dept_PHY credits
print("=== STEP 1: data_round1.py ===")
with open(f'{BASE}/data_round1.py', encoding='utf-8') as f:
    r1 = f.read()
r1 = replace_credits(r1, 'Dept_PHY', DEPT_PHY_CREDITS_FULL)
with open(f'{BASE}/data_round1.py', 'w', encoding='utf-8') as f:
    f.write(r1)
print("data_round1.py written.\n")

# STEP 2: data_round2.py — fix course classifications + data damage
print("=== STEP 2: data_round2.py ===")
with open(f'{BASE}/data_round2.py', encoding='utf-8') as f:
    r2 = f.read()

# 2a. graduationCategory: 전공선택 → 전공필수
print("  Fixing graduationCategory: 전공선택 → 전공필수 (4 courses)...")
for code in CAT_TO_REQUIRED:
    r2, ok = fix_str_field_by_code(r2, code, 'graduationCategory', '전공선택', '전공필수')
    if ok:
        print(f"    {code}: 전공선택 → 전공필수")

# 2b. PHY4201 데이터 손상 수정: courseName + credits
print("  Fixing PHY4201 data damage (courseName, credits)...")
r2, ok = fix_str_field_by_code(r2, 'PHY4201', 'courseName', PHY4201_NAME_FIX[0], PHY4201_NAME_FIX[1])
if ok: print("    PHY4201: courseName fixed → '특수연구'")
r2, ok = fix_int_field_by_code(r2, 'PHY4201', 'credits', 25, 3)
if ok: print("    PHY4201: credits fixed → 3")

# 2c. PHY4204 데이터 손상 수정: courseName + description + credits
print("  Fixing PHY4204 data damage (courseName, description, credits)...")
r2, ok = fix_str_field_by_code(r2, 'PHY4204', 'courseName', PHY4204_NAME_FIX[0], PHY4204_NAME_FIX[1])
if ok: print("    PHY4204: courseName fixed → '졸업프로젝트'")
r2, ok = fix_str_field_by_code(r2, 'PHY4204', 'description', PHY4204_NAME_FIX[0], PHY4204_DESC_FIX[1])
if ok: print("    PHY4204: description fixed → '졸업프로젝트 (강의 3시간)'")
r2, ok = fix_int_field_by_code(r2, 'PHY4204', 'credits', 25, 3)
if ok: print("    PHY4204: credits fixed → 3")

# 2d. countsTowardMajorCredits: True → False
print("  Fixing countsTowardMajorCredits: True → False (7 courses)...")
for code in COUNTS_FALSE:
    r2, ok = fix_bool_field_by_code(r2, code, 'countsTowardMajorCredits', 'True', 'False')
    if ok:
        print(f"    {code}: countsTowardMajorCredits True → False")

with open(f'{BASE}/data_round2.py', 'w', encoding='utf-8') as f:
    f.write(r2)
print("data_round2.py written.\n")

# STEP 3: data_round4.py — add PHY job fits
print("=== STEP 3: data_round4.py ===")
with open(f'{BASE}/data_round4.py', encoding='utf-8') as f:
    r4 = f.read()
r4 = add_job_fits(r4, PHY_COURSE_JOB_FITS, 'PHY')
with open(f'{BASE}/data_round4.py', 'w', encoding='utf-8') as f:
    f.write(r4)
print("data_round4.py written.\n")

print("=== ALL PHY PATCHES APPLIED ===")
