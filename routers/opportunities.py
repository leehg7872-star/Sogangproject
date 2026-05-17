"""
routers/opportunities.py — MODULE 04: 진로 기회 큐레이션

엔드포인트:
  POST /api/opportunities

흐름:
  Step 1  위비티·공모전코리아 실공고 스크래핑 (async)
  Step 2  비스크래핑 사이트 검증 URL 풀 생성
  Step 3  LLM 가중 유사도 채점 (직무50% / 경험30% / 자격증20%)
  Step 4  정렬 + 중복 제거 → 반환
"""

import json
import urllib.parse as _urlparse
from fastapi import APIRouter

from models import OpportunitiesRequest
from utils.common import major_display
from utils.scraper import scrape_contests
from utils.career import get_career_profile
from utils.llm import llm_json

router = APIRouter()

# ── 비스크래핑 사이트 URL 풀 ───────────────────────────────────────
_URL_SOURCES: dict[str, dict] = {
    "링커리어":     {"tpl": "https://linkareer.com/search?query={q}",                               "tag": "대외활동"},
    "캠퍼스픽활동": {"tpl": "https://www.campuspick.com/activity?search={q}",                       "tag": "대외활동"},
    "캠퍼스픽공모": {"tpl": "https://www.campuspick.com/competition?search={q}",                    "tag": "공모전"},
    "사람인":       {"tpl": "https://www.saramin.co.kr/zf_user/search?searchword={q}&search_area=main", "tag": "인턴"},
    "잡코리아":     {"tpl": "https://www.jobkorea.co.kr/Search/?stext={q}",                         "tag": "인턴"},
    "KOTRA":        {"tpl": "https://www.kotra.or.kr/search?query={q}",                             "tag": "대외활동"},
    "한국무역협회": {"tpl": "https://www.kita.net/search.do?query={q}",                             "tag": "대외활동"},
    "서강대취업":   {"url": "https://career.sogang.ac.kr/board/job_list.html",                      "tag": "교내"},
    "서강대국제처": {"url": "https://international.sogang.ac.kr/programs",                          "tag": "교내"},
}

OPPORTUNITIES_SYSTEM = """서강대학교 진로 기회 매칭 AI.

아래 가중치로 학생 프로파일과 각 공고의 유사도(match, 0~100)를 계산하세요.

[가중치]
- 목표직무 · 관심산업 (50%): 공고 직무/분야가 목표직무·관심산업과 얼마나 일치하는가
- 비교과 · 인턴 · 프로젝트 경험 (30%): 공고에서 요구하는 경험·역량이 학생 활동 이력과 얼마나 겹치는가
- 자격증 · 어학점수 (20%): 공고 지원 조건이 보유 자격증·어학과 얼마나 일치하는가

채점 기준:
- url_type이 "scraped"인 공고: 실제 제목·설명 내용 기반으로 정밀 채점
- url_type이 "verified_search"인 공고: 직무 키워드 기반 추정 채점

출력 JSON (배열, match 내림차순, 최대 10개):
[
  {
    "tag":      "공모전|대외활동|인턴|교내",
    "org":      "기관명",
    "title":    "공고 제목",
    "deadline": "마감일 또는 상시",
    "match":    85,
    "reason":   "어떤 가중치 항목이 높았는지 한 줄 포함한 매칭 이유",
    "url":      "입력 url 그대로",
    "url_type": "입력 url_type 그대로"
  }
]

규칙:
- url·url_type은 반드시 입력 데이터에서 그대로 복사 (변경·생성 금지)
- 동일 org에서 가장 높은 match 1개만 선택
"""


def _site_url(src_key: str, query: str = "") -> str:
    src = _URL_SOURCES.get(src_key, {})
    if "tpl" in src:
        return src["tpl"].format(q=_urlparse.quote(query))
    return src.get("url", f"https://www.google.com/search?q={_urlparse.quote(query)}")


