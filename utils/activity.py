"""
utils/activity.py — 비교과 활동·인턴십 자유 텍스트 정규화

제안서 세부업무 #3 (나):
  "비정형 입력(비교과 이력 free-text)의 표준 카테고리 분류"
  예) "멋쟁이사자처럼 프론트엔드 파트장"
   → category: "IT동아리", skills: ["프론트엔드 개발", "리더십"], role: "leader"
"""

from utils.llm import llm_json

_NORMALIZE_SYSTEM = """당신은 대학생 비교과 활동 분류 AI입니다.
자유 텍스트로 입력된 비교과 활동·인턴십 이력을 표준 구조로 분류하세요.

표준 카테고리 (category 필드에 사용):
  IT동아리 | 학술동아리 | 봉사동아리 | 문화동아리 | 학생회
  공모전_수상 | 공모전_참가 | 논문_연구 | 학부연구생
  기업인턴 | 스타트업인턴 | 공공기관인턴
  해외연수 | 교환학생 | 어학연수
  프로젝트 | 자격증취득 | 기타

출력 JSON 구조:
{
  "items": [
    {
      "raw":      "원문 그대로",
      "category": "표준 카테고리 1개",
      "skills":   ["역량·기술 태그", ...],
      "role":     "leader | member | individual",
      "duration": "기간 (명시된 경우만, 없으면 빈 문자열)"
    }
  ],
  "skill_tags":       ["전체 통합 스킬 태그 (중복 제거)"],
  "category_summary": "활동 이력 한 줄 요약 (예: IT동아리 리더, 기업인턴 2회)"
}

규칙:
- 쉼표·줄바꿈으로 구분된 활동을 각각 items 한 항목으로 파싱
- 활동이 없거나 입력이 비어 있으면 {"items":[], "skill_tags":[], "category_summary":"없음"}
- 입력에 명시되지 않은 내용을 추가하지 말 것"""

# 세션 캐시 (key: activities|internships 원문)
_activity_cache: dict[str, dict] = {}

_EMPTY_RESULT = {"items": [], "skill_tags": [], "category_summary": "없음"}


async def normalize_activities(activities: str, internships: str = "") -> dict:
    """
    비교과 활동·인턴십 자유 텍스트 → 표준 구조화 결과 반환 (캐시 적용).

    반환 예시:
    {
      "items": [
        {"raw": "멋쟁이사자처럼 파트장", "category": "IT동아리",
         "skills": ["프론트엔드", "리더십"], "role": "leader", "duration": ""}
      ],
      "skill_tags": ["프론트엔드", "리더십"],
      "category_summary": "IT동아리 리더"
    }
    """
    combined = f"{activities.strip()}|{internships.strip()}"
    if not activities.strip() and not internships.strip():
        return _EMPTY_RESULT

    if combined in _activity_cache:
        return _activity_cache[combined]

    raw_input = ""
    if activities.strip():
        raw_input += f"[비교과 활동]\n{activities.strip()}\n"
    if internships.strip():
        raw_input += f"[인턴십·프로젝트 경험]\n{internships.strip()}"

    result = await llm_json(_NORMALIZE_SYSTEM, raw_input.strip(), max_tokens=800)

    if not isinstance(result, dict):
        result = dict(_EMPTY_RESULT)
    result.setdefault("items",            [])
    result.setdefault("skill_tags",       [])
    result.setdefault("category_summary", "없음")

    _activity_cache[combined] = result
    print(f"[ACTIVITY] 정규화 완료: {len(result['items'])}개 항목 → {result['category_summary']}")
    return result
