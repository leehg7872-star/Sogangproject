"""
models.py — 공유 Pydantic 요청/응답 모델
"""

from pydantic import BaseModel


class MajorEntry(BaseModel):
    dept:        str = ""
    deptIri:     str = ""
    enrollType:  str = ""
    role:        str = ""
    track:       str = ""
    specialCond: str = ""
    order:       int = 1


class StudentProfile(BaseModel):
    name:        str = ""
    studentId:   str = ""
    major:       str = ""
    deptIri:     str = ""
    track:       str = ""
    majorIri:    str = ""
    currentYS:   str = "3-1"
    military:    str = "해당없음"
    credits:     int = 0
    job:         str = ""
    secondaryMajor: str = ""
    thirdMajor:     str = ""
    majors:         list[MajorEntry] = []
    hasTeacherCert: bool = False
    hasBSMS:        bool = False
    completed:   str = ""
    activities:  str = ""
    internships: str = ""
    certs:       str = ""
    industries:  str = ""
    region:      str = ""
    time:        str = ""


class PlannerRequest(BaseModel):
    profile: StudentProfile


class GradeEntry(BaseModel):
    code:  str
    grade: str  # "A+","A0","B+","B0","C+","C0","D+","D0","F","P"


class RebalanceRequest(BaseModel):
    profile:           StudentProfile
    newCompletedCodes: list[str] = []        # 이번 학기 이수 과목 코드
    newGrades:         list[GradeEntry] = [] # 성적 (F/D 감지, GPA 계산)
    newActivities:     str = ""              # 신규 비교과 활동
    leaveOfAbsence:    int = 0               # 추가 휴학 학기 수
    majorChange:       str = ""              # 전공 변경 시 새 전공명
    currentGpa:        float = 0.0           # 현재 누적 GPA


class RecommenderRequest(BaseModel):
    profile:    StudentProfile
    sortBy:     str = "fit"
    filterType: str = "all"


class OpportunitiesRequest(BaseModel):
    profile: StudentProfile


class AlumniRequest(BaseModel):
    profile: StudentProfile
