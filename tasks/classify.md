# 파트: classify — DB·카카오·분류 (담당 박세훈)

## 목표
`db.py`(Supabase), `kakao.py`(공개 API), `classify.py`(분류 + 학습)를 구현한다. 해커톤 조건 ②(공개 API)가 이 파트에 걸려 있다.

## 소유 파일
`db.py`, `kakao.py`, `classify.py`, `supabase/schema.sql`, `tests/test_classify.py`, `tests/test_db.py`

## 선행 조건 (사람)
- HUMAN_TODO 2번: Supabase 프로젝트 생성, `supabase/schema.sql` 실행
- HUMAN_TODO 3번: 카카오 REST 키 발급
- `.env.local`에 `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `KAKAO_REST_KEY`, `CP_SALT`
- 키가 없어도 구현과 단위 테스트(monkeypatch)는 끝까지 한다. 실연결 확인(6단계)만 보류한다.

## 1. db.py — PostgREST 직접 호출 (requests만)
```python
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
```
- 환경변수는 호출 시점에 `config.env()`로 읽는다(import 시점 X). 그래야 테스트가 env 없이 import된다.
- `select(table, **filters) -> list[dict]`
  - 일반 kwargs `k=v`는 `k=eq.v`
  - 값이 튜플 `(op, v)`면 `k={op}.{v}` (예: `ts=("gte", iso)`, `asked_at=("is", "null")`)
  - 특수 kwargs: `_order="ts.asc"`, `_limit=10`, `_select="id,amount"`
  - 한 컬럼에 조건 두 개(범위)는 `_and="(ts.gte.X,ts.lte.Y)"`를 그대로 `and` 파라미터로 넘긴다.
- `insert(table, row) -> dict`: POST + `Prefer: return=representation` → 첫 행
- `upsert(table, row, on_conflict) -> dict`: POST + `?on_conflict=...` + `Prefer: resolution=merge-duplicates,return=representation`
- `update(table, match, values) -> None`: PATCH, match는 select 규칙과 같다
- `delete(table, match) -> None`: DELETE (대시보드·규칙 삭제용)
- 오류 처리: `r.raise_for_status()` 전에 `r.text[:300]`을 포함한 RuntimeError를 낸다. **키는 메시지에 넣지 않는다.**
- `cp_key(name, method) -> str`
  - 정규화: `norm = re.sub(r"\s+", "", name).lower()`
  - `method == "transfer"`: `"p:" + sha256((norm + CP_SALT).encode()).hexdigest()[:16]`
  - 그 외: `"m:" + norm`
- `get_settings() -> dict`: settings 테이블 → `{key: value}`. 숫자로 보이는 값은 int/float로 변환한다.
- 편의 함수(계약 추가분, watch.py가 쓴다):
  - `load_rules() -> dict` → `{cp_key: category}` (active=true만)
  - `load_cache() -> dict` → `{name: row}`

## 2. kakao.py — 카카오 로컬 키워드 검색
- `GET https://dapi.kakao.com/v2/local/search/keyword.json`
  - params: `query=name`, `size=1`
  - header: `Authorization: KakaoAK {KAKAO_REST_KEY}`
  - timeout 5초
- 반환: `{"code": doc.get("category_group_code") or None, "name": doc.get("category_name", "")}`
- 0건, 네트워크 오류, 4xx/5xx이면 `None`. 예외를 밖으로 던지지 않는다(분류 전체가 멈추면 안 된다). `print`로 경고 한 줄만 남긴다.
- `KAKAO_REST_KEY`가 없으면 호출하지 않고 `None`을 반환한다.

## 3. classify.py
```python
def classify(txn, rules, cache) -> (category, confidence, cache_row | None)
```
카테고리 정의는 `config.categories()`에서 읽는다. 카카오 매핑은 각 카테고리의 `kakao_codes`에서 역인덱스를 만든다.

`name = txn["counterparty"]`, `key = db.cp_key(name, txn["method"])`, `norm = 정규화(name)`

