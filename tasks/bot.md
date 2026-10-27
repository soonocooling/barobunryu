# 파트: bot — 텔레그램·watch.py 본체 (담당 권순오)

## 목표
5분마다 실행되는 `watch.py`를 완성한다. 흐름: 입력 수신 → 거래 생성 → 분류 → 애매한 것만 질문 → 답장·버튼으로 확정 → 엔빵·정산 → 반복 금지.
해커톤 조건 ③(혼자 알린다)과 ④(비틀기)의 본체다.

## 소유 파일
`bot.py`, `watch.py`, `tests/test_watch.py`, `tests/fakedb.py`, `state.json`, `.github/workflows/watch.yml`

## 의존
- `parse.py`(조원영), `classify.py`·`db.py`(박세훈)
- **이들이 아직 스텁이어도 개발을 시작한다.** 테스트는 `tests/fakedb.py`(메모리 DB)와 monkeypatch로 돌린다. 실제 parse·classify가 머지되면 테스트가 그대로 통과해야 한다.

## 1. bot.py
- `get_updates(offset)`: `GET getUpdates` params `offset`, `timeout=0`, `allowed_updates=["message","callback_query"]` → `result` 리스트
- `send(text, buttons=None) -> message_id`: 이미 있음. `parse_mode`는 쓰지 않는다(특수문자 이스케이프 문제 회피).
- `edit(message_id, text, buttons=None)`: `editMessageText`. buttons가 None이면 키보드를 제거한다. "message is not modified" 오류는 무시한다.
- `answer_callback(cb_id, text=None)`: 만료(`query is too old`) 등 모든 오류를 무시한다.
- 모든 요청은 timeout 10초다. 4xx면 응답 본문 앞 200자를 담은 예외를 낸다. 토큰은 메시지에 넣지 않는다.

## 2. watch.py 실행 순서
```
main():
  load_env(); state = load_state(); s = db.get_settings(); t = now()
  asked_today가 오늘 날짜가 아니면 {"date": 오늘, "count": 0}으로 리셋
  updates = bot.get_updates(state["tg_offset"])
  for u in updates:
      try: handle_update(u)
      except Exception as e: print(오류)       # 한 건 실패가 나머지를 막지 않는다
      state["tg_offset"] = u["update_id"] + 1   # 실패해도 offset은 넘긴다(무한 재처리 방지)
  process_inbox()
  classify_new(s)
  ask_pending(s, state, t)
  digest(s, state, t)
  state["last_run"] = t.isoformat(timespec="seconds")
  save_state(state)
```
- `GITHUB_EVENT_NAME == "workflow_dispatch"`일 때 "봇이 살아 있습니다"를 보내던 뼈대 코드는 **삭제한다**(데모 때 스팸이 된다).
- 보안: `update`의 chat id가 `CHAT_ID`와 다르면 무시한다. 봇 아이디를 아는 누구나 메시지를 보낼 수 있기 때문이다.

## 3. handle_update(u)
**message**
- `/today`, `/month` → 요약 응답(7절)
- `/start`, `/help` → 사용법 3줄: `스벅 6500` / `+11500 세훈`(입금) / `50000 상대 이체`
- `reply_to_message`가 있으면 → `tg_message_id == reply_to_message.message_id`인 거래를 찾아 `apply_answer(txn, parse.parse_answer(text))`. 못 찾으면 "어느 거래인지 모르겠어"
- 그 외 → `parse.parse_manual(text)` → None이면 사용법 응답 / 아니면 `create_txn(txn, source="tg")`

**callback_query** (`data` 형식, 모두 64바이트 이내)
- `c:{txn_id}:{code}` → 카테고리 확정. `code == "split"`이면 원래 메시지를 "몇 명이서? 이 메시지에 답장해줘 (예: 4명)"로 편집한다(키보드 제거).
- `s:{split_id}:{income_txn_id}` → 해당 엔빵에 정산으로 연결(`matched_by=user`)
- `g:{income_txn_id}` → 일반 입금(`income`)으로 확정
- `j:{txn_id}:{n}` → "엔빵이었어?" 질문에 대한 예. `apply_answer(txn, {"split_n": n, ...})`
- 처리 후 `answer_callback(cb["id"])`

## 4. 거래 생성·분류
`create_txn(t, source)`:
1. 중복 검사: 같은 `amount`·`cp_key`이고 `ts`가 ±2분 안인 거래가 있으면 무시한다.
2. `key = db.cp_key(name, method)`
   - counterparties에 없으면 upsert한다.
   - 사람(transfer): `type="person"`, `alias="상대 #{기존 person 수+1}"`
   - 가맹점: `type="merchant"`, `alias=None`
