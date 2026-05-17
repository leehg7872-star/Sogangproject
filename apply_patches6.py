#!/usr/bin/env python3
"""apply_patches6.py — Apply SCIENCE기반 자유전공학부 (Dept_FREE_SCI) patch."""

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


# ── SCIENCE기반 자유전공학부 patch data ──────────────────────────────

DEPT_FREE_SCI_CREDITS_FULL = {
    # ── 총학점 ──
    '기본_총학점': 130,

    # ── 전인교육 (공통) ──
    '교양_공통필수': 11,
    '교양_공통선택_①': 3,
    '교양_공통선택_②': 3,
    '교양_공통선택_③': 3,
    '교양_공통선택_④': 3,
    '교양_전인교육_합계': 23,

    # ── SCIENCE기반필수교과 (전공입문교과 18학점) ──
    '기본_SCIENCE기반필수_최소학점': 18,
    'SCIENCE기반필수_구성': {
        '진로탐색_0학점': {
            'SCI1001': '자유전공진로탐색 (0학점)',
            '비고': '이수 필수이나 학점 인정 없음',
        },
        'SCI_핵심_5과목_15학점': {
            'SCI1011': '과학수학 (3학점)',
            'SCI1012': '통합물리 (3학점)',
            'SCI1013': '통합화학 (3학점)',
            'SCI1014': '통합생물학 (3학점)',
            'SCI1021': '과학도를 위한 선형대수 (3학점)',
        },
        '일반실험_6개중_택3_3학점': {
            '후보_6과목': [
                'PHY1101 일반물리실험Ⅰ', 'PHY1102 일반물리실험Ⅱ',
                'CHM1051 일반화학실험Ⅰ', 'CHM1052 일반화학실험Ⅱ',
                'BIO1105 일반생물학실험Ⅰ', 'BIO1106 일반생물학실험Ⅱ',
            ],
            '선택_학점': 3,
            '비고': '6과목 중 3과목 선택 이수 (각 1학점). 총 3학점.',
        },
        '합계': 18,
    },

    # ── 공통선택 ④ 특수필수 ──
    '기본_공통선택특수필수': 3,
    '공통선택_④_특수규정': {
        '과목코드': 'STS2015',
        '과목명': '과학도를 위한 파이썬',
        '학점': 3,
        '비고': 'SCIENCE기반 자유전공생은 자연·공학계열로 제1전공 선택 시에도 미적분학Ⅰ 대신 STS2015(과학도를 위한 파이썬)를 공통선택 ④ 영역 필수 이수. 일반 학과의 공통선택④ 미적분학Ⅰ과 다른 점.',
    },

    # ── 전공 학점 이수 (제1전공 연동) ──
    '기본_제1전공_다전공요건': '제1전공의 다전공 학점 이수요건을 따름',
    '전공_이수_원칙': {
        '주석': '전공필수·전공선택·전공소계는 선택한 제1전공의 다전공 학점이수요건 기준 적용.',
        '전공입문_처리': 'SCIENCE기반필수교과 18학점이 제1전공의 전공입문교과를 대체 인정.',
    },

    # ── 기반필수 → 전공입문 대체 인정 매핑 ──
    '기반필수_전공입문_대체_매핑': {
        '적용_조건': '제1전공으로 자연·공학계열 전공을 다전공 이수할 때 기반필수교과목이 전공입문교과목을 대체 인정.',
        '매핑_테이블': {
            'SCI1011 과학수학': 'STS2006 미적분학Ⅱ',
            'SCI1012 통합물리': 'PHY1001 일반물리Ⅰ',
            'SCI1013 통합화학': 'CHM1001 일반화학Ⅰ',
            'SCI1014 통합생물학': 'BIO1101 일반생물학Ⅰ',
            'SCI1021 과학도를 위한 선형대수': 'MAT2110 선형대수학',
        },
        '비고': '기반필수 5과목(15학점)이 위 전공입문 과목들을 각각 1:1로 대체. 실험과목(택3) 3학점은 별도 이수.',
    },

    # ── 로드맵 ──
    'Road_Map': {
        '구조_주석': '요람 기반교육과정 이수 로드맵 — 학년별 이수 계획',
        '1학년': {
            '교양_공통필수': ['성장과 성찰', '자연계글쓰기', '알바트로스세미나'],
            '교양_공통선택': ['④인간과 과학&AI: 과학도를 위한 파이썬 (STS2015, 필수)'],
            'SCIENCE기반필수': ['과학수학 (SCI1011)', '통합생물학 (SCI1014)'],
            '소계_교양': 8,
            '소계_기반필수': 6,
        },
        '2학년': {
            '교양_공통필수': ['글로벌언어1 택1', '기초인공지능프로그래밍'],
            '교양_공통선택': ['①인간과신앙 택1', '②인간과사상 택1', '③인간과사회 택1'],
            'SCIENCE기반필수': [
                '통합물리 (SCI1012)', '통합화학 (SCI1013)',
                '과학도를 위한 선형대수 (SCI1021)', '자유전공진로탐색 (SCI1001, 0학점)',
            ],
            '소계_교양': 9,
            '소계_기반필수': 9,
        },
        '3_4학년': {
            '전공입문교과': '제1전공 다전공 기준 — 기반필수 이수로 대체 인정',
            '전공필수': '제1전공의 다전공 학점이수요건을 따름',
            '전공선택': '제1전공의 다전공 학점이수요건을 따름',
        },
        '비고': '1·2학년 기반교육 이수 후 3학년 시작 전 제1전공을 선택. 이후 해당 전공의 다전공 이수요건 적용.',
    },
}


