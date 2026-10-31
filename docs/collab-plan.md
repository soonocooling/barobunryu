# 바로분류 — 개발·협업 계획서

1조 · 권순오 · 조원영 · 박세훈 · 3차 해커톤 (THE해커톤 CAMPUS 5회차)
도구: Cursor, GitHub (Actions·Secrets·Issues·PR), Supabase, Vercel, 텔레그램

> 기준 문서: `plan.md` (매뉴얼 5.3 양식) · `docs/product-spec.md` (기능 명세)
> 이 문서는 **누가, 언제, 어떤 파일을, 어떤 규칙으로** 만드는지 정한다.

---

## 1. 목표와 성공 기준

**1분 발표 문장**: "토스는 애매한 이체를 '이체'로 뭉개고 엔빵을 전액 지출로 잡는다. 우리 봇은 애매한 것만 결제 직후 묻고, '치킨 4명' 한 줄로 분류와 엔빵 차감을 끝낸다."

| 조건 (매뉴얼) | 우리 충족 방법 | 담당 |
|---|---|---|
| ① 뜯는다 | Wappalyzer(toss.im) + Cursor 캡처 분석 → plan.md 원본 해부 | 조원영 |
| ② 공개 API | 카카오 로컬 키워드 검색 (가맹점 → 업종) | 박세훈 |
| ③ 혼자 알린다 | GitHub Actions 5분 cron → 텔레그램, state.json·asked_at으로 반복 금지 | 권순오 |
| ④ 비틀기 | 애매한 것만 즉시 질문 + 자유 답장 파싱 + 엔빵 차감 | 전원 |
| ⑤ 선 | 앱 파일 안 엶, 비공개 주소 안 씀, 캡처 가림, 이름 해시, 키는 Secrets | 전원 (팀장 최종 검사) |
| 배포 URL | Vercel 대시보드 1장 | 조원영 |

---

## 2. 역할 (매뉴얼 5.2 기준)

| 역할 | 사람 | 공부할 장 | 소유 파일 (이 사람만 수정) |
|---|---|---|---|
| **팀장 + 알리는 사람** | 권순오 | 4장 | `watch.py`, `bot.py`, `config.py`, `.github/`, `state.json`, `plan.md`, `README.md`, `CLAUDE.md`, `tasks/`, `HUMAN_TODO.md`, `tests/test_watch.py`, `tests/fakedb.py`, `scripts/demo_check.py` |
| **뜯는 사람** | 조원영 | 1장 + 2장 | `parse.py`, `keywords.json`, `tests/test_parse.py`, `tests/fixtures/`, `docs/원본캡처/`, `docs/push-samples.md`, `docs/screen-flow.md`, `docs/stack.png`, `dashboard/` |
| **받는 사람** | 박세훈 | 3장 | `kakao.py`, `classify.py`, `db.py`, `supabase/schema.sql`, `tests/test_classify.py`, `tests/test_db.py`, `scripts/check_*.py` |

> Claude Code로 개발한다. 각자 Cursor 터미널에서 `claude`를 실행하고 "○○ 개발 시작해"라고 말하면 `CLAUDE.md` → `tasks/<파트>.md` 절차대로 진행된다.

- 역할은 변경할 수 있다. 바꾸면 이 표와 plan.md 역할 줄을 같이 고친다.
- 다른 사람 소유 파일을 고쳐야 하면 직접 수정하지 말고, 소유자에게 PR 코멘트나 메시지로 요청한다. 이 원칙으로 충돌을 없앤다.
- 공용 파일(`plan.md`, `requirements.txt`, `docs/product-spec.md`)은 팀장만 커밋한다.

---

## 3. 저장소 구조

운영진 데모 저장소를 **권순오 계정으로 포크**한 뒤 아래 구조로 맞춘다. 저장소는 **공개**로 둔다(Actions 무료 분 때문). 데이터는 저장소에 넣지 않는다.

