"""
routers/alumni.py — MODULE 05: 동문 진로 경로 패턴

엔드포인트:
  POST /api/alumni  동문 샘플 데이터 조회 + LLM 패턴 분석 리포트
"""

import json
from fastapi import APIRouter

from models import AlumniRequest
from utils.common import dept_iri_from_profile, major_display
from utils.llm import llm_json

router = APIRouter()

# 샘플 동문 데이터 (실제 연동: 취업지원팀 DB)
SAMPLE_ALUMNI_DATA = {
    "Dept_CHI": {
        "job_무역": {
            "total": 47,
            "top_companies": ["포스코인터내셔널", "LX인터내셔널", "삼성물산", "현대코퍼레이션", "코트라"],
            "common_courses": [
                {"code": "CHI4008", "name": "무역 중국어",               "pct": 89},
                {"code": "CHI3037", "name": "오늘의 중국경제",            "pct": 76},
                {"code": "CHI4015", "name": "중국진출기업 문화적 현지화",  "pct": 71},
                {"code": "CHI4014", "name": "글로벌라이제이션과 중국",     "pct": 65},
                {"code": "CHI3039", "name": "중국 경영의 이해",           "pct": 60},
            ],
            "common_certs": ["HSK 5급 이상", "BCT 중급 이상", "OPIc IH"],
            "avg_internship_months": 4.2,
        }
    }
}

ALUMNI_SYSTEM = """당신은 서강대학교 동문 진로 패턴 분석 AI입니다.
동문 데이터와 학생 프로파일을 받아 패턴 분석 리포트를 JSON으로 생성합니다.

출력 JSON 구조:
{
  "headline": "N명의 동문이 [직무]로 진출",
  "total_alumni": 47,
  "top_companies": ["회사1", "회사2", ...],
  "patterns": [
    {"code": "CHI4008", "name": "무역 중국어", "pct": 89, "bar_width": 89}
  ],
  "cert_patterns": ["HSK 5급 이상", "..."],
  "avg_internship": "4.2개월",
  "insight": "이 직무로 진출한 동문들의 공통 특징 2~3줄 분석"
}"""


@router.post("/api/alumni")
async def alumni(req: AlumniRequest):
    """MODULE 05: 동문 경로 패턴 분석"""
    p        = req.profile
    dept_iri = dept_iri_from_profile(p)

    dept_data = SAMPLE_ALUMNI_DATA.get(dept_iri, {})
    job_key   = None
    for key in dept_data:
        kw = key.replace("job_", "")
        if kw in p.job or p.job in kw:
            job_key = key
            break
    alumni_data = dept_data.get(job_key, {})

    context = {
        "profile": {
            "major":          major_display(p),
            "secondaryMajor": p.secondaryMajor or None,
            "thirdMajor":     p.thirdMajor     or None,
            "job":            p.job,
            "dept_iri":       dept_iri,
        },
        "alumni_data": alumni_data,
        "note": "동문 DB 연동 전 샘플 데이터 기반 분석",
    }

    result = await llm_json(
        ALUMNI_SYSTEM,
        f"다음 데이터로 동문 패턴 분석을 생성하세요:\n{json.dumps(context, ensure_ascii=False, indent=2)}",
    )
    return result if isinstance(result, dict) else {"error": "동문 분석 생성 실패"}
