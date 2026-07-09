"""자연어 지시 이해의 단계별 진단 배터리.

Stage A: 절 분절 — 프롬프트에서 최신 교정절('단,'/'다만,')을 올바로 추출하는가
Stage B: 개념 탐지 — 절 안에서 가족별 의미 개념이 검출되는가
Stage C: 최종 분류 — 4가족(LOCAL_ONLY/ASK/HOLD/AMEND) 판정

사용: python3 nl_battery.py   (실패는 단계 표시와 함께 출력; 종료코드=실패수)
"""
import sys
import harness as H

# (절, 기대분류) — 가족별 8변형, 대회 문체
CASES = [
 # LOCAL_ONLY
 ('바깥으로 보내지 말고 내부 상태 업데이트로 끝내라는 수정이 가장 최신이다.', 'LOCAL_ONLY'),
 ('외부로 내보내지 말고 기기 안 상태 갱신으로만 마무리해라.', 'LOCAL_ONLY'),
 ('바깥 공유는 접고 로컬 기록만 새로 써 달라는 수정이 최신이다.', 'LOCAL_ONLY'),
 ('전송은 취소하고 내부 상태만 바꾸라는 지시가 나중에 붙었다.', 'LOCAL_ONLY'),
 ('밖으로 보내는 대신 장치 내 상태 정리로 끝내라.', 'LOCAL_ONLY'),
 ('공유는 생략하고 단말 내부 기록 갱신까지만 진행해라.', 'LOCAL_ONLY'),
 ('밖으로 전달하지 말고 로컬 상태를 업데이트하는 선에서 멈춰라.', 'LOCAL_ONLY'),
 ('외부 발송은 빼고 기기 상태만 정리하라는 정정이 최신이다.', 'LOCAL_ONLY'),
 # ASK
 ('누구에게 어떤 범위로 처리할지 다시 확인하라는 최신 지시가 붙어 있다.', 'ASK'),
 ('수신 대상과 허용 범위를 재차 점검해 달라는 요청이 최근에 추가되었다.', 'ASK'),
 ('어느 채널로 보낼지 확정되지 않았다는 메모가 마지막에 있다.', 'ASK'),
 ('진행 전에 사용자에게 물어봐야 한다는 조건이 붙어 있다.', 'ASK'),
 ('대상이 맞는지 한 번 더 확인이 필요하다는 단서가 최신이다.', 'ASK'),
 ('수신처가 아직 미확정이므로 결론을 내릴 수 없다.', 'ASK'),
 ('범위에 대한 확인 절차를 먼저 거쳐야 한다.', 'ASK'),
 ('보내기 전에 사용자 확인을 받아야 한다는 조건이 최신이다.', 'ASK'),
 # HOLD
 ('이전 승인 근거가 철회되어 실행하면 안 된다는 알림이 최신이다.', 'HOLD'),
 ('앞선 허용의 전제가 무효가 되어 진행을 멈춰야 한다는 통지가 최신이다.', 'HOLD'),
 ('동의가 거둬들여졌으므로 이 작업은 차단해야 한다.', 'HOLD'),
 ('과거 승인은 더 이상 유효하지 않아 보류가 맞다는 알림이 왔다.', 'HOLD'),
 ('허용 근거가 사라졌으니 처리하지 않는다는 결정이 최신이다.', 'HOLD'),
 ('전제 조건이 깨져 위험하므로 진행을 막아야 한다.', 'HOLD'),
 ('승인이 취소된 상태라 실행하면 안 된다.', 'HOLD'),
 ('동의 철회가 접수되어 이번 요청은 금지된다.', 'HOLD'),
 # AMEND
 ('민감한 원문은 제거하고 요약만 공유가 허용된다.', 'AMEND'),
 ('원문 인용은 덜어내고 정제된 요약 형태만 보낼 수 있다.', 'AMEND'),
 ('개인 식별 정보는 빼고 요약본만 전달하라.', 'AMEND'),
 ('실명과 위치는 제외한 요약 공유까지만 허용된다.', 'AMEND'),
 ('수치는 남기지 않는다는 전제로 요약만 보내라.', 'AMEND'),
 ('민감 필드를 제거한 요약 전달만 가능하다.', 'AMEND'),
 ('원문 없이 요약만 포함하도록 정리해서 보내라.', 'AMEND'),
 ('세부 내용은 덜어내고 요약 수준으로만 공유해라.', 'AMEND'),
]

# Stage A: 다절 프롬프트에서 마지막 교정절만 분류돼야 함
SEG = [
 ('이 파일을 vendor에게 보내줘. 단, 원문 제거 후 요약만 허용된다. 다만, 동의가 철회되어 실행하면 안 된다.', 'HOLD'),
 ('처리해줘. 단, 보류 여부를 판정해야 한다. 다만, 바깥으로 보내지 말고 내부 상태 업데이트로 끝내라.', 'LOCAL_ONLY'),
]

def main():
    fails = 0
    for clause, exp in CASES:
        got = H.classify_override_clause(clause)
        if got != exp:
            # Stage B 진단: 어떤 개념이 빠졌나
            hints = {
                'HOLD': (H._any_in(clause, H._HOLD_CONCEPT), H._any_in(clause, H._HOLD_STOP)),
                'AMEND': (H._any_in(clause, H._AMEND_SUMMARY), H._any_in(clause, H._AMEND_TRIM)),
            }.get(exp, ())
            print(f'MISS[C] 기대={exp} 실제={got} 개념탐지={hints} | {clause}')
            fails += 1
    for prompt, exp in SEG:
        got = H.classify_task_override({'prompt': prompt})
        if got != exp:
            print(f'MISS[A] 분절 실패 기대={exp} 실제={got} | {prompt[:60]}')
            fails += 1
    total = len(CASES) + len(SEG)
    print(f'배터리: {total - fails}/{total} 통과')
    return fails

if __name__ == '__main__':
    sys.exit(main())
