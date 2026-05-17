"""
routers/dashboard.py — 대시보드 모듈

엔드포인트:
  POST /api/profile    학생 프로파일 저장 → 대시보드 stat-box 반환
  POST /api/transcript 이수표 파일 분석 (멀티모달 LLM + DB 검증)
"""

import re, json, base64
from fastapi import APIRouter, HTTPException, UploadFile, File

import deps
from models import PlannerRequest
from utils.common import major_display
from utils.graduation import graduation_req
from utils.career import get_career_profile
from utils.llm import llm

router = APIRouter()

# ── 이수표 분석 프롬프트 ─────────────────────────────────────────
TRANSCRIPT_SYSTEM = """당신은 서강대학교 과목이수표 분석 AI입니다.
이수표에 있는 모든 과목을 빠짐없이 추출하세요. 일부만 추출하거나 생략하지 마세요.

출력 JSON 구조 (배열, 이수한 모든 과목 포함):
[
  {"code": "CHI2001", "name": "전공기초중국어Ⅰ", "credits": 3, "sem": "21-2"}
]

규칙:
- code: 영문 2~4자 + 숫자 4자리 (예: CHI2001, EEE3005, CSE3080)
- sem: 연도2자리-학기 (예: 21-2, 22-1) — 불명확하면 ""
- credits: 숫자, 불명확하면 3
- 이수표에 보이는 과목은 전공/교양/어학 불문하고 전부 포함
- 추출 불가능한 경우만 빈 배열 [] 반환"""


# ════════════════════════════════════════════════════════════════
# POST /api/profile
# ════════════════════════════════════════════════════════════════

@router.post("/api/profile")
async def profile_save(req: PlannerRequest):
    """프로파일 저장 후 대시보드 stat-box 반환 + career profile 선생성·캐싱"""
    p         = req.profile
    grad      = graduation_req(p)
    total_req = grad.get("totalCredits", 130)
    career    = await get_career_profile(p)
    remaining = max(0, total_req - p.credits)
    pct       = round((p.credits / total_req) * 100) if total_req else 0

    return {
        "d_major":          major_display(p),
        "d_id":             f"{p.studentId} · {p.currentYS.replace('-', '학년 ')}학기",
        "d_credits":        p.credits,
        "d_credits_pct":    f"{pct}% 진행",
        "d_remaining":      remaining,
        "d_remaining_sub":  "졸업까지 남은 학점",
        "d_job":            p.job or "미정",
        "d_track":          grad.get("variant", p.track),
        "d_total_req":      total_req,
        "career_keywords":  career.get("keywords", [])[:6],
        "career_rationale": career.get("rationale", ""),
    }


# ════════════════════════════════════════════════════════════════
# POST /api/transcript
# ════════════════════════════════════════════════════════════════

def _validate_transcript_courses(courses: list) -> tuple[list, list]:
    """추출된 과목 코드를 KUZU DB와 교차 검증"""
    valid, invalid = [], []
    code_pattern = re.compile(r'^[A-Z]{2,4}\d{4}$')

    for c in courses:
        if not isinstance(c, dict):
            continue
        code = str(c.get("code", "")).strip().upper()

        if not code_pattern.match(code):
            invalid.append({"code": code, "reason": "코드 형식 불일치"})
            continue

        try:
            result = deps.kuzu_conn.execute(
                "MATCH (c:Course {courseCode: $code}) "
                "RETURN c.courseName, c.credits LIMIT 1",
                {"code": code}
            )
            if result.has_next():
                row = result.get_next()
                valid.append({
                    "code":    code,
                    "name":    row[0] or c.get("name", ""),
                    "credits": row[1] or c.get("credits", 3),
                    "sem":     c.get("sem", ""),
                    "source":  "db_verified",
                })
            else:
                valid.append({
                    "code":    code,
                    "name":    c.get("name", ""),
                    "credits": c.get("credits", 3),
                    "sem":     c.get("sem", ""),
                    "source":  "unverified",
                })
        except Exception:
            valid.append({**c, "code": code, "source": "unverified"})

    return valid, invalid


async def _extract_transcript_chunked(text: str, chunk_size: int = 6000) -> list:
    """긴 텍스트 이수표를 청크로 나눠 추출 후 병합"""
    if len(text) <= chunk_size:
        raw = await llm(TRANSCRIPT_SYSTEM,
                        f"다음 이수표 텍스트에서 모든 과목을 빠짐없이 추출하세요:\n{text}",
                        max_tokens=3000)
        raw = re.sub(r"```(?:json)?|```", "", raw).strip()
        match = re.search(r"\[[\s\S]*\]", raw)
        try:
            return json.loads(match.group(0) if match else raw)
        except Exception:
            return []

    all_courses: list = []
    seen_codes: set   = set()
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        raw = await llm(
            TRANSCRIPT_SYSTEM,
            f"다음 이수표 텍스트 일부({i//chunk_size+1}번째 구간)에서 과목을 추출하세요:\n{chunk}",
            max_tokens=2000,
        )
        raw = re.sub(r"```(?:json)?|```", "", raw).strip()
        match = re.search(r"\[[\s\S]*\]", raw)
        try:
            chunk_courses = json.loads(match.group(0) if match else raw)
            for c in chunk_courses:
                code = str(c.get("code", "")).strip().upper()
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    all_courses.append(c)
        except Exception:
            pass
    return all_courses


@router.post("/api/transcript")
async def transcript_analysis(file: UploadFile = File(...)):
    """이수표 파일 → 과목 목록 추출 (멀티모달 LLM + Python DB 검증)"""
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(400, "파일 크기는 10MB 이하여야 합니다.")

    content_bytes = await file.read()
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else ""

    if ext in ("jpg", "jpeg", "png"):
        b64        = base64.b64encode(content_bytes).decode()
        media_type = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        resp = await deps.openai_client.chat.completions.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[
                {"role": "system", "content": TRANSCRIPT_SYSTEM},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                    {"type": "text", "text": "이 이수표에 있는 모든 과목을 빠짐없이 추출하세요. 누락 없이 전부 포함해야 합니다."},
                ]},
            ],
        )
        raw_text = resp.choices[0].message.content
        raw_text = re.sub(r"```(?:json)?|```", "", raw_text).strip()
        match    = re.search(r"\[[\s\S]*\]", raw_text)
        try:
            courses_raw = json.loads(match.group(0) if match else raw_text)
        except Exception:
            courses_raw = []

    elif ext == "pdf":
        try:
            import fitz
            doc  = fitz.open(stream=content_bytes, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
        except Exception:
            text = content_bytes.decode("utf-8", errors="ignore")
        courses_raw = await _extract_transcript_chunked(text)

    else:
        text        = content_bytes.decode("utf-8", errors="ignore")
        courses_raw = await _extract_transcript_chunked(text)

    courses, invalid = _validate_transcript_courses(courses_raw)

    if invalid:
        print(f"[TRANSCRIPT] 무효 코드 필터링: {[i['code'] for i in invalid]}")

    db_verified   = sum(1 for c in courses if c.get("source") == "db_verified")
    total_credits = sum(c.get("credits", 0) for c in courses if isinstance(c, dict))

    return {
        "courses":      courses,
        "count":        len(courses),
        "totalCredits": total_credits,
        "db_verified":  db_verified,
        "unverified":   len(courses) - db_verified,
        "filtered":     len(invalid),
        "filename":     file.filename,
    }