```
barobunryu/
├─ plan.md                      팀장
├─ README.md                    팀장 (출처 표시, 원본 이름·로고 없음)
├─ requirements.txt             requests
├─ state.json                   Actions가 매 실행 커밋 (금액·이름 없음)
├─ watch.py                     권순오 — 오케스트레이션
├─ bot.py                       권순오 — 텔레그램 API
├─ parse.py                     조원영 — 알림·입력·답장 파싱
├─ keywords.json                조원영 — 키워드 → 카테고리 사전
├─ classify.py                  박세훈 — 분류 파이프라인
├─ kakao.py                     박세훈 — 카카오 로컬 호출
├─ db.py                        박세훈 — Supabase REST 래퍼
├─ supabase/schema.sql          박세훈
├─ tests/
│  ├─ fixtures/push_samples.json  조원영 (가린 샘플)
│  ├─ test_parse.py               조원영
│  └─ test_classify.py            박세훈
├─ dashboard/                   조원영 — Next.js → Vercel
├─ docs/
│  ├─ product-spec.md  collab-plan.md  push-samples.md
│  ├─ screen-flow.md   stack.png       원본캡처/
├─ prompts/
│  ├─ 권순오/  조원영/  박세훈/    각자 Cursor 대화 내보내기 (비밀값 제거)
├─ .cursor/rules/project.mdc    팀장
├─ .github/
│  ├─ workflows/watch.yml       권순오
│  └─ pull_request_template.md  팀장
├─ .env.example                 키 이름만
└─ .gitignore                   .env.local, *.har, __pycache__, node_modules
```

---

## 4. 인터페이스 계약 — 구현 시작 전에 고정한다

이 시그니처를 먼저 합의해 두면 세 명이 동시에 개발해도 합칠 때 깨지지 않는다. 바꿔야 하면 팀 전원 동의 후 이 문서부터 고친다.

### 공통 데이터 형태
```python
Txn = {
  "ts": "2026-10-27T19:42:00+09:00",   # ISO, Asia/Seoul
  "amount": 23000,                       # int, 양수
  "direction": "out",                    # "out" | "in"
  "method": "card",                      # "card" | "transfer"
  "counterparty": "교촌치킨 신촌점",      # 원문 (DB 저장 전 db 계층에서 해시 처리)
}
Answer = {
  "category": "food" | None,             # 카테고리 코드 (product-spec 표)
  "split_n": 4 | None,
  "my_share": 15000 | None,
  "my_share_of_other": False,            # "내 몫" + 키워드 → 역방향 엔빵
  "skip": False,                         # "몰라", "패스"
}
```

### parse.py (조원영)
```python
def parse_push(raw: str) -> Txn | None
    # 결제 알림 원문 1건 → Txn. 못 읽으면 None. 포맷은 docs/push-samples.md 기준
def parse_manual(text: str) -> Txn | None
    # 텔레그램 직접 입력: "스벅 6500", "6500 스벅", "+11500 세훈", "50000 홍길동 이체"
    # +는 입금, "이체"·"송금"은 method=transfer, ts는 현재 시각
def parse_answer(text: str) -> Answer
    # "치킨 4명", "내 몫 15000", "고기 내 몫", "몰라"
```

### classify.py · kakao.py · db.py (박세훈)
```python
def kakao_lookup(name: str) -> dict | None
    # {"code": "FD6", "name": "음식점 > 치킨"} 또는 None. 실패·0건이면 None
def classify(txn: Txn, rules: dict, cache: dict) -> tuple[str, float, dict | None]
    # (category, confidence, 캐시에 새로 넣을 행 또는 None)
    # 순서: rules → cache → kakao → keywords.json → etc
# db.py: requests로 Supabase PostgREST를 직접 호출한다 (라이브러리 추가 없음)
def select(table, **filters) -> list[dict]     # k=v → eq, k=(op,v), _order, _limit, _select, _and
def insert(table, row: dict) -> dict
def upsert(table, row: dict, on_conflict: str) -> dict
def update(table, match: dict, values: dict) -> None
def delete(table, match: dict) -> None
def cp_key(name: str, method: str) -> str     # 사람: "p:"+sha256(norm+CP_SALT)[:16], 가맹점: "m:"+norm
def get_settings() -> dict
def load_rules() -> dict                       # {cp_key: category} (active만)
def load_cache() -> dict                       # {norm_name: merchant_cache 행}
# classify.py
def learn(cp_key: str, category: str) -> None  # F-07 규칙 학습
```
카테고리 코드·라벨·키워드·카카오 매핑의 단일 출처는 `keywords.json`(`config.categories()`)이다.
시스템 카테고리: `transfer`(용도 불명), `self`(계좌 이동), `income`(수입), `settlement`(정산 받음).

