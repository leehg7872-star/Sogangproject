"""
utils/scraper.py — 공모전·채용 사이트 비동기 스크래퍼

지원 사이트 (정적 HTML):
  - 위비티 (wevity.com)
  - 공모전코리아 (contestkorea.com)
  - 서강대 취업지원팀 (career.sogang.ac.kr)

반환 구조:
  {"tag", "org", "title", "description", "deadline", "url", "url_type", "source"}
"""

import asyncio
import httpx
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_TIMEOUT  = 8.0
_MAX_ITEMS = 15


async def _fetch(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(
            headers=_HEADERS, follow_redirects=True, timeout=_TIMEOUT
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.text
    except Exception as e:
        print(f"[SCRAPER] fetch 실패: {url} — {e}")
        return None


# ── 위비티 ────────────────────────────────────────────────────────

async def scrape_wevity(keyword: str) -> list[dict]:
    """위비티 공모전 검색 결과 파싱"""
    import urllib.parse
    url  = f"https://www.wevity.com/?c=find&s={urllib.parse.quote(keyword)}"
    html = await _fetch(url)
    if not html:
        return []

    soup    = BeautifulSoup(html, "html.parser")
    results = []

    # 위비티 리스트 셀렉터 (복수 후보 — 사이트 업데이트 시 조정)
    items = (
        soup.select("ul.list > li")
        or soup.select(".ctt-list li")
        or soup.select(".list-wrap li")
        or soup.select(".contest-list li")
    )

    for item in items[:_MAX_ITEMS]:
        title_el    = (item.select_one(".tit")
                       or item.select_one("strong.tit")
                       or item.select_one("p.tit")
                       or item.select_one("h3")
                       or item.select_one("strong"))
        deadline_el = (item.select_one(".due")
                       or item.select_one(".dday")
                       or item.select_one(".date"))
        org_el      = (item.select_one(".host")
                       or item.select_one(".org")
                       or item.select_one(".company"))
        desc_el     = (item.select_one(".desc")
                       or item.select_one(".txt")
                       or item.select_one("p.info"))
        link_el     = item.select_one("a[href]")

        if not title_el:
            continue

        href = link_el["href"] if link_el else ""
        if href and not href.startswith("http"):
            href = "https://www.wevity.com" + href

        results.append({
            "tag":         "공모전",
            "org":         org_el.get_text(strip=True) if org_el else "위비티",
            "title":       title_el.get_text(strip=True),
            "description": desc_el.get_text(strip=True)[:120] if desc_el else "",
            "deadline":    deadline_el.get_text(strip=True) if deadline_el else "",
            "url":         href or url,
            "url_type":    "scraped",
            "source":      "위비티",
        })

    print(f"[SCRAPER] 위비티: {len(results)}건 수집 (키워드: {keyword!r})")
    return results


# ── 공모전코리아 ───────────────────────────────────────────────────

async def scrape_contestkorea(keyword: str) -> list[dict]:
    """공모전코리아 검색 결과 파싱"""
    import urllib.parse
    url  = f"https://www.contestkorea.com/sub/list.php?str={urllib.parse.quote(keyword)}"
    html = await _fetch(url)
    if not html:
        return []

    soup    = BeautifulSoup(html, "html.parser")
    results = []

    # 공모전코리아 리스트 셀렉터 (복수 후보)
    items = (
        soup.select("ul.contest_lists > li")
        or soup.select(".list_body tr")
        or soup.select("div.list-wrap li")
        or soup.select(".competition-list li")
    )

    for item in items[:_MAX_ITEMS]:
        title_el    = (item.select_one(".int_title")
                       or item.select_one(".title")
                       or item.select_one("td.tit")
                       or item.select_one("strong")
                       or item.select_one("h4"))
        deadline_el = (item.select_one(".due_date")
                       or item.select_one(".date")
                       or item.select_one("td.end"))
        org_el      = (item.select_one(".host_name")
                       or item.select_one(".host")
                       or item.select_one("td.host"))
        desc_el     = (item.select_one(".desc")
                       or item.select_one(".summary")
                       or item.select_one("td.summary"))
        link_el     = item.select_one("a[href]")

        if not title_el:
            continue

        href = link_el["href"] if link_el else ""
        if href and not href.startswith("http"):
            href = "https://www.contestkorea.com" + href

        results.append({
            "tag":         "공모전",
            "org":         org_el.get_text(strip=True) if org_el else "공모전코리아",
            "title":       title_el.get_text(strip=True),
            "description": desc_el.get_text(strip=True)[:120] if desc_el else "",
            "deadline":    deadline_el.get_text(strip=True) if deadline_el else "",
            "url":         href or url,
            "url_type":    "scraped",
            "source":      "공모전코리아",
        })

    print(f"[SCRAPER] 공모전코리아: {len(results)}건 수집 (키워드: {keyword!r})")
    return results


# ── 서강대 취업지원팀 ─────────────────────────────────────────────

_SOGANG_CAREER_BASE = "https://career.sogang.ac.kr"
_SOGANG_JOB_LIST    = f"{_SOGANG_CAREER_BASE}/board/job_list.html"


async def scrape_sogang_jobs(keyword: str = "") -> list[dict]:
    """서강대 취업지원팀 채용공고 게시판 파싱"""
    url  = _SOGANG_JOB_LIST
    html = await _fetch(url)
    if not html:
        return []

    soup    = BeautifulSoup(html, "html.parser")
    results = []

    # 서강대 취업게시판 셀렉터 (복수 후보)
    items = (
        soup.select("table.board_list tbody tr")
        or soup.select("ul.board_list > li")
        or soup.select(".bbs_list tr")
        or soup.select("table.list_table tbody tr")
        or soup.select(".job-list li")
    )

    for item in items[:_MAX_ITEMS]:
        # 제목 셀렉터
        title_el = (
            item.select_one("td.subject a")
            or item.select_one("td.title a")
            or item.select_one(".tit a")
            or item.select_one("a[href]")
        )
        # 기업/기관명
        org_el = (
            item.select_one("td.company")
            or item.select_one("td.org")
            or item.select_one(".company")
        )
        # 마감일
        deadline_el = (
            item.select_one("td.due")
            or item.select_one("td.date")
            or item.select_one(".end_date")
            or item.select_one("td:last-child")
        )

        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        if not title or title in ("", "제목"):  # 헤더 행 제외
            continue

        # 키워드 필터링 (키워드가 주어진 경우)
        if keyword:
            kw_lower = keyword.lower()
            if kw_lower not in title.lower():
                continue

        href = title_el.get("href", "")
        if href and not href.startswith("http"):
            href = _SOGANG_CAREER_BASE + "/" + href.lstrip("/")

        results.append({
            "tag":         "채용·인턴",
            "org":         org_el.get_text(strip=True) if org_el else "서강대 취업지원팀",
            "title":       title,
            "description": "",
            "deadline":    deadline_el.get_text(strip=True) if deadline_el else "",
            "url":         href or _SOGANG_JOB_LIST,
            "url_type":    "scraped",
            "source":      "서강대취업지원팀",
        })

    print(f"[SCRAPER] 서강대 취업지원팀: {len(results)}건 수집")
    return results


# ── 통합 진입점 ────────────────────────────────────────────────────

async def scrape_contests(job: str, industries: str = "") -> list[dict]:
    """
    위비티 + 공모전코리아 동시 스크래핑.
    키워드: 목표직무 단독, 관심산업 단독 — 두 쿼리 병렬 실행 후 병합
    """
    kw_job = job.strip()
    kw_ind = industries.split(",")[0].strip() if industries else ""

    queries = [kw_job]
    if kw_ind and kw_ind != kw_job:
        queries.append(kw_ind)

    tasks = []
    for kw in queries[:2]:  # 최대 2개 키워드
        tasks.append(scrape_wevity(kw))
        tasks.append(scrape_contestkorea(kw))

    # 서강대 취업지원팀은 직무 키워드로 필터링 (없으면 전체)
    tasks.append(scrape_sogang_jobs(kw_job))

    batch   = await asyncio.gather(*tasks, return_exceptions=True)
    merged  = []
    seen    = set()

    for result in batch:
        if isinstance(result, Exception):
            continue
        for item in result:
            key = item["title"].strip()
            if key not in seen:
                seen.add(key)
                merged.append(item)

    print(f"[SCRAPER] 병합 결과: {len(merged)}건 (중복제거 후)")
    return merged
