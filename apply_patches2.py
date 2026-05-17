#!/usr/bin/env python3
"""apply_patches2.py — Apply GKE and MAT (v1+v2) patches."""
import importlib.util, sys, re

# ── helpers (same as apply_patches.py) ──────────────────────────────
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


def fix_str_field(content, code, field, old_val, new_val):
    """Replace a string field value for a given courseCode."""
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


def fix_int_field(content, code, field, old_val, new_val):
    """Replace an integer field value for a given courseCode."""
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


def apply_course_corrections(content, corrections):
    count = 0
    for c in corrections:
        code = c['courseCode']
        cur_type = c['현재_courseType'];  new_type = c['수정_courseType']
        cur_cat  = c['현재_graduationCategory']; new_cat = c['수정_graduationCategory']
        changed = False
        if cur_type != new_type:
            content, ok = fix_str_field(content, code, 'courseType', cur_type, new_type)
            if ok: changed = True
        if cur_cat != new_cat:
            content, ok = fix_str_field(content, code, 'graduationCategory', cur_cat, new_cat)
            if ok: changed = True
        if changed:
            count += 1
            print(f"    fixed {code}: type={new_type}, cat={new_cat}")
    return content, count


def add_courses(content, new_courses):
    lines = content.split('\n')
    for i in range(len(lines)-1, -1, -1):
        if lines[i].strip() == ']':
            inserts = []
            for c in new_courses:
                items = ', '.join(f"'{k}': {py_repr(v)}" for k, v in c.items() if k != '비고')
                inserts.append(f"    {{{items}}},")
            lines[i:i] = inserts
            print(f"  [OK] Added {len(new_courses)} new course(s)")
            return '\n'.join(lines)
    print("  WARNING: closing ']' not found")
    return content


def add_code_shares(content, shares):
    lines = content.split('\n')
    in_list = False
    for i, line in enumerate(lines):
        if 'CODE_SHARES' in line and '= [' in line:
            in_list = True
        if in_list and line.strip() == ']':
            inserts = []
            for pair in shares:
                a = pair.get('a') or pair.get('code_a')
                b = pair.get('b') or pair.get('code_b')
                note = pair.get('note', '')
                inserts.append(f"    {{'code_a': '{a}', 'code_b': '{b}', 'note': {py_repr(note)}}},")
            lines[i:i] = inserts
            print(f"  [OK] Added {len(shares)} CODE_SHARES pairs")
            return '\n'.join(lines)
    print("  WARNING: CODE_SHARES closing ']' not found")
    return content


def add_job_fits(content, fits, label):
    lines = content.split('\n')
    in_list = False
    for i, line in enumerate(lines):
        if 'COURSE_JOB_FITS' in line and '= [' in line:
            in_list = True
        if in_list and line.strip() == ']':
            inserts = [f"    {{'courseCode': '{f['courseCode']}', 'jobIri': '{f['jobIri']}', 'weight': {f['weight']}}}," for f in fits]
            lines[i:i] = inserts
            print(f"  [OK] Added {len(fits)} {label} job fits")
            return '\n'.join(lines)
    print("  WARNING: COURSE_JOB_FITS closing ']' not found")
    return content


# ── load patch modules ───────────────────────────────────────────────
UPLOAD = '/root/.claude/uploads/71451745-3a79-4399-b27c-aeba0a485746'

def load_patch(fname):
    spec = importlib.util.spec_from_file_location(fname, f'{UPLOAD}/{fname}')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

print("Loading patch modules...")
gke   = load_patch('0d506021-data_gke_patch.py')
matv1 = load_patch('438c9c5a-data_mat_patch_v1.py')
matv2 = load_patch('5b263538-data_mat_patch_v2.py')
print("All 3 patch modules loaded.\n")

BASE = '/home/user/Sogangproject'

# ────────────────────────────────────────────────────────────────────
# STEP 1: data_round1.py — GKE + MAT credits
# ────────────────────────────────────────────────────────────────────
print("=== STEP 1: data_round1.py ===")
with open(f'{BASE}/data_round1.py', encoding='utf-8') as f: r1 = f.read()

r1 = replace_credits(r1, 'Dept_GKE', gke.DEPT_GKE_CREDITS_FULL)
r1 = replace_credits(r1, 'Dept_MAT', matv1.DEPT_MAT_CREDITS_FULL)