### bot.py (권순오)
```python
def get_updates(offset: int) -> list[dict]
def send(text: str, buttons: list[list[tuple[str, str]]] | None = None) -> int   # message_id
def edit(message_id: int, text: str, buttons=None) -> None   # buttons None이면 키보드 제거
def answer_callback(cb_id: str, text: str | None = None) -> None   # 만료 오류 무시
```

### watch.py 실행 순서 (권순오)
```
state = load_state()
updates = get_updates(state["tg_offset"])
  ├ message(답장 아님)  → parse_manual → 거래 생성
  ├ message(질문에 답장) → parse_answer → 확정 / 엔빵 / 학습
  └ callback_query      → "c:{txn_id}:{code}" → 확정
inbox 'new' 행 → parse_push → 거래 생성 → raw_text 비우고 status=done
새 거래 → classify → c<θ 또는 엔빵 의심이면 pending
pending & asked_at 없음 → 하루 상한 안이면 send + asked_at 기록
입금 거래 → 미정산 splits 매칭
21시 이후 & last_digest_date ≠ 오늘 → 묶음 메시지
state["tg_offset"] = 마지막 update_id + 1 → save_state()
```

### 스텁 우선 원칙
구현 단계 첫 10분 안에 각자 **위 시그니처대로 고정값을 반환하는 스텁**을 main에 머지한다. 예를 들어 `classify`는 `("etc", 0.2, None)`을 반환한다. 이렇게 하면 watch.py가 처음부터 끝까지 돌아가고, 이후 각자 자기 파일의 진짜 구현으로 바꿔 끼운다.

---

## 5. 진행 순서와 사람별 작업 (매뉴얼 5.1의 8단계)

시간은 3인 팀 기준 대략치다. **각 단계의 '끝 기준'을 넘기 전에는 다음 단계로 가지 않는다.**

### ① 개념 잡기 — 20분
| 권순오 | 조원영 | 박세훈 |
|---|---|---|
| 4장 정독, GitHub Actions·텔레그램 봇 | 1·2장 정독, Wappalyzer 설치 | 3장 정독, 카카오디벨로퍼스 가입·앱 생성·REST 키 발급 (활성화 대기 시간 확보) |

**끝 기준**: 셋 다 "앱을 뜯어서, 공개 API로 받아서, 깃허브가 혼자 돌리다, 텔레그램으로 알린다"를 자기 말로 말할 수 있다. 각자 BotFather 테스트 봇에서 sendMessage를 주소창으로 보내봤다.

### ② 운영진 데모 보기 — 10분
전원 같이 본다. 권순오는 그 자리에서 데모 저장소를 포크한다.
**끝 기준**: 최종 결과물이 어떤 모양인지 셋이 같은 그림을 갖고 있다.

### ③ 해부 — 35분
| 권순오 | 조원영 | 박세훈 |
|---|---|---|
| 멘토에게 거래 원천 방식 승인 받기 (product-spec 결정사항 1) · plan.md 원본 해부 취합 · 추정 테이블 검토 | 토스 소비·내역·상세·정산 화면 캡처 (**금액·잔액·이름 가림**) → `docs/원본캡처/` · 결제·이체·입금·취소 푸시 각 3~5건 → `docs/push-samples.md` · Wappalyzer(toss.im) → `docs/stack.png` · Cursor로 캡처 → `docs/screen-flow.md` | 카카오 로컬 문서 확인 · 값-출처 대응표의 '공개 API 대체' 열 작성 · 카테고리 매핑표 검증 (실제 가맹점 10개로 category_group_code 확인) |

**끝 기준**: plan.md '원본 해부'의 추정 항목이 캡처로 확인되거나 수정됐고, 해부 체크리스트 4칸이 채워졌고, 셋이 읽고 OK했다. **이전에는 코드를 만들지 않는다.**

### ④ API 손으로 확인 — 15분
| 권순오 | 조원영 | 박세훈 |
|---|---|---|
| 본 봇 생성(`barobunryu_bot` 등, 원본 이름 금지), TELEGRAM_CHAT_ID 확보 | push-samples를 `tests/fixtures/push_samples.json`(입력 원문 → 기대 Txn)으로 변환 | Hoppscotch나 curl로 카카오 키워드 검색 → JSON 확인 → 경로를 plan.md에 기입 · Supabase 프로젝트 생성, 팀원 초대 |

**끝 기준**: 카카오 응답에서 `category_group_code`를 눈으로 봤고, 경로가 plan.md에 적혀 있다.

