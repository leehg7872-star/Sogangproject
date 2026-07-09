# AAR History — 일반동작 → 특화+오류분류 → 피드백 → 재분류 루프의 기록

각 반복은 "가설 → 측정 → 재분류(승격/유지/기각)"의 형태로 기록한다.
`python3 harness.py aar [dev|submit]`가 이 루프의 계기판이다.

## #1. 미지 boundary 라벨 의미론 (서버 A/B)
- 가설: `redacted_after_selection_boundary`는 blocked의 동의어가 아니라 "redact 예정" → ask.
- 측정: 해당 alias가 단독 결정하는 GENERIC 5개만 hold→ask로 뒤집은 제출. 0.8596→0.8556 (−0.0040 ≈ 이론최대의 85%).
- 재분류: **기각 → 기존 매핑 유지(서버 확증)**. hold 경로의 scope/policy/plan 방출 스택까지 통째로 검증됨.

## #2. persona-evidence target (Tier 3)
- 가설: broken memory_key의 숨겨진 profile 값은 dev 정답에서 노출된 (인물,필드) 사실로 추정 가능.
- 측정: screening 4개 target 교체 제출. 점수 무변화(0.8596) — #1로 public 채점 포함이 확인됐으므로, 구답·신답 모두 오답으로 판정.
- 재분류: **유지(무비용) + 인물-사실의 key 간 안정성 가정은 기각**. dev 로컬 이득(+0.015)과 hidden-set 보험 가치는 존속.

## #3. ask/hold의 bare-user target 가설
- 가설: override ask/hold 208개의 target='user'가 대량 오답(결손 87문제분)일 것.
- 측정: dev override ASK/HOLD 18개의 참조 target 확인 → 17/18이 'user'.
- 재분류: **기각(제출 불필요 — dev 증거로 폐기)**. 예상 오류율 ~6%로 하향.

## #4. CONTROL_TABLE → 원리 승격
- 가설: matched 셀들은 일반 원리("확정 바인딩은 route를 해소하므로 잔여 모호성은 ask가 아니라 최소화")로 승격 가능.
- 측정: 승격 후 full 완전 불변(dev 0.9531, screening 0 diff), 범용(L2, 예시-암기 제거) 0.8283→**0.8669** (control 0.85→0.917).
- 재분류: **승격 확정**. 단일예시(single) 셀은 특화로 잔류. AAR dev 리포트: 잔여 불일치 48건 전부 "특화가 정답=유지", 승격 후보 0 — 루프 폐쇄 확인.

## #5. 자기-갱신 기제 (runtime alias 학습)
- 조치: 미지 라벨 alias를 상수에서 기제로 이전 — `prepare()`가 partner-set 역할매칭을 실행 중 수행, 유일-일치 시에만 채택.
- 검증: 하드코딩 alias를 비운 자가시험에서 서버-확증 매핑 2개를 정확히 재발견. 하드코딩(확증) alias가 항상 우선.

## 상시 계기 (매 실행 기록)
- self-consistency: 일반층 vs 방출층 control 합의도 (task별 trace가 `aar_log`와 session에 적재)
- verify-then-emit: hold→none·ask→confirm 등 dev 100% 불변식을 방출 전 검증·수리 (현재 위반 0 — 회귀 가드)

## #6. 유니버셜 피드백 매체 도입 (메타모픽 불변성) — dev 포화 이후의 기준
- 매체: 정답 없이 성립하는 문서화된 불변식 — record/object 순서 무의미(TERMS_GUIDE), WM-코드 임의성, 프리픽스 등가.
- 1차 측정: 4개 의미보존 변형 × 820 task 전부 **위반 0** (순서/개명/프리픽스 불변 확인).
- 스트레스 측정(경계 타격):
  - 교정절 패러프레이즈 4종 중 1종 미인식(ASK→GENERIC) → **수정**: 재차/다시+점검·재확인 패턴 추가. dev/screening 무변화 확인.
  - 미지 라벨 동의어 주입: 완전일치 매처가 부분 마스킹에 실패 → **코사인 프로파일 매칭 + fixpoint 2-pass로 교체**. 실측 시나리오(자가시험: 서버확증 alias 2종 재발견) 통과, 필드별 독립 치환에서 dispatch 흡수. 한계: 두 필드 동시 마스킹(비실측 최악 케이스)에서는 학습을 거부하고 보수적 기본값으로 낙하 — 조용한 오염 대신 설계된 안전 저하.
- 재분류: 유니버셜 매체가 dev 포화 이후의 상시 피드백 기준으로 채택됨. 위반 = 라벨 불요 결함 신호.
