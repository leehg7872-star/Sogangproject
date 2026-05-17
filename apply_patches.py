#!/usr/bin/env python3
"""apply_patches.py — Apply all 5 department patches sequentially."""
import re, sys, os

def py_repr(obj):
    """Serialize Python obj to compact single-quoted Python literal."""
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


def replace_credits(content, iri, new_credits_dict, also_code_prefix=None):
    """Replace 'credits' dict for a dept IRI. Optionally also replace code_prefix."""
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if f"'iri': '{iri}'" not in line:
            continue
        # Replace code_prefix if requested
        if also_code_prefix:
            old_cp, new_cp = also_code_prefix
            line = line.replace(f"'code_prefix': '{old_cp}'", f"'code_prefix': '{new_cp}'")
        # Find 'credits': { ... }
        start = line.find("'credits': {")
        if start == -1:
            print(f"  WARNING: no 'credits' key found for {iri}")
            lines[i] = line
            continue
        credits_start = start + len("'credits': ")
        depth = 0
        j = credits_start
        while j < len(line):
            if line[j] == '{': depth += 1
            elif line[j] == '}':
                depth -= 1
                if depth == 0:
                    credits_end = j + 1
                    break
            j += 1
        new_credits_str = py_repr(new_credits_dict)
        lines[i] = line[:credits_start] + new_credits_str + line[credits_end:]
        print(f"  [OK] Replaced credits for {iri}")
        break
    return '\n'.join(lines)


def fix_course_field(content, code, field, old_val, new_val):
    """In data_round2.py, for a course with courseCode=code, replace field value."""
    old_str = f"'{field}': '{old_val}'"
    new_str = f"'{field}': '{new_val}'"
    # Only replace within the line containing this courseCode
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if f"'courseCode': '{code}'" in line:
            if old_str in line:
                lines[i] = line.replace(old_str, new_str, 1)
                return '\n'.join(lines), True
            else:
                print(f"  WARNING: {code} line does not contain '{old_str}' — skipping")
                return '\n'.join(lines), False
    print(f"  WARNING: courseCode '{code}' not found in file")
    return content, False


def apply_course_corrections(content, corrections):
    """Apply a list of course correction dicts to data_round2.py content."""
    count = 0
    for c in corrections:
        code = c['courseCode']
        cur_type = c['현재_courseType']
        new_type = c['수정_courseType']
        cur_cat  = c['현재_graduationCategory']
        new_cat  = c['수정_graduationCategory']
        changed = False
        if cur_type != new_type:
            content, ok = fix_course_field(content, code, 'courseType', cur_type, new_type)
            if ok: changed = True
        if cur_cat != new_cat:
            content, ok = fix_course_field(content, code, 'graduationCategory', cur_cat, new_cat)
            if ok: changed = True
        if changed:
            count += 1
            print(f"    fixed {code}: type={new_type}, cat={new_cat}")
    return content, count


def add_courses_to_round2(content, new_courses):
    """Append new course dicts to the COURSES list in data_round2.py."""
    # Find the last item line and the closing bracket of COURSES
    # Insert before the last ']' that closes COURSES
    # Find COURSES = [ ... ]
    # The list ends with a line that is just ']'
    lines = content.split('\n')
    # Find the closing ] of COURSES list
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped == ']':
            # Insert new courses before this closing bracket
            insert_lines = []
            for course in new_courses:
                # Build single-line dict string
                items = ', '.join(f"'{k}': {py_repr(v)}" for k, v in course.items() if k != '비고')
                insert_lines.append(f"    {{{items}}},")
            lines[i:i] = insert_lines
            print(f"  [OK] Added {len(new_courses)} new course(s) to COURSES")
            return '\n'.join(lines)
    print("  WARNING: Could not find closing ']' for COURSES list")
    return content


def add_code_shares(content, shares):
    """Append new CODE_SHARES pairs to data_round3.py."""
    # Find CODE_SHARES = [ ... ]
    lines = content.split('\n')
    # Find first occurrence of CODE_SHARES list closing ]
    in_code_shares = False
    for i, line in enumerate(lines):
        if 'CODE_SHARES' in line and '= [' in line:
            in_code_shares = True
        if in_code_shares and line.strip() == ']':
            insert_lines = []
            for pair in shares:
                a = pair.get('a') or pair.get('code_a')
                b = pair.get('b') or pair.get('code_b')
                note = pair.get('note', '')
                insert_lines.append(f"    {{'code_a': '{a}', 'code_b': '{b}', 'note': {py_repr(note)}}},")
            lines[i:i] = insert_lines
            print(f"  [OK] Added {len(shares)} CODE_SHARES pairs")
            return '\n'.join(lines)
    print("  WARNING: Could not find CODE_SHARES closing ']'")
    return content


def add_job_fits(content, fits, label):
    """Append COURSE_JOB_FITS entries to data_round4.py."""
    lines = content.split('\n')
    # Find COURSE_JOB_FITS list's closing ]
    in_fits = False
    for i, line in enumerate(lines):
        if 'COURSE_JOB_FITS' in line and '= [' in line:
            in_fits = True
        if in_fits and line.strip() == ']':
            insert_lines = []
            for fit in fits:
                code = fit['courseCode']
                job  = fit['jobIri']
                w    = fit['weight']
                insert_lines.append(f"    {{'courseCode': '{code}', 'jobIri': '{job}', 'weight': {w}}},")
            lines[i:i] = insert_lines
            print(f"  [OK] Added {len(fits)} {label} job fits")
            return '\n'.join(lines)
    print("  WARNING: Could not find COURSE_JOB_FITS closing ']'")
    return content