### ⑤ 뼈대 세우기 — 15분
| 권순오 | 조원영 | 박세훈 |
|---|---|---|
| 저장소 구조 정리, `watch.yml`(8장) 반영, Secrets 6개 등록, Actions 활성화, `.cursor/rules`, PR 템플릿 → **뼈대 PR 머지** | `dashboard/` Next.js 생성 → Vercel 연결, 기본 인증 미들웨어, 빈 페이지 배포 | `supabase/schema.sql`(7장) 실행, anon/service 키를 팀원 각자 Supabase 대시보드에서 복사하도록 안내 (채팅으로 공유 금지) |

**끝 기준**: `Run workflow` 수동 실행에서 "봇이 살아 있습니다"가 폰에 왔고, Vercel URL이 401(비밀번호 요구)을 띄운다.

### ⑥ 구현 — 60분

| 시간 | 권순오 | 조원영 | 박세훈 |
|---|---|---|---|
| 0–10 | bot.py 완성, watch.py 루프(스텁 연결) | parse.py 스텁 PR | classify/kakao/db 스텁 PR |
| 10–40 | 질문 발송 + 버튼·답장 처리 + asked_at 반복 금지 + state.json | parse_manual, parse_answer, parse_push + 테스트 통과 | db.py 실제 구현, kakao_lookup + 캐시, classify 파이프라인 + 테스트 |
| 40–50 | 엔빵(F-08) 처리, 정산 매칭(F-09) | 대시보드: 월 합계 + 미분류 목록 (view `monthly_summary`) | 규칙 학습(F-07), keywords.json 보강 (조원영과 협의) |
| 50–60 | **통합**: main에서 데모 시나리오(10장) 전체 실행 | 통합 지원, 대시보드 확인 | 통합 지원, DB 값 확인 |

**시간이 모자랄 때 버리는 순서**: 대시보드 꾸미기 → F-07 학습 → F-09 자동 매칭(수동 버튼으로 대체) → F-08. **F-01·F-03·F-05와 반복 금지는 절대 버리지 않는다.**
**끝 기준**: 수동 실행에서 진짜 질문이 폰에 왔고, 버튼과 답장으로 확정됐다.

### ⑦ 반복 검사 — 10분 대기
스케줄 실행을 두 번 기다린다. 확인할 것은 세 가지다: ① 같은 질문이 다시 오지 않는다 ② 저장소에 `update state` 커밋이 생겼다 ③ Actions 탭이 초록이다. 기다리는 동안 README와 발표 준비를 한다.

### ⑧ 마무리 — 20분
| 권순오 | 조원영 | 박세훈 |
|---|---|---|
| 11장 체크리스트 전체 검사 (특히 비밀값·캡처 가림), README 출처 표시, 최종 PR 머지 | 데모 화면 녹화(텔레그램 + 대시보드), 발표 1분 시연 | prompts/ 정리 검사, plan.md 데이터 섹션 한도 기입 |

---

## 6. GitHub 협업 규칙

### 브랜치
- `main`: 항상 동작하는 상태. **보호 규칙은 걸지 않는다.** Actions가 `state.json`을 main에 직접 커밋해야 하기 때문이다. 대신 팀 규칙으로 직접 push를 금지한다(Actions 봇만 예외).
- 작업 브랜치: `feat/<영역>-<이름>`. 예: `feat/parse-wonyoung`, `feat/classify-sehun`, `feat/bot-soono`
- 브랜치는 짧게 유지한다. 30분 이상 머지하지 않고 들고 있지 않는다.

### 커밋
- 형식: `type(scope): 내용` — type은 `feat`, `fix`, `test`, `docs`, `chore`
- 예: `feat(parse): 이체 직접 입력 파싱`, `fix(bot): 콜백 만료 오류 무시`

### 이슈
- 기능 ID마다 이슈 1개(F-01, F-03, F-05, F-08, F-09, F-07, F-12, 해부, 배포). 담당자를 지정하고 라벨은 `mvp` / `v1.1`.
- PR 본문에 `Closes #번호`를 적는다.

### PR
- 템플릿 (`.github/pull_request_template.md`):
  ```
  ## 무엇을
  ## 관련 기능 ID / 이슈
  ## 확인한 방법 (테스트·스크린샷)
  ## 체크
  - [ ] 내 소유 파일만 수정
  - [ ] 키·토큰·실명·금액 캡처 없음
  - [ ] 인터페이스 계약(collab-plan 4장) 그대로
  ```