3. `cp_label` = 가맹점이면 원문 이름, 사람이면 alias. **사람 실명은 어디에도 저장하지 않는다.**
4. transactions에 insert한다(`category=null`, `status="auto"`, `source`).
5. `direction == "in"`이면 `match_income(txn)`

`process_inbox()`:
- inbox `status=new` → `parse.parse_push(raw)`
  - 성공: `create_txn(..., source="auto")` → `raw_text=null`, `status=done`
  - 실패: `status=failed`, `raw_text=null`. "못 읽었어: {원문 앞 30자}"를 1회 보낸다(원문은 보내기 전에만 사용).

`classify_new(s)`:
- `category is null`인 거래마다 `classify.classify(txn, db.load_rules(), db.load_cache())`
- cache_row가 있으면 merchant_cache에 upsert한다.
- `status`:
  - `c < s["threshold"]` → pending
  - 엔빵 의심(`direction=out`, category ∈ {food, cafe, culture}, `amount >= s["split_suspect_min"]`) → pending
  - 그 외 → auto
- income으로 분류됐고 이미 정산 매칭된 거래는 건드리지 않는다(match_income이 먼저 category를 settlement로 채운다).

## 5. 질문 (ask_pending)
- 대상: `status=pending`, `asked_at is null`, `ts` 오름차순
- 지금이 조용한 시간(`quiet_start`~`quiet_end`)이거나 `asked_today.count >= daily_ask_cap`이면 보내지 않는다. 묶음으로 넘긴다.
- 메시지:
  ```
  [확인] 10/27 19:42 · {cp_label} {amount:,}원 {출금|입금}. 뭐였어?
  버튼을 누르거나 이 메시지에 답장해줘 (예: 치킨 4명)
  ```
- 버튼 (`config.categories()`의 label, `ask:false` 제외):
  - 엔빵 의심이면 첫 줄 `[엔빵]`
  - 후보 2개
    - 현재 category가 etc·transfer·income이 아니면 그것 + 기본 후보 1개
    - 기본 후보: transfer면 `living`, `food`, `gift`에서 앞 2개 / card면 `food`, `shopping`
  - 마지막 줄 `[엔빵] [기타]` (엔빵 버튼이 이미 첫 줄에 있으면 `[기타]`만)
  - `callback_data = f"c:{id}:{code}"`, 엔빵은 `f"c:{id}:split"`
- 보낸 뒤 `asked_at=now`, `tg_message_id`를 update하고 `asked_today.count += 1`
- **반복 금지의 기준은 `asked_at`이다.** asked_at이 있는 거래는 다시 묻지 않는다.

`digest(s, state, t)` (F-06 간이판):
- `t.hour >= digest_hour`이고 `state.last_digest_date != 오늘`이며, 미질문 pending이 1건 이상일 때만 실행한다.
- "오늘 미뤄진 N건" 1통을 보내고, 각 거래를 질문 형식으로 보낸다(상한 무시). `last_digest_date=오늘`
- 0건이면 아무것도 보내지 않고, `last_digest_date`도 바꾸지 않는다.

## 6. 답장 적용 (apply_answer)
`apply_answer(txn, ans)`:
1. `ans.skip` → category `etc`
2. `ans.category` 있으면 그것, 없으면 기존 category 유지. 기존이 transfer·etc이고 새 값도 없으면 → "카테고리를 못 알아들었어"와 함께 같은 버튼으로 메시지를 편집하고 종료한다(asked_at 유지, 재질문 아님).
3. `ans.my_share_of_other` → category만 확정한다(F-10: 친구가 대표결제한 몫의 이체).
4. 엔빵 (`split_n` 또는 `my_share`가 있고 `direction=out`):
   - `n = split_n` 또는 (my_share만 있으면 `max(2, round(amount/my_share))`)
   - `my = my_share` 또는 `ceil(amount / n)`
   - splits에 upsert(`txn_id` unique): `total=amount`, `receivable=amount-my`, `remaining=receivable`, `status=open`
   - category가 아직 transfer·etc·null이면 food로 둔다(엔빵은 대개 식비. 사용자가 카테고리를 같이 말하면 그게 우선)
5. transaction update: `category`, `status=confirmed`, `confidence=1.0`
6. `classify.learn(cp_key, category)`
7. 원래 메시지를 편집한다: `✅ {label}` + (엔빵이면 ` · {n}명 엔빵 (내 몫 {my:,}원, 받을 돈 {receivable:,}원)`). 키보드 제거.