1. `key in rules` → `(rules[key], 0.95, None)`
2. 키워드 사전에서 `self`가 매칭되면 → `("self", 0.9, None)` (내 계좌 이동)
3. `txn["direction"] == "in"` → `("income", 0.5, None)`. 정산 판정은 watch.py가 한다.
4. `txn["method"] == "transfer"` → `("transfer", 0.3, None)`. 처음 보는 이체 상대는 반드시 질문하게 된다.
5. `norm in cache` → `(row["category"], row["confidence"], None)`
6. 키워드 사전 매칭(parse_answer와 같은 규칙: 라벨 또는 키워드 포함, 최장 일치, ask:false 제외) → `(cat, 0.8, cache_row)`
7. `kakao_lookup(name)`:
   - 코드가 매핑에 있음 → `(cat, 0.85, cache_row)`
   - 문서는 있는데 매핑 없음 → `("etc", 0.5, cache_row)`
   - None → 8단계로
8. `("etc", 0.2, None)`

`cache_row = {"name": norm, "kakao_code": ..., "kakao_name": ..., "category": cat, "confidence": c}`
키워드 매칭을 카카오보다 먼저 하는 이유: 배달앱·쇼핑몰은 카카오가 엉뚱한 장소를 돌려주는 경우가 많고, API 호출을 줄일 수 있다.

```python
def learn(cp_key, category) -> None   # F-07
```
- `category in ("etc", "transfer", "income", "settlement")`면 아무것도 안 한다.
- rules에 행이 없으면 insert(hits=1, active=false)
- 같은 category면 hits+1, `active = hits >= 2`
- 다른 category면 category를 교체하고 hits=1, active=false

## 4. 테스트
- `tests/test_classify.py`: `monkeypatch`로 `kakao.kakao_lookup`과 `db.cp_key`(또는 env `CP_SALT`)를 고정한다. 네트워크는 0회여야 한다.
  - 규칙 적중 → 0.95
  - 이체, 규칙 없음 → transfer 0.3
  - 입금 → income
  - "스벅"(키워드) → cafe 0.8, 카카오 호출 0회
  - "교촌치킨 신촌점"(카카오 FD6 모킹) → food 0.85, cache_row 반환
  - 캐시 적중 → 카카오 호출 0회
  - 카카오 None → etc 0.2
  - "내 통장" → self
- `tests/test_db.py`: `requests.request`(또는 사용한 함수)를 monkeypatch해서 URL·파라미터 조립만 검사한다.
  - `select("transactions", status="pending", asked_at=("is","null"), _order="ts.asc")`의 params
  - `cp_key("홍 길동","transfer")`가 `p:`로 시작하고 16자 해시이며, 원문이 포함되지 않음
  - `cp_key("교촌치킨 신촌점","card") == "m:교촌치킨신촌점"`

## 5. 인터페이스 변경 반영
`docs/collab-plan.md` 4장에 `upsert`, `delete`, `get_settings`, `load_rules`, `load_cache`, `learn`이 추가됐다는 것을 한 줄씩 적는다. 이 문서는 공용이므로 PR 설명에도 남긴다.

## 6. 실연결 확인 (키가 있을 때만)
- `scripts/check_kakao.py "교촌치킨 신촌점"` 스크립트를 만들어 실행한다. 코드와 카테고리를 출력한다.
- `scripts/check_db.py`를 만든다. settings를 select해서 출력한 뒤 merchant_cache에 테스트 행을 upsert·select·delete한다.
- 결과를 `plan.md` '데이터' 섹션의 "쓸 값의 경로" 확인용으로 보고한다. 한도(콘솔 쿼터)는 HUMAN_TODO 3번에서 사람이 적는다.

## 완료 기준
- [ ] `python -m pytest -q` 전체 통과, 네트워크 호출 0
- [ ] 키가 있으면 check_kakao·check_db 성공
- [ ] PR 생성

## 다음 파트
없음. bot 파트(권순오)의 통합을 돕고, 대시보드(조원영)가 `db.py`를 읽는 방식을 같이 확인한다.