- 리뷰어 1명, 돌아가며 맡는다: 조원영 → 박세훈 → 권순오 → 조원영. 5분 안에 리뷰한다.
- 머지 방식: Squash merge
- push 전에 항상 `git pull --rebase origin main`을 실행한다. Actions가 5분마다 main에 커밋하므로 rebase는 필수다.

### 비밀값
- 공유 채널(카톡, 디스코드, PR)에 키를 붙여넣지 않는다. 각자 Supabase·카카오 콘솔에서 직접 복사해 `.env.local`에 넣는다.
- 실수로 커밋했다면 즉시 팀장에게 알리고 키를 재발급한다. 봇은 BotFather `/revoke`, 카카오는 키 재발급, Supabase는 키 rotate.

### 소통
- 각 단계 끝에 2분 체크인: 끝 기준 충족 여부와 막힌 것
- 10분 넘게 막히면 바로 팀장에게, 팀장도 막히면 멘토에게

---

## 7. Supabase 스키마 (`supabase/schema.sql`)

```sql
create table counterparties (
  cp_key text primary key,
  alias text,
  type text not null default 'merchant' check (type in ('merchant','person','self')),
  created_at timestamptz not null default now()
);

create table inbox (
  id bigint generated always as identity primary key,
  raw_text text,                                   -- 처리 후 null로 지움
  source text not null default 'auto',
  status text not null default 'new' check (status in ('new','done','failed')),
  created_at timestamptz not null default now()
);

create table transactions (
  id bigint generated always as identity primary key,
  ts timestamptz not null,
  amount integer not null check (amount > 0),
  direction text not null check (direction in ('out','in')),
  method text not null check (method in ('card','transfer')),
  cp_key text references counterparties(cp_key),
  cp_label text,                                   -- 가맹점명 또는 별칭 (사람 실명 금지)
  category text,
  confidence real,
  status text not null default 'auto' check (status in ('auto','pending','confirmed')),
  asked_at timestamptz,
  tg_message_id bigint,
  created_at timestamptz not null default now()
);

create table splits (
  id bigint generated always as identity primary key,
  txn_id bigint not null references transactions(id),
  total integer not null, n integer not null check (n >= 2),
  my_share integer not null, receivable integer not null, remaining integer not null,
  status text not null default 'open' check (status in ('open','done')),
  created_at timestamptz not null default now()
);

create table settlements (
  id bigint generated always as identity primary key,
  split_id bigint not null references splits(id),
  txn_id bigint not null references transactions(id),   -- 정산 입금 거래
  amount integer not null,
  matched_by text not null check (matched_by in ('auto','user')),
  created_at timestamptz not null default now()
);

create table rules (
  id bigint generated always as identity primary key,
  cp_key text unique references counterparties(cp_key),
  category text not null,
  hits integer not null default 1,
  active boolean not null default false,          -- hits >= 2면 true
  created_at timestamptz not null default now()
);

create table merchant_cache (
  name text primary key,
  kakao_code text, kakao_name text,
  category text, confidence real,
  created_at timestamptz not null default now()
);

create table settings (key text primary key, value text not null);
insert into settings values ('threshold','0.7'),('daily_ask_cap','5'),('digest_hour','21'),('split_suspect_min','30000');

-- 월별 순지출: 엔빵이면 내 몫만, 계좌 이동 제외. 정산 입금은 지출 계산에 쓰지 않는다
create view monthly_summary as
select to_char(t.ts at time zone 'Asia/Seoul','YYYY-MM') as month,
       t.category,
       sum(coalesce(s.my_share, t.amount)) as spent
from transactions t
left join splits s on s.txn_id = t.id
where t.direction = 'out' and coalesce(t.category,'') <> 'self'
group by 1, 2;

-- RLS: 전 테이블 활성화. anon은 inbox insert만 허용. 나머지는 service_role(Actions·대시보드 서버)만
alter table counterparties enable row level security;
alter table inbox          enable row level security;
alter table transactions   enable row level security;
alter table splits         enable row level security;
alter table settlements    enable row level security;
alter table rules          enable row level security;
alter table merchant_cache enable row level security;
alter table settings       enable row level security;
create policy inbox_insert_only on inbox for insert to anon with check (true);
```

---

## 8. GitHub Actions (`.github/workflows/watch.yml`)

매뉴얼 4.4 파일에서 다음을 바꾼다: 간격 5분, 동시 실행 방지, Secrets 6개, push 전 rebase.