## 7. 정산·요약
`match_income(txn)` (F-09):
- 후보: `status=open`이고 14일 이내 생성된 splits 중 `|amount - total/n| <= 10` 또는 `amount <= remaining`
- 후보 1개:
  - settlements insert (`auto`)
  - `remaining -= amount`, 0 이하면 `status=done`
  - 입금 거래는 `category=settlement`, `status=confirmed`
  - "정산 반영 · 남은 받을 돈 {remaining:,}원" 1줄
- 후보 2개 이상: "어느 정산이야?" + 버튼 최대 3개 `s:{split_id}:{txn_id}` (라벨: `{원거래 cp_label} {total:,}원`) + `[일반 입금]` `g:{txn_id}`. 입금 거래는 `status=pending`, `asked_at=now`
- 후보 0개: 아무것도 안 한다(classify가 income으로 처리)

엔빵 사후 추정 (F-09 후반, 시간 남으면):
- 최근 24시간 안의 `direction=out`, `amount >= split_suspect_min`, split 없는 거래 T에 대해, T 이후 들어온 미매칭 입금 중 금액이 서로 ±10% 안인 것이 2건 이상이면 "엔빵이었어? ({k+1}명 추정)" + `[맞아]` `j:{T.id}:{k+1}`를 1회 보낸다.
- 1회 제한은 T의 `asked_at`이 있으면 보내지 않는 것으로 처리한다.

`/today`, `/month`:
- `/month`: `monthly_summary`의 이번 달 행 → 카테고리 라벨별 금액 + 합계 + open splits의 `remaining` 합(받을 돈)
- `/today`: 오늘 `direction=out`이고 self가 아닌 거래의 순지출 합. 엔빵은 my_share로 계산한다.

## 8. 테스트 — tests/fakedb.py, tests/test_watch.py
- `fakedb.py`: `db`의 select/insert/upsert/update/delete/get_settings/load_rules/load_cache/cp_key를 메모리 dict로 흉내 낸다.
  - select는 eq, `("is","null")`, `("gte"/"lte"/"lt"/"gt", v)`, `_order`, `_limit`를 지원한다.
  - `monkeypatch.setattr(watch, "db", fake)` 형태로 주입할 수 있게 watch.py는 `import db`로 쓴다.
- `bot`은 send·edit·answer_callback 호출을 리스트에 기록하는 가짜로 바꾼다.
- `parse`·`classify`는 실제 모듈을 쓰되, 스텁 상태여도 테스트가 의미 있도록 필요한 테스트에서만 monkeypatch한다.
- 시나리오 테스트 (docs/collab-plan.md 10장 데모와 같다):
  1. "스벅 6500" → cafe, auto, 질문 0회 (classify가 cafe 0.8을 반환하도록 모킹 가능)
  2. "46000 교촌치킨" → food, 엔빵 의심 → 질문 1회, 첫 버튼 `c:{id}:split`
  3. 그 메시지에 "4명" 답장 → splits(my_share 11500, receivable 34500), 메시지 편집에 ✅
  4. 같은 실행을 한 번 더 → 질문 0회 (**반복 금지**)
  5. "+11500 상대B" ×3 → 매번 자동 매칭, 마지막에 split done, 입금 category settlement
  6. "50000 상대A 이체" → transfer, 질문 1회 → 콜백 `c:{id}:living` → confirmed, learn 호출
  7. 하루 상한: pending 7건 → 5건만 질문, `asked_today.count == 5`
  8. 다른 chat id에서 온 메시지 → 무시
  9. update 처리 중 예외 → offset은 증가, 다음 update는 처리됨

## 9. 실제 실행 확인 (Secrets 등록 후)
- 로컬: `.env.local`에 **테스트 봇** 토큰으로 `python watch.py`를 실행하고 텔레그램으로 시나리오 1~3을 직접 해본다.
- Actions: PR 머지 후 `gh workflow run watch`를 실행하고 `gh run watch`로 결과를 본다. 폰 확인 후 5분 뒤 반복 여부를 본다.

## 완료 기준
- [ ] `python -m pytest -q` 전체 통과, 시나리오 테스트 9개
- [ ] 뼈대의 "봇이 살아 있습니다" 코드 제거
- [ ] 실제 봇으로 시나리오 2~4 성공 (질문 → 답장 → ✅ → 재질문 없음)
- [ ] PR 생성

## 다음 파트
`integrate`
