"""
data_round2_meta.py — 하위 호환 stub

data_round2.py 재설계 이후 모든 메타데이터(semOpen1/2, yearMin, avgGpa, description)가
data_round2.COURSES 각 레코드에 직접 포함됩니다.

이 파일은 기존 코드의 import 오류를 막기 위한 호환성 stub입니다.
새 코드에서는 data_round2.COURSES의 필드를 직접 사용하세요.
"""
import sys
sys.path.insert(0, __file__.replace("data_round2_meta.py", ""))
from data_round2 import COURSES as _COURSES

# 하위 호환: COURSE_META[courseCode] = {sem_open_1, sem_open_2, year_min, avg_gpa, description}
COURSE_META: dict[str, dict] = {
    c["courseCode"]: {
        "sem_open_1":  c.get("semOpen1", True),
        "sem_open_2":  c.get("semOpen2", True),
        "year_min":    c.get("yearMin", 1),
        "avg_gpa":     c.get("avgGpa", 0.0),
        "description": c.get("description", ""),
    }
    for c in _COURSES
}
