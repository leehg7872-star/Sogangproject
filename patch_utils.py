#!/usr/bin/env python3
"""Shared text-manipulation helpers for patching data_round*.py files."""


def py_repr(obj):
    """Serialize a Python object to a compact single-quoted Python literal."""
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
    """Replace the 'credits' dict for a dept IRI in data_round1.py content."""
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if f"'iri': '{iri}'" not in line:
            continue
        if also_code_prefix:
            old_cp, new_cp = also_code_prefix
            line = line.replace(f"'code_prefix': '{old_cp}'", f"'code_prefix': '{new_cp}'")
        start = line.find("'credits': {")
        if start == -1:
            print(f"  WARNING: no 'credits' key found for {iri}")
            lines[i] = line
            continue
        credits_start = start + len("'credits': ")
        depth, j = 0, credits_start
        while j < len(line):
            if line[j] == '{': depth += 1
            elif line[j] == '}':
                depth -= 1
                if depth == 0:
                    credits_end = j + 1
                    break
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


def fix_bool_field(content, code, field, old_val, new_val):
    """Replace a boolean field value for a given courseCode."""
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
    """Apply a list of course correction dicts to data_round2.py content."""
    count = 0
    for c in corrections:
        code     = c['courseCode']
        cur_type = c['현재_courseType'];      new_type = c['수정_courseType']
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
    """Append new course dicts to the COURSES list in data_round2.py."""
    lines = content.split('\n')
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == ']':
            inserts = []
            for course in new_courses:
                items = ', '.join(f"'{k}': {py_repr(v)}" for k, v in course.items() if k != '비고')
                inserts.append(f"    {{{items}}},")
            lines[i:i] = inserts
            print(f"  [OK] Added {len(new_courses)} new course(s) to COURSES")
            return '\n'.join(lines)
    print("  WARNING: Could not find closing ']' for COURSES list")
    return content


def add_code_shares(content, shares):
    """Append new CODE_SHARES pairs to data_round3.py."""
    lines = content.split('\n')
    in_list = False
    for i, line in enumerate(lines):
        if 'CODE_SHARES' in line and '= [' in line:
            in_list = True
        if in_list and line.strip() == ']':
            inserts = []
            for pair in shares:
                a    = pair.get('a') or pair.get('code_a')
                b    = pair.get('b') or pair.get('code_b')
                note = pair.get('note', '')
                inserts.append(f"    {{'code_a': '{a}', 'code_b': '{b}', 'note': {py_repr(note)}}},")
            lines[i:i] = inserts
            print(f"  [OK] Added {len(shares)} CODE_SHARES pairs")
            return '\n'.join(lines)
    print("  WARNING: Could not find CODE_SHARES closing ']'")
    return content


def add_job_fits(content, fits, label):
    """Append COURSE_JOB_FITS entries to data_round4.py."""
    lines = content.split('\n')
    in_list = False
    for i, line in enumerate(lines):
        if 'COURSE_JOB_FITS' in line and '= [' in line:
            in_list = True
        if in_list and line.strip() == ']':
            inserts = [
                f"    {{'courseCode': '{f['courseCode']}', 'jobIri': '{f['jobIri']}', 'weight': {f['weight']}}},"
                for f in fits
            ]
            lines[i:i] = inserts
            print(f"  [OK] Added {len(fits)} {label} job fits")
            return '\n'.join(lines)
    print("  WARNING: Could not find COURSE_JOB_FITS closing ']'")
    return content