```yaml
name: watch
on:
  schedule:
    - cron: "*/5 * * * *"        # UTC. 5분 간격은 시간대와 무관
  workflow_dispatch:
permissions:
  contents: write
concurrency:
  group: watch                   # 수동 실행과 스케줄이 겹쳐도 한 번에 하나만
  cancel-in-progress: false
jobs:
  watch:
    runs-on: ubuntu-latest
    timeout-minutes: 4
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python watch.py
        env:
          TZ: Asia/Seoul
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
          KAKAO_REST_KEY: ${{ secrets.KAKAO_REST_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          CP_SALT: ${{ secrets.CP_SALT }}
      - name: 마지막 상태 저장
        run: |
          git config user.name "watch-bot"
          git config user.email "watch-bot@users.noreply.github.com"
          git add state.json
          git diff --cached --quiet && exit 0
          git commit -m "update state"
          git pull --rebase origin main
          git push
```

### 키·환경변수 위치
| 이름 | Actions Secrets | Vercel | 각자 .env.local | 비고 |
|---|---|---|---|---|
| SUPABASE_URL | ○ | ○ | ○ | |
| SUPABASE_SERVICE_KEY | ○ | ○ | ○ | 브라우저에 절대 노출 금지 |
| SUPABASE_ANON_KEY | — | — | — | 폰 자동화(inbox insert)에만 사용 |
| KAKAO_REST_KEY | ○ | — | 박세훈 | 막히면 운영진 공용 키 ⑧ |
| TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID | ○ | — | 권순오 | 로컬 테스트는 각자 테스트 봇으로 |
| CP_SALT | ○ | — | ○ | 임의 긴 문자열, 한 번 정하면 바꾸지 않음 |
| DASH_PASSWORD | — | ○ | 조원영 | |

**`getUpdates` 충돌 주의**: 본 봇 토큰으로 로컬에서 `watch.py`를 돌리면 Actions와 offset이 꼬인다. 로컬 실행은 각자 만든 테스트 봇 토큰으로만 한다.

---

## 9. Cursor 사용 규칙

### `.cursor/rules/project.mdc`
```
---
description: 바로분류 프로젝트 규칙
alwaysApply: true
---
- 기능은 @plan.md 와 @docs/product-spec.md, 함수 시그니처·데이터 형태는 @docs/collab-plan.md 4장을 그대로 따른다.
- 요청한 사람의 소유 파일(collab-plan 2장)만 수정한다. 다른 파일 수정이 필요하면 코드를 고치지 말고 제안만 한다.
- 파이썬 외부 라이브러리는 requests만 쓴다. Supabase는 PostgREST를 requests로 직접 호출한다.
- 키·토큰은 os.environ에서만 읽는다. 하드코딩 금지. 로컬은 python-dotenv로 .env.local을 읽는다(개발 의존성).
- 시각은 Asia/Seoul 기준. 금액은 int(원).
- 사람 이름(이체 상대)은 DB에 원문으로 저장하지 않는다.
- 원본 서비스 이름·로고를 코드, 문구, README에 쓰지 않는다.
```

### 역할별 첫 프롬프트
- **조원영**: `@docs/push-samples.md @docs/collab-plan.md 4장의 parse_push, parse_manual, parse_answer를 parse.py에 구현하고, tests/fixtures/push_samples.json을 쓰는 pytest를 tests/test_parse.py에 만들어줘. 정규식에는 각각 무엇을 잡는지 주석을 달아줘.`
- **박세훈**: `@supabase/schema.sql @docs/product-spec.md 카테고리 표 @docs/collab-plan.md 4장대로 db.py, kakao.py, classify.py를 만들어줘. classify는 rules→cache→kakao→keywords.json→etc 순서고, 카카오 호출은 캐시 미스일 때만 한다.`
- **권순오**: `@docs/collab-plan.md 4장의 watch.py 실행 순서대로 watch.py와 bot.py를 만들어줘. 질문은 asked_at이 없는 pending만, 하루 상한은 settings.daily_ask_cap, callback_data는 "c:{txn_id}:{code}". 매뉴얼 4.5처럼 load→fetch→판단→send→save 구조를 유지해.`
- **대시보드(조원영)**: `@supabase/schema.sql dashboard에 Next.js 페이지 1장을 만들어줘. 서버 컴포넌트에서 service key로 monthly_summary와 status=pending 거래를 읽고, middleware.ts에서 DASH_PASSWORD 기본 인증을 걸어줘. 하단에 "장소 분류 데이터: Kakao Local API".`