with open(f'{BASE}/data_round1.py', 'w', encoding='utf-8') as f: f.write(r1)
print("data_round1.py written.\n")

# ────────────────────────────────────────────────────────────────────
# STEP 2: data_round2.py — corrections + new courses + BIO1102 fix
# ────────────────────────────────────────────────────────────────────
print("=== STEP 2: data_round2.py ===")
with open(f'{BASE}/data_round2.py', encoding='utf-8') as f: r2 = f.read()

# GKE: 30 course corrections (IntroductoryCourse → ElectiveCourse)
print("  Applying GKE corrections (GKE3001–GKE3030)...")
r2, n = apply_course_corrections(r2, gke.GKE_COURSE_CORRECTIONS)
print(f"  GKE: {n} courses corrected")

# MAT v1: name fix for MAT3020
print("  Fixing MAT3020 courseName...")
fix = matv1.MAT_COURSE_NAME_FIX[0]
r2, ok = fix_str_field(r2, fix['courseCode'], 'courseName',
                       fix['현재_courseName'], fix['수정_courseName'])
if ok: print(f"    MAT3020 name fixed → '{fix['수정_courseName']}'")

# MAT v2: corrections (MAT4120 ElectiveCourse → RequiredCourse)
print("  Applying MAT v2 corrections (MAT4120)...")
r2, n = apply_course_corrections(r2, matv2.MAT_COURSE_CORRECTIONS)
print(f"  MAT v2: {n} courses corrected")

# MAT v2: BIO1102 data damage fix
print("  Fixing BIO1102 data damage...")
bio_fix = matv2.BIO1102_FIX['필드별_정정']
code = matv2.BIO1102_FIX['courseCode']
r2, ok1 = fix_str_field(r2, code, 'courseName',
    bio_fix['courseName']['현재'], bio_fix['courseName']['정정'])
r2, ok2 = fix_int_field(r2, code, 'credits',
    bio_fix['credits']['현재'], bio_fix['credits']['정정'])
r2, ok3 = fix_str_field(r2, code, 'description',
    bio_fix['description']['현재'], bio_fix['description']['정정'])
r2, ok4 = fix_str_field(r2, code, 'hoursInfo',
    bio_fix['hoursInfo']['현재'], bio_fix['hoursInfo']['정정'])
if all([ok1, ok2, ok3, ok4]):
    print(f"    BIO1102: all 4 fields fixed")
else:
    print(f"    BIO1102: partial fix (name={ok1}, credits={ok2}, desc={ok3}, hours={ok4})")

# Add new courses: GKE (KLC1002) + MAT v1 (STS2006)
print("  Adding new courses (KLC1002, STS2006)...")
all_new = gke.GKE_COURSE_NEW + matv1.MAT_COURSE_NEW
r2 = add_courses(r2, all_new)

with open(f'{BASE}/data_round2.py', 'w', encoding='utf-8') as f: f.write(r2)
print("data_round2.py written.\n")

# ────────────────────────────────────────────────────────────────────
# STEP 3: data_round3.py — MAT code shares
# ────────────────────────────────────────────────────────────────────
print("=== STEP 3: data_round3.py ===")
with open(f'{BASE}/data_round3.py', encoding='utf-8') as f: r3 = f.read()
r3 = add_code_shares(r3, matv1.MAT_CODE_SHARES)
with open(f'{BASE}/data_round3.py', 'w', encoding='utf-8') as f: f.write(r3)
print("data_round3.py written.\n")

# ────────────────────────────────────────────────────────────────────
# STEP 4: data_round4.py — job fits
# ────────────────────────────────────────────────────────────────────
print("=== STEP 4: data_round4.py ===")
with open(f'{BASE}/data_round4.py', encoding='utf-8') as f: r4 = f.read()
r4 = add_job_fits(r4, gke.GKE_COURSE_JOB_FITS,   'GKE')
r4 = add_job_fits(r4, matv1.MAT_COURSE_JOB_FITS,  'MAT')
with open(f'{BASE}/data_round4.py', 'w', encoding='utf-8') as f: f.write(r4)
print("data_round4.py written.\n")

print("=== ALL GKE + MAT PATCHES APPLIED ===")