# ── data_round2.py 수정 사항 ─────────────────────────────────────────
# 1. SCI1001: credits 3 → 0 (자유전공진로탐색 실제 0학점), graduationCategory '전공필수' → '전공입문'
# 2. SCI1011~SCI1021: graduationCategory '전공필수' → '전공입문'
#    (기반필수교과는 전공입문교과에 해당, 전공학점 미포함)
# 3. SCI1001~SCI1021: countsTowardMajorCredits True → False (전공입문 미포함 원칙)

SCI_CAT_TO_PREMAJOR = ['SCI1001', 'SCI1011', 'SCI1012', 'SCI1013', 'SCI1014', 'SCI1021']
SCI_COUNTS_FALSE    = ['SCI1001', 'SCI1011', 'SCI1012', 'SCI1013', 'SCI1014', 'SCI1021']

# ── COURSE_JOB_FITS ──────────────────────────────────────────────────
SCI_COURSE_JOB_FITS = [
    # 과학수학 — 수리 기반
    {"courseCode": "SCI1011", "jobIri": "Job_데이터분석", "weight": 0.60},
    {"courseCode": "SCI1011", "jobIri": "Job_AI엔지니어", "weight": 0.55},

    # 통합물리 — 반도체/물리 기반
    {"courseCode": "SCI1012", "jobIri": "Job_반도체",    "weight": 0.60},
    {"courseCode": "SCI1012", "jobIri": "Job_데이터분석", "weight": 0.50},

    # 통합화학 — 소재/반도체 기반
    {"courseCode": "SCI1013", "jobIri": "Job_반도체",    "weight": 0.60},

    # 통합생물학 — 데이터/AI 바이오 기반
    {"courseCode": "SCI1014", "jobIri": "Job_데이터분석", "weight": 0.55},
    {"courseCode": "SCI1014", "jobIri": "Job_AI엔지니어", "weight": 0.50},

    # 과학도를 위한 선형대수 — AI/데이터 핵심 기반
    {"courseCode": "SCI1021", "jobIri": "Job_AI엔지니어", "weight": 0.75},
    {"courseCode": "SCI1021", "jobIri": "Job_데이터분석", "weight": 0.70},
    {"courseCode": "SCI1021", "jobIri": "Job_소프트웨어", "weight": 0.60},
]


# ── MAIN ─────────────────────────────────────────────────────────────
BASE = '/home/user/Sogangproject'

# STEP 1: data_round1.py — expand Dept_FREE_SCI credits
print("=== STEP 1: data_round1.py ===")
with open(f'{BASE}/data_round1.py', encoding='utf-8') as f:
    r1 = f.read()
r1 = replace_credits(r1, 'Dept_FREE_SCI', DEPT_FREE_SCI_CREDITS_FULL)
with open(f'{BASE}/data_round1.py', 'w', encoding='utf-8') as f:
    f.write(r1)
print("data_round1.py written.\n")

# STEP 2: data_round2.py — fix SCI course fields
print("=== STEP 2: data_round2.py ===")
with open(f'{BASE}/data_round2.py', encoding='utf-8') as f:
    r2 = f.read()

# 2a. SCI1001 credits 3 → 0 (0학점 과목)
print("  Fixing SCI1001 credits: 3 → 0...")
r2, ok = fix_int_field_by_code(r2, 'SCI1001', 'credits', 3, 0)
if ok: print("    SCI1001: credits 3 → 0")

# 2b. graduationCategory '전공필수' → '전공입문' (모든 SCI 기반필수)
print("  Fixing graduationCategory: 전공필수 → 전공입문 (6 SCI courses)...")
for code in SCI_CAT_TO_PREMAJOR:
    r2, ok = fix_str_field_by_code(r2, code, 'graduationCategory', '전공필수', '전공입문')
    if ok:
        print(f"    {code}: 전공필수 → 전공입문")

# 2c. countsTowardMajorCredits True → False (전공입문 미포함)
print("  Fixing countsTowardMajorCredits: True → False (6 SCI courses)...")
for code in SCI_COUNTS_FALSE:
    r2, ok = fix_bool_field_by_code(r2, code, 'countsTowardMajorCredits', 'True', 'False')
    if ok:
        print(f"    {code}: countsTowardMajorCredits True → False")

with open(f'{BASE}/data_round2.py', 'w', encoding='utf-8') as f:
    f.write(r2)
print("data_round2.py written.\n")

# STEP 3: data_round4.py — add SCI job fits
print("=== STEP 3: data_round4.py ===")
with open(f'{BASE}/data_round4.py', encoding='utf-8') as f:
    r4 = f.read()
r4 = add_job_fits(r4, SCI_COURSE_JOB_FITS, 'SCI')
with open(f'{BASE}/data_round4.py', 'w', encoding='utf-8') as f:
    f.write(r4)
print("data_round4.py written.\n")

print("=== ALL SCIENCE기반 자유전공학부 PATCHES APPLIED ===")
