#!/usr/bin/env python3
"""
apply_all_patches.py — Single orchestrator for all Sogang Career Copilot data patches.

Patch groups (in application order):
  1. TIC / TIR / GMT / GEC / GME  — loaded from external upload modules
  2. GKE / MAT v1 + v2            — loaded from external upload modules
  3. CHM  (화학과)
  4. BIO  (생명과학과)
  5. PHY  (물리학과)
  6. FREE_SCI (SCIENCE기반 자유전공학부)
"""

import importlib.util
import sys

from patch_utils import (
    replace_credits, fix_str_field, fix_int_field, fix_bool_field,
    apply_course_corrections, add_courses, add_code_shares, add_job_fits,
)
from data_patches import chm, bio, phy, free_sci

BASE   = '/home/user/Sogangproject'
UPLOAD = '/root/.claude/uploads/71451745-3a79-4399-b27c-aeba0a485746'


# ── helpers ──────────────────────────────────────────────────────────────────

def read(name):
    with open(f'{BASE}/{name}', encoding='utf-8') as f:
        return f.read()

def write(name, content):
    with open(f'{BASE}/{name}', 'w', encoding='utf-8') as f:
        f.write(content)

def load_upload(fname):
    path = f'{UPLOAD}/{fname}'
    spec = importlib.util.spec_from_file_location(fname, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── GROUP 1: TIC / TIR / GMT / GEC / GME ────────────────────────────────────

def apply_group1():
    print('\n══════════════════════════════════════════')
    print('GROUP 1: TIC / TIR / GMT / GEC / GME')
    print('══════════════════════════════════════════')

    print('Loading upload modules...')
    tic = load_upload('8116ef5d-data_tic_patch.py')
    tir = load_upload('0d793756-data_tir_patch.py')
    gmt = load_upload('5a791cc8-data_gmt_patch.py')
    gec = load_upload('2894042d-data_gec_patch.py')
    gme = load_upload('76918760-data_gme_patch.py')

    # data_round1.py
    print('\n--- data_round1.py ---')
    r1 = read('data_round1.py')
    r1 = replace_credits(r1, 'Dept_TIC', tic.DEPT_TIC_CREDITS_FULL)
    r1 = replace_credits(r1, 'Dept_TIR', tir.DEPT_TIR_CREDITS_FULL)
    r1 = replace_credits(r1, 'Dept_GMT', gmt.DEPT_GMT_CREDITS_FULL)
    r1 = replace_credits(r1, 'Dept_GME', gme.DEPT_GME_CREDITS_FULL)
    r1 = replace_credits(r1, 'Dept_GIS', gec.DEPT_GEC_FULL['credits'],
                         also_code_prefix=('GIS', 'GEC'))
    write('data_round1.py', r1)

    # data_round2.py
    print('\n--- data_round2.py ---')
    r2 = read('data_round2.py')
    r2, n = apply_course_corrections(r2, tic.TIC_COURSE_CORRECTIONS)
    print(f'  TIC: {n} courses corrected')
    r2, n = apply_course_corrections(r2, tir.TIR_COURSE_CORRECTIONS)
    print(f'  TIR: {n} courses corrected')
    r2, n = apply_course_corrections(r2, gmt.GMT_COURSE_CORRECTIONS)
    print(f'  GMT: {n} courses corrected')
    r2, n = apply_course_corrections(r2, gme.GME_COURSE_CORRECTIONS)
    print(f'  GME: {n} courses corrected')
    r2, ok = fix_str_field(r2, 'GIS1001', 'courseName', '글로벌융학학부입문', '글로벌융합학부입문')
    if ok: print('  GIS1001 name fixed')
    r2 = add_courses(r2, tic.TIC_COURSE_NEW + tir.TIR_COURSE_NEW +
                         gec.GEC_COURSE_NEW + gme.GME_COURSE_NEW)
    write('data_round2.py', r2)

    # data_round3.py
    print('\n--- data_round3.py ---')
    r3 = read('data_round3.py')
    r3 = add_code_shares(r3, tic.TIC_CODE_SHARES)
    write('data_round3.py', r3)

    # data_round4.py
    print('\n--- data_round4.py ---')
    r4 = read('data_round4.py')
    for label, fits in [('TIC', tic.TIC_COURSE_JOB_FITS), ('TIR', tir.TIR_COURSE_JOB_FITS),
                        ('GMT', gmt.GMT_COURSE_JOB_FITS), ('GEC', gec.GEC_COURSE_JOB_FITS),
                        ('GME', gme.GME_COURSE_JOB_FITS)]:
        r4 = add_job_fits(r4, fits, label)
    write('data_round4.py', r4)


# ── GROUP 2: GKE / MAT ───────────────────────────────────────────────────────

def apply_group2():
    print('\n══════════════════════════════════════════')
    print('GROUP 2: GKE / MAT v1 + v2')
    print('══════════════════════════════════════════')

    print('Loading upload modules...')
    gke   = load_upload('0d506021-data_gke_patch.py')
    matv1 = load_upload('438c9c5a-data_mat_patch_v1.py')
    matv2 = load_upload('5b263538-data_mat_patch_v2.py')

    # data_round1.py
    print('\n--- data_round1.py ---')
    r1 = read('data_round1.py')
    r1 = replace_credits(r1, 'Dept_GKE', gke.DEPT_GKE_CREDITS_FULL)
    r1 = replace_credits(r1, 'Dept_MAT', matv1.DEPT_MAT_CREDITS_FULL)
    write('data_round1.py', r1)

    # data_round2.py
    print('\n--- data_round2.py ---')
    r2 = read('data_round2.py')
    r2, n = apply_course_corrections(r2, gke.GKE_COURSE_CORRECTIONS)
    print(f'  GKE: {n} courses corrected')

    fix = matv1.MAT_COURSE_NAME_FIX[0]
    r2, ok = fix_str_field(r2, fix['courseCode'], 'courseName',
                           fix['현재_courseName'], fix['수정_courseName'])
    if ok: print(f"  MAT3020 name fixed → '{fix['수정_courseName']}'")

    r2, n = apply_course_corrections(r2, matv2.MAT_COURSE_CORRECTIONS)
    print(f'  MAT v2: {n} courses corrected')

    bio_fix  = matv2.BIO1102_FIX['필드별_정정']
    code     = matv2.BIO1102_FIX['courseCode']
    r2, ok1 = fix_str_field(r2, code, 'courseName',  bio_fix['courseName']['현재'],  bio_fix['courseName']['정정'])
    r2, ok2 = fix_int_field(r2, code, 'credits',     bio_fix['credits']['현재'],     bio_fix['credits']['정정'])
    r2, ok3 = fix_str_field(r2, code, 'description', bio_fix['description']['현재'], bio_fix['description']['정정'])
    r2, ok4 = fix_str_field(r2, code, 'hoursInfo',   bio_fix['hoursInfo']['현재'],   bio_fix['hoursInfo']['정정'])
    print(f'  BIO1102: name={ok1}, credits={ok2}, desc={ok3}, hours={ok4}')

    r2 = add_courses(r2, gke.GKE_COURSE_NEW + matv1.MAT_COURSE_NEW)
    write('data_round2.py', r2)

    # data_round3.py
    print('\n--- data_round3.py ---')
    r3 = read('data_round3.py')
    r3 = add_code_shares(r3, matv1.MAT_CODE_SHARES)
    write('data_round3.py', r3)

    # data_round4.py
    print('\n--- data_round4.py ---')
    r4 = read('data_round4.py')
    r4 = add_job_fits(r4, gke.GKE_COURSE_JOB_FITS,  'GKE')
    r4 = add_job_fits(r4, matv1.MAT_COURSE_JOB_FITS, 'MAT')
    write('data_round4.py', r4)


# ── GROUP 3: CHM ─────────────────────────────────────────────────────────────

def apply_group3():
    print('\n══════════════════════════════════════════')
    print('GROUP 3: CHM (화학과)')
    print('══════════════════════════════════════════')

    print('\n--- data_round1.py ---')
    r1 = read('data_round1.py')
    r1 = replace_credits(r1, 'Dept_CHM', chm.DEPT_CHM_CREDITS_FULL)
    write('data_round1.py', r1)

    print('\n--- data_round2.py ---')
    r2 = read('data_round2.py')
    for code in chm.CAT_TO_REQUIRED:
        r2, ok = fix_str_field(r2, code, 'graduationCategory', '전공선택', '전공필수')
        if ok: print(f'  {code}: 전공선택 → 전공필수')
    for code in chm.CAT_TO_ELECTIVE_CORE:
        r2, ok = fix_str_field(r2, code, 'graduationCategory', '전공선택', '전공필수선택')
        if ok: print(f'  {code}: 전공선택 → 전공필수선택')
    for code in chm.COUNTS_FALSE:
        r2, ok = fix_bool_field(r2, code, 'countsTowardMajorCredits', 'True', 'False')
        if ok: print(f'  {code}: countsTowardMajorCredits → False')
    write('data_round2.py', r2)

    print('\n--- data_round4.py ---')
    r4 = read('data_round4.py')
    r4 = add_job_fits(r4, chm.CHM_COURSE_JOB_FITS, 'CHM')
    write('data_round4.py', r4)


# ── GROUP 4: BIO ─────────────────────────────────────────────────────────────

def apply_group4():
    print('\n══════════════════════════════════════════')
    print('GROUP 4: BIO (생명과학과)')
    print('══════════════════════════════════════════')

    print('\n--- data_round1.py ---')
    r1 = read('data_round1.py')
    r1 = replace_credits(r1, 'Dept_BIO', bio.DEPT_BIO_CREDITS_FULL)
    write('data_round1.py', r1)

    print('\n--- data_round2.py ---')
    r2 = read('data_round2.py')
    for code in bio.COUNTS_FALSE:
        r2, ok = fix_bool_field(r2, code, 'countsTowardMajorCredits', 'True', 'False')
        if ok: print(f'  {code}: countsTowardMajorCredits → False')
    write('data_round2.py', r2)

    print('\n--- data_round4.py ---')
    r4 = read('data_round4.py')
    r4 = add_job_fits(r4, bio.BIO_COURSE_JOB_FITS, 'BIO')
    write('data_round4.py', r4)


# ── GROUP 5: PHY ─────────────────────────────────────────────────────────────

def apply_group5():
    print('\n══════════════════════════════════════════')
    print('GROUP 5: PHY (물리학과)')
    print('══════════════════════════════════════════')

    print('\n--- data_round1.py ---')
    r1 = read('data_round1.py')
    r1 = replace_credits(r1, 'Dept_PHY', phy.DEPT_PHY_CREDITS_FULL)
    write('data_round1.py', r1)

    print('\n--- data_round2.py ---')
    r2 = read('data_round2.py')
    for code in phy.CAT_TO_REQUIRED:
        r2, ok = fix_str_field(r2, code, 'graduationCategory', '전공선택', '전공필수')
        if ok: print(f'  {code}: 전공선택 → 전공필수')

    r2, ok = fix_str_field(r2, 'PHY4201', 'courseName', *phy.PHY4201_NAME_FIX)
    if ok: print("  PHY4201: courseName → '특수연구'")
    r2, ok = fix_int_field(r2, 'PHY4201', 'credits', 25, 3)
    if ok: print('  PHY4201: credits → 3')

    r2, ok = fix_str_field(r2, 'PHY4204', 'courseName', *phy.PHY4204_NAME_FIX)
    if ok: print("  PHY4204: courseName → '졸업프로젝트'")
    r2, ok = fix_str_field(r2, 'PHY4204', 'description', phy.PHY4204_DESC_FIX[0], phy.PHY4204_DESC_FIX[1])
    if ok: print("  PHY4204: description fixed")
    r2, ok = fix_int_field(r2, 'PHY4204', 'credits', 25, 3)
    if ok: print('  PHY4204: credits → 3')

    for code in phy.COUNTS_FALSE:
        r2, ok = fix_bool_field(r2, code, 'countsTowardMajorCredits', 'True', 'False')
        if ok: print(f'  {code}: countsTowardMajorCredits → False')
    write('data_round2.py', r2)

    print('\n--- data_round4.py ---')
    r4 = read('data_round4.py')
    r4 = add_job_fits(r4, phy.PHY_COURSE_JOB_FITS, 'PHY')
    write('data_round4.py', r4)


# ── GROUP 6: FREE_SCI ────────────────────────────────────────────────────────

def apply_group6():
    print('\n══════════════════════════════════════════')
    print('GROUP 6: FREE_SCI (SCIENCE기반 자유전공학부)')
    print('══════════════════════════════════════════')

    print('\n--- data_round1.py ---')
    r1 = read('data_round1.py')
    r1 = replace_credits(r1, 'Dept_FREE_SCI', free_sci.DEPT_FREE_SCI_CREDITS_FULL)
    write('data_round1.py', r1)

    print('\n--- data_round2.py ---')
    r2 = read('data_round2.py')
    r2, ok = fix_int_field(r2, 'SCI1001', 'credits', 3, 0)
    if ok: print('  SCI1001: credits 3 → 0')
    for code in free_sci.SCI_CAT_TO_PREMAJOR:
        r2, ok = fix_str_field(r2, code, 'graduationCategory', '전공필수', '전공입문')
        if ok: print(f'  {code}: 전공필수 → 전공입문')
    for code in free_sci.SCI_COUNTS_FALSE:
        r2, ok = fix_bool_field(r2, code, 'countsTowardMajorCredits', 'True', 'False')
        if ok: print(f'  {code}: countsTowardMajorCredits → False')
    write('data_round2.py', r2)

    print('\n--- data_round4.py ---')
    r4 = read('data_round4.py')
    r4 = add_job_fits(r4, free_sci.SCI_COURSE_JOB_FITS, 'SCI')
    write('data_round4.py', r4)


# ── ENTRY POINT ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Each group can be selectively skipped by passing group numbers as args,
    # e.g. `python apply_all_patches.py 3 4 5 6` to skip groups 1 and 2
    # (which require the external upload files to be present).
    groups = {1: apply_group1, 2: apply_group2, 3: apply_group3,
              4: apply_group4, 5: apply_group5, 6: apply_group6}

    run = {int(x) for x in sys.argv[1:]} if len(sys.argv) > 1 else set(groups)

    for num, fn in groups.items():
        if num in run:
            fn()

    print('\n══════════════════════════════════════════')
    print('ALL PATCHES APPLIED SUCCESSFULLY')
    print('══════════════════════════════════════════')
