# 파트: integrate — 통합과 데모 리허설 (담당 권순오, 팀 전원 참관)

## 목표
main에서 데모 시나리오 8단계가 실제 텔레그램과 Actions로 끝까지 돈다. 반복 금지 검사(매뉴얼 7단계)를 통과한다.

## 선행 조건
- parse, classify, bot PR 머지 완료 (dashboard는 없어도 진행)
- Secrets 6개 등록 (HUMAN_TODO 6), Actions 활성화 (HUMAN_TODO 7)

## 절차
1. `git checkout main && git pull --rebase origin main` → `git checkout -b chore/integrate`
2. `python -m pytest -q` 전체 통과를 확인한다. 실패하면 원인 파일과 소유자를 보고한다. 계약(collab-plan 4장)과 다르게 구현한 쪽이 고친다. 사용자가 "고쳐"라고 하면 직접 고친다.
3. `scripts/demo_check.py`를 만든다. db.py로 다음을 출력하는 읽기 전용 스크립트다.
   - 최근 거래 10건(id, ts, cp_label, amount, direction, category, status, asked_at 유무)
   - open splits
   - 이번 달 monthly_summary
   - 출력에 키는 넣지 않는다.
4. 데이터 초기화 여부를 사용자에게 묻는다. 동의하면 `scripts/reset_demo.py`를 만들어 실행한다. transactions, splits, settlements, rules, counterparties, merchant_cache를 비우되 settings는 유지한다. **service key가 가리키는 프로젝트가 데모용인지 다시 확인한다.**
5. 사용자와 함께 시나리오를 실행한다. 각 단계마다 사용자가 텔레그램에 입력하고 → 내가 `gh workflow run watch` → `gh run watch` → `python scripts/demo_check.py`로 기대값과 비교한다.

   | # | 사용자 입력 | 기대 |
   |---|---|---|
   | 1 | `스벅 6500` | cafe, auto, 질문 없음 |
   | 2 | `46000 교촌치킨` | food, `[엔빵]` 질문 |
   | 3 | 2번 질문에 답장 `4명` | ✅ · 4명 엔빵 (내 몫 11,500원) |
   | 4 | `50000 상대A 이체` | transfer, 질문 |
   | 5 | 4번 버튼 `주거·통신` | ✅, rules hits=1 |
   | 6 | `+11500 상대B` 3회 | 매번 정산 반영, 마지막 받을 돈 0 |
   | 7 | 아무것도 안 하고 스케줄 2회 대기 | 재질문 없음, `update state` 커밋 2개 |
   | 8 | 대시보드 접속 | 이번 달 식비 11,500원 |

   `gh`가 없으면 사용자에게 Actions 탭에서 Run workflow를 누르라고 안내하고, 결과 확인만 내가 한다.
6. 어긋난 단계는 원인을 찾아 보고한다. 수정이 필요한 파일 소유자를 명시한다.
7. 성공하면 `docs/demo-log.md`에 각 단계 결과를 1줄씩 기록한다. 금액은 데모 값만, 실명은 쓰지 않는다. 사용자에게 텔레그램과 Actions 탭 캡처를 `docs/demo/`에 넣으라고 안내한다.
8. 커밋 → PR → 머지.

## 완료 기준
- [ ] 시나리오 1~7 성공 (8은 dashboard 배포 후)
- [ ] Actions 기록에 초록 체크가 연속 2회 이상, `update state` 커밋 존재
- [ ] `docs/demo-log.md` 작성

## 다음
`check`