# ============================================================
# Import patch data
# ============================================================
sys.path.insert(0, '/root/.claude/uploads/71451745-3a79-4399-b27c-aeba0a485746')
import importlib.util

def load_patch(filename):
    spec = importlib.util.spec_from_file_location(
        filename, f'/root/.claude/uploads/71451745-3a79-4399-b27c-aeba0a485746/{filename}')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

print("Loading patch modules...")
tic = load_patch('8116ef5d-data_tic_patch.py')
tir = load_patch('0d793756-data_tir_patch.py')
gmt = load_patch('5a791cc8-data_gmt_patch.py')
gec = load_patch('2894042d-data_gec_patch.py')
gme = load_patch('76918760-data_gme_patch.py')
print("All patch modules loaded.\n")

BASE = '/home/user/Sogangproject'

# ============================================================
# STEP 1: Patch data_round1.py
# ============================================================
print("=== STEP 1: Patching data_round1.py ===")
with open(f'{BASE}/data_round1.py', 'r', encoding='utf-8') as f:
    r1 = f.read()

r1 = replace_credits(r1, 'Dept_TIC', tic.DEPT_TIC_CREDITS_FULL)
r1 = replace_credits(r1, 'Dept_TIR', tir.DEPT_TIR_CREDITS_FULL)
r1 = replace_credits(r1, 'Dept_GMT', gmt.DEPT_GMT_CREDITS_FULL)
r1 = replace_credits(r1, 'Dept_GME', gme.DEPT_GME_CREDITS_FULL)
# GIS: replace entire entry using DEPT_GEC_FULL
# code_prefix GIS->GEC and full credits
r1 = replace_credits(r1, 'Dept_GIS', gec.DEPT_GEC_FULL['credits'], also_code_prefix=('GIS', 'GEC'))

with open(f'{BASE}/data_round1.py', 'w', encoding='utf-8') as f:
    f.write(r1)
print("data_round1.py written.\n")

# ============================================================
# STEP 2: Patch data_round2.py
# ============================================================
print("=== STEP 2: Patching data_round2.py ===")
with open(f'{BASE}/data_round2.py', 'r', encoding='utf-8') as f:
    r2 = f.read()

print("  Applying TIC corrections...")
r2, n = apply_course_corrections(r2, tic.TIC_COURSE_CORRECTIONS)
print(f"  TIC: {n} courses corrected")

print("  Applying TIR corrections...")
r2, n = apply_course_corrections(r2, tir.TIR_COURSE_CORRECTIONS)
print(f"  TIR: {n} courses corrected")

print("  Applying GMT corrections (GIS1001-GIS2005, GMT4xxx)...")
r2, n = apply_course_corrections(r2, gmt.GMT_COURSE_CORRECTIONS)
print(f"  GMT: {n} courses corrected")

print("  Applying GME corrections...")
r2, n = apply_course_corrections(r2, gme.GME_COURSE_CORRECTIONS)
print(f"  GME: {n} courses corrected")

print("  Fixing GIS1001 courseName typo...")
r2, ok = fix_course_field(r2, 'GIS1001', 'courseName', '글로벌융학학부입문', '글로벌융합학부입문')
if ok: print("    GIS1001 name fixed")

print("  Adding new courses...")
all_new = (tic.TIC_COURSE_NEW + tir.TIR_COURSE_NEW +
           gec.GEC_COURSE_NEW + gme.GME_COURSE_NEW)
r2 = add_courses_to_round2(r2, all_new)

with open(f'{BASE}/data_round2.py', 'w', encoding='utf-8') as f:
    f.write(r2)
print("data_round2.py written.\n")

# ============================================================
# STEP 3: Patch data_round3.py
# ============================================================
print("=== STEP 3: Patching data_round3.py ===")
with open(f'{BASE}/data_round3.py', 'r', encoding='utf-8') as f:
    r3 = f.read()

r3 = add_code_shares(r3, tic.TIC_CODE_SHARES)

with open(f'{BASE}/data_round3.py', 'w', encoding='utf-8') as f:
    f.write(r3)
print("data_round3.py written.\n")

# ============================================================
# STEP 4: Patch data_round4.py
# ============================================================
print("=== STEP 4: Patching data_round4.py ===")
with open(f'{BASE}/data_round4.py', 'r', encoding='utf-8') as f:
    r4 = f.read()

r4 = add_job_fits(r4, tic.TIC_COURSE_JOB_FITS, 'TIC')
r4 = add_job_fits(r4, tir.TIR_COURSE_JOB_FITS, 'TIR')
r4 = add_job_fits(r4, gmt.GMT_COURSE_JOB_FITS, 'GMT')
r4 = add_job_fits(r4, gec.GEC_COURSE_JOB_FITS, 'GEC')
r4 = add_job_fits(r4, gme.GME_COURSE_JOB_FITS, 'GME')

with open(f'{BASE}/data_round4.py', 'w', encoding='utf-8') as f:
    f.write(r4)
print("data_round4.py written.\n")

print("=== ALL PATCHES APPLIED SUCCESSFULLY ===")
