# 파트: parse — 입력·답장·알림 파싱 (담당 조원영)

## 목표
`parse.py`의 세 함수를 구현하고 `tests/test_parse.py`로 검증한다. 외부 호출은 없다(순수 함수).

## 소유 파일
`parse.py`, `keywords.json`(키워드 추가만 가능, 구조 변경 금지), `tests/test_parse.py`, `tests/fixtures/push_samples.json`

## 계약 (docs/collab-plan.md 4장)
```python
Txn = {"ts": "2026-10-27T19:42:00+09:00", "amount": 23000, "direction": "out"|"in",
       "method": "card"|"transfer", "counterparty": "교촌치킨 신촌점"}
Answer = {"category": str|None, "split_n": int|None, "my_share": int|None,
          "my_share_of_other": bool, "skip": bool}
```
카테고리 코드와 키워드는 `config.categories()`(= keywords.json)에서 읽는다. 코드에 하드코딩하지 않는다.

## 1. parse_manual(text) — 텔레그램 직접 입력
규칙:
- 공백으로 토큰을 나눈다. 금액 토큰 정규식: `^\+?[\d,]+원?$`. 쉼표와 "원"을 제거하고 int로 만든다.
- 한국어 단위도 지원한다: `1만2천`, `1.5만`, `3만원`, `6천`. 정규식 `^\+?(\d+(?:\.\d+)?)만(?:(\d+)천)?원?$`, `^\+?(\d+)천원?$`.
- 금액 토큰은 정확히 1개여야 한다. 0개 또는 2개 이상이면 `None`.
- 금액 앞에 `+`가 있으면 `direction="in"`, 아니면 `"out"`.
- `method`:
  - 토큰에 `이체`, `송금`, `보냄`, `계좌`가 있으면 `"transfer"`. 이 키워드 토큰은 상대 이름에서 뺀다.
  - `direction="in"`이면 항상 `"transfer"`.
  - 나머지는 `"card"`.
- `counterparty`: 금액과 키워드를 뺀 나머지 토큰을 공백으로 이은 것. 비어 있으면 `None`.
- `/`로 시작하면(명령) `None`.
- `ts`: `config.now().isoformat(timespec="seconds")`
- 예:
  - `"스벅 6500"` → out, card, 스벅, 6500
  - `"6,500원 스벅"` → 동일
  - `"+11500 세훈"` → in, transfer, 세훈
  - `"50000 홍길동 이체"` → out, transfer, 홍길동
  - `"교촌치킨 신촌점 46000"` → counterparty `"교촌치킨 신촌점"`
  - `"3만 고기집"` → 30000
  - `"안녕"` → None, `"100 200 가게"` → None

## 2. parse_answer(text) — 질문에 대한 답장
위에서부터 모두 적용한다(배타 아님).
- `skip`: `keywords.json`의 `skip_words` 중 하나가 포함되면 `skip=True`, `category="etc"`. 그리고 바로 반환한다.
- `split_n`: `(\d+)\s*(명|빵|인)` 또는 `엔빵\s*(\d+)` 또는 `n빵` 앞의 숫자. 2~20만 인정한다.
- `my_share`:
  - `내\s*몫\s*([\d,]+)` 또는 `내꺼\s*([\d,]+)` → int
  - "내 몫"·"내꺼"가 있는데 숫자가 없으면 `my_share_of_other=True` (친구가 대표결제, 이 이체는 내 몫이라는 뜻)
- `category`:
  - 각 카테고리의 `label` 자체(예: "식비", "교통") 또는 `keywords` 중 텍스트에 포함된 것을 찾는다. 대소문자는 무시한다.
  - 여러 개가 매칭되면 **가장 긴 키워드**의 카테고리를 쓴다.
  - `ask: false`인 카테고리(transfer, settlement)는 제외한다. 단 `self`, `income`은 매칭을 허용한다.
- 예:
  - `"치킨 4명"` → food, 4
  - `"4명"` → category None, 4
  - `"엔빵 3"` → split 3
  - `"내 몫 15,000"` → my_share 15000
  - `"고기 내 몫"` → food, my_share_of_other True
  - `"월세"` → living
  - `"몰라"` → etc, skip
  - `"ㅋㅋ"` → 전부 None/False

## 3. parse_push(raw) — 결제 알림 원문
- `tests/fixtures/push_samples.json`에 샘플이 있으면 그 포맷에 맞춘다. **샘플이 비어 있으면** 아래 일반 규칙으로만 구현하고, 보고에 "실제 샘플 필요(HUMAN_TODO 8)"를 적는다.
- 일반 규칙:
  - 금액: `([\d,]+)\s*원` 중 "잔액" 바로 뒤가 아닌 첫 번째
  - 취소: `취소|환불`이 있으면 `None` (F-02는 v1.1)
  - 방향: `입금|받았|들어왔` → in / `출금|결제|승인|보냈|이체|송금` → out
  - 수단: `이체|송금|입금|보냈|받았` → transfer, 그 외 card
  - 상대: 알려진 패턴 순서대로 추출한다.
    - `(.+?)에서\s*[\d,]+원` (결제)
    - `(.+?)님(에게|께|으로부터|이)` (이체)
    - `[\d,]+원\s*(.+?)\s*(결제|승인)`
    - 못 찾으면 None
  - 줄바꿈과 앱 이름 접두(예: 대괄호로 시작하는 머리말)를 먼저 제거한다.
- 어느 필드든 못 읽으면 전체 `None`. 부분 결과를 반환하지 않는다.

## 4. 테스트 — tests/test_parse.py
- 위 예시를 전부 `pytest.mark.parametrize`로 테스트한다.
- `push_samples.json`의 각 샘플에 대해 `expected`와 비교한다(`ts` 제외). 샘플이 0개면 그 테스트는 `pytest.skip`.
- `parse_manual`의 `ts`가 `+09:00`으로 끝나는지 확인한다.

## 5. keywords.json 보강
- 테스트에서 매칭이 안 되는 자주 쓰는 표현이 나오면 키워드를 추가한다.
- 키워드는 소문자로 저장한다. 비교할 때 입력도 소문자로 바꾼다.

## 완료 기준
- [ ] `python -m pytest -q tests/test_parse.py` 전부 통과 (샘플 없으면 skip 1건 허용)
- [ ] 외부 import는 표준 라이브러리 + `config`만
- [ ] PR 생성

## 다음 파트
`dashboard` (같은 담당자). 박세훈의 `db.py`가 머지된 뒤에 시작하는 게 좋다.