def _build_url_pool(job: str, major: str, industries: list[str]) -> list[dict]:
    """JS 사이트용 검색 URL 풀 (링크만 제공)"""
    kw_job  = job
    kw_full = f"{job} {major}".strip()
    kw_ind  = industries[0] if industries else job

    return [
        {"tag": "대외활동", "org": "링커리어",    "title": f"{kw_job} 서포터즈·대외활동",
         "description": "", "deadline": "",
         "url": _site_url("링커리어", f"{kw_job} 대외활동"),  "url_type": "verified_search"},

        {"tag": "공모전",   "org": "캠퍼스픽",    "title": f"{kw_ind} 분야 공모전·챌린지",
         "description": "", "deadline": "",
         "url": _site_url("캠퍼스픽공모", kw_ind),            "url_type": "verified_search"},

        {"tag": "대외활동", "org": "캠퍼스픽",    "title": f"{kw_job} 대외활동",
         "description": "", "deadline": "",
         "url": _site_url("캠퍼스픽활동", kw_job),            "url_type": "verified_search"},

        {"tag": "인턴",     "org": "사람인",       "title": f"{kw_job} 신입·인턴 채용",
         "description": "", "deadline": "",
         "url": _site_url("사람인", kw_full),                  "url_type": "verified_search"},

        {"tag": "인턴",     "org": "잡코리아",     "title": f"{kw_full} 인턴 공고",
         "description": "", "deadline": "",
         "url": _site_url("잡코리아", kw_full),                "url_type": "verified_search"},

        {"tag": "대외활동", "org": "KOTRA",        "title": f"KOTRA {kw_job} 글로벌 청년 프로그램",
         "description": "", "deadline": "",
         "url": _site_url("KOTRA", kw_job),                    "url_type": "verified_search"},

        {"tag": "대외활동", "org": "한국무역협회", "title": f"한국무역협회 {kw_job} 프로그램",
         "description": "", "deadline": "",
         "url": _site_url("한국무역협회", kw_job),             "url_type": "verified_search"},

        {"tag": "교내",     "org": "서강대 취업지원팀", "title": "서강대 취업지원팀 채용·인턴 공고",
         "description": "", "deadline": "",
         "url": _site_url("서강대취업"),                       "url_type": "verified_search"},

        {"tag": "교내",     "org": "서강대 국제처",    "title": "서강대 해외연수·글로벌 프로그램",
         "description": "", "deadline": "",
         "url": _site_url("서강대국제처"),                     "url_type": "verified_search"},
    ]


def _dedup(opps: list[dict]) -> list[dict]:
    seen_org_tag: set[str] = set()
    result: list[dict]     = []
    for o in opps:
        key = f"{o.get('org','')}|{o.get('tag','')}".lower()
        if key not in seen_org_tag:
            seen_org_tag.add(key)
            result.append(o)
    return result


@router.post("/api/opportunities")
async def opportunities(req: OpportunitiesRequest):
    """MODULE 04: 진로 기회 큐레이션 (스크래핑 + URL풀 하이브리드)"""
    p          = req.profile
    job        = p.job or "취업"
    major      = major_display(p)
    industries = [i.strip() for i in (p.industries or "").split(",") if i.strip()]

    # Step 1: 위비티·공모전코리아 실공고 스크래핑 + career profile 동시 실행
    import asyncio
    scraped, career = await asyncio.gather(
        scrape_contests(job, p.industries or ""),
        get_career_profile(p),
    )
    print(f"[OPP] 스크래핑 결과: {len(scraped)}건")

    # Step 2: 비스크래핑 사이트 URL 풀
    url_pool = _build_url_pool(job, major, industries)

    # Step 3: LLM 가중 유사도 채점
    all_posts = scraped + url_pool
    act       = career.get("normalized_activities", {})
    context = {
        "profile": {
            "job":              job,
            "industries":       p.industries or "",
            "activity_summary": act.get("category_summary", p.activities or "없음"),
            "activity_skills":  act.get("skill_tags", []),
            "certs":            p.certs or "",
            "major":            major,
        },
        "weight_guide": {
            "직무·산업 (50%)":     "목표직무·관심산업과 공고 분야 일치도",
            "경험·활동 (30%)":     "activity_skills와 공고 요구 역량 겹침 정도",
            "자격증·어학 (20%)":   "certs와 공고 지원 조건 일치도",
        },
        "postings": all_posts,
    }

    result = await llm_json(
        OPPORTUNITIES_SYSTEM,
        f"다음 데이터로 가중 유사도를 계산하세요:\n{json.dumps(context, ensure_ascii=False, indent=2)}",
        max_tokens=2500,
    )

    if not isinstance(result, list):
        result = []

    # Step 4: 정렬 + 중복 제거
    result.sort(key=lambda x: -x.get("match", 0))
    result = _dedup(result)

    # url 누락 시 원본 풀에서 복원
    post_url_map = {p["title"]: p["url"] for p in all_posts}
    for o in result:
        if not o.get("url"):
            o["url"]      = post_url_map.get(o.get("title", ""), "")
            o["url_type"] = "verified_search"

    high_count  = sum(1 for o in result if o.get("match", 0) >= 80)
    scraped_cnt = sum(1 for o in result if o.get("url_type") == "scraped")

    return {
        "opportunities":    result,
        "total":            len(result),
        "high_match_count": high_count,
        "scraped_count":    scraped_cnt,
        "job":              job,
        "industries":       p.industries or "미입력",
        "region":           p.region     or "미입력",
    }