### 대화 기록
- 단계가 끝날 때마다 Cursor 채팅을 내보내 `prompts/내이름/단계번호.md`로 저장한다. **올리기 전에 키, 토큰, 실명, 금액을 검색해 지운다.**

---

## 10. 데모 시나리오 (통합 테스트 겸 발표)

이름은 더미(별칭)를 쓴다. 각 단계 사이에 `Run workflow`를 누른다.

| # | 입력 (텔레그램) | 기대 결과 | 보여줄 포인트 |
|---|---|---|---|
| 1 | `스벅 6500` | 질문 없이 카페·간식으로 분류 | 확실한 건 조용히 처리 |
| 2 | `46000 교촌치킨` | 카카오 FD6 → 식비. 3만원 이상이라 `[엔빵?]` 질문 | 공개 API 분류 + 엔빵 의심 |
| 3 | 2번 질문에 답장 `4명` | ✅ 식비 · 4명 엔빵 (내 몫 11,500원) | 대충 쓴 답 파싱 |
| 4 | `50000 상대A 이체` | `[확인] 상대 #1 50,000원 출금. 뭐였어?` | 원본이 못 하는 이체 용도 |
| 5 | 4번에서 버튼 `주거·통신` | ✅ 확정, 메시지 수정 | 1탭 |
| 6 | `+11500 상대B` × 3 | 정산 자동 매칭, 받을 돈 0 | 정산이 수입으로 안 잡힘 |
| 7 | (5분 대기) | 같은 질문 재발송 없음, `update state` 커밋 | 반복 금지 (조건 ③) |
| 8 | 대시보드 | 이번 달 식비가 11,500원(46,000원 아님) | 원본과 비교 화면 |

---

## 11. 제출 체크리스트 (매뉴얼 5.4 + 우리 추가)

- [ ] plan.md '원본 해부' 완성, `docs/stack.png` · `docs/screen-flow.md` 첨부 (①)
- [ ] plan.md에 카카오 로컬 API 이름, 한도, 호출 정책 기입 (②)
- [ ] Actions 스케줄 켜짐, 초록 체크 기록 (③)
- [ ] 텔레그램 질문 도착 캡처 (③)
- [ ] 5~10분 뒤 같은 질문이 반복되지 않음, `update state` 커밋 존재 (③)
- [ ] 발표에서 "원본은 안 해주고 우리는 해준다" 1분 시연 (④)
- [ ] Vercel 배포 URL (비밀번호 보호)
- [ ] 저장소 전체에서 `KakaoAK`, `eyJ`(Supabase 키 접두), 봇 토큰 패턴(`:AA`) 검색 결과 0건 (⑤)
- [ ] 캡처에 금액·잔액·타인 이름 없음. DB에 실명 없음. inbox raw_text 처리 후 비워짐 (⑤)
- [ ] README에 출처 표시, 원본 이름·로고 없음 (⑤)
- [ ] 브랜치·PR 규칙대로 머지, `prompts/각자이름/` 업로드 (협업)

---

## 12. 리스크와 대응

| 리스크 | 신호 | 대응 |
|---|---|---|
| 멘토가 '본인 알림 텍스트' 방식을 불허 | 해부 단계 확인 결과 | 더미 거래 CSV를 inbox에 넣는 스크립트로 데모. 비틀기 자체는 그대로 유지 |
| 카카오 키 활성화 지연 | 401 / 인증 오류 | 운영진 공용 키 ⑧. 그동안 keywords.json으로 분류 |
| 푸시 문구가 너무 다양해 파싱이 늦어짐 | 30분 시점에 parse_push 테스트 50% 미만 | parse_manual(직접 입력)만으로 데모. parse_push는 v1.1 |
| cron 지연으로 데모가 끊김 | 실행이 5분 넘게 밀림 | 발표는 `Run workflow` 수동 실행으로 |
| Actions push 실패 | `rejected` 로그 | rebase 단계 확인, Workflow permissions를 Read and write로 |
| 통합 때 시그니처 불일치 | KeyError, TypeError | 4장 계약이 기준. 계약과 다르게 구현한 쪽이 고친다 |
| 시간 부족 | 구현 40분 시점에 F-05 미완 | 6장 컷 순서대로 버린다. 해부·API·뼈대는 건너뛰지 않는다 |
