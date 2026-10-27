# CLAUDE.md — 바로분류 (3차 해커톤 1조)

Claude Code는 이 파일을 매 세션 자동으로 읽는다. 아래 규칙이 모든 작업에 우선한다.

## 이 프로젝트
결제 직후 애매한 거래만 텔레그램으로 묻고, 대충 쓴 답("치킨 4명")으로 분류와 엔빵 차감까지 끝내는 가계부 봇.
GitHub Actions가 5분마다 `watch.py`를 실행한다(서버 없음). 데이터는 Supabase, 대시보드는 Vercel.

기준 문서 (충돌하면 위가 우선):
1. `docs/collab-plan.md` 4장 — 함수 시그니처·데이터 형태 (인터페이스 계약)
2. `docs/product-spec.md` — 기능 명세 (F-01~F-13), 카테고리 표
3. `plan.md` — 해커톤 제출 양식, 알림 규칙
4. `docs/reference/3차_해커톤_참고매뉴얼.pdf` — 해커톤 조건 원문 (필요할 때만 읽는다)

## 명령 해석 — 가장 중요
사용자가 아래처럼 말하면 해당 `tasks/` 파일을 **처음부터 끝까지 읽고, 그 절차를 멈추지 말고 끝까지 수행**한다.
`/start <파트>` 슬래시 명령도 같다.

| 사용자가 하는 말 (예) | 파트 | 읽을 파일 | 담당 |
|---|---|---|---|
| "세팅 시작해", "뼈대 만들어" | setup | `tasks/setup.md` | 권순오 |
| "해부 정리해", "원본 해부 시작" | dissect | `tasks/dissect.md` | 조원영 |
| "파싱 개발 시작해", "parse 시작" | parse | `tasks/parse.md` | 조원영 |
| "분류 개발 시작해", "classify 시작", "DB 시작" | classify | `tasks/classify.md` | 박세훈 |
| "봇 개발 시작해", "watch 시작", "알림 시작" | bot | `tasks/bot.md` | 권순오 |
| "대시보드 개발 시작해" | dashboard | `tasks/dashboard.md` | 조원영 |
| "통합 시작해", "데모 돌려" | integrate | `tasks/integrate.md` | 권순오 |
| "제출 검사해", "체크리스트 돌려" | check | `tasks/check.md` | 권순오 |

파트가 모호하면 위 표를 보여주고 한 번만 묻는다.

## 작업 방식
1. 시작할 때 `git status`로 상태를 확인한다. main이면 `git pull --rebase origin main` 후 `git checkout -b feat/<파트>`로 브랜치를 만든다. 이미 해당 브랜치면 그대로 쓴다.
2. tasks 파일의 "선행 조건"을 확인한다. 사람이 해야 할 일(키 발급, 계정, 캡처 등)이 빠졌으면 **할 수 있는 부분은 먼저 끝내고**, 마지막에 `HUMAN_TODO.md`의 해당 항목 번호와 함께 무엇이 필요한지 알려준다.
3. 구현 → `python -m pytest -q` 통과 → 커밋. 커밋 메시지: `type(scope): 내용` (feat/fix/test/docs/chore).
4. push 전 `git pull --rebase origin main`. 그 다음 `git push -u origin feat/<파트>`.
5. `gh`가 있고 로그인돼 있으면 `gh pr create --fill --base main`으로 PR을 만든다. 없으면 PR을 만들라고 사용자에게 한 줄로 안내한다.
6. **main에 직접 push하지 않는다.** (Actions 봇의 state.json 커밋만 예외)
7. 끝나면 보고한다: 만든 파일, 테스트 결과, 남은 사람 작업(HUMAN_TODO 번호), 다음에 할 파트.

## 코드 규칙
- 파일 소유권: `docs/collab-plan.md` 2장. 현재 파트 소유 파일만 수정한다. 다른 파트 파일에 버그가 있으면 고치지 말고 보고한다. 단 `tasks/setup.md`와 `tasks/integrate.md`는 전체를 다룰 수 있다.
- 파이썬 3.10 이상. 런타임 의존성은 `requests`만 쓴다. 개발 의존성은 `pytest`, `python-dotenv`.
- Supabase는 `db.py`를 통해서만 접근한다. PostgREST를 requests로 직접 호출한다(supabase-py 금지).
- 키와 토큰은 `os.environ`에서만 읽는다. 로컬에서는 `config.py`의 `load_env()`가 `.env.local`을 읽는다. **하드코딩 금지.**
- 시각은 `zoneinfo.ZoneInfo("Asia/Seoul")`, 금액은 `int`(원).
- 이체 상대(사람) 이름은 DB에 원문으로 저장하지 않는다(`db.cp_key`의 해시와 별칭만).
- **원본 서비스 이름과 로고**를 코드, 봇 메시지, README, 대시보드에 쓰지 않는다. `plan.md`와 `docs/`의 해부 기록에만 쓸 수 있다.
- 카테고리 코드와 라벨의 단일 출처는 `keywords.json`이다. 다른 곳에 하드코딩하지 않는다.
- 외부 호출(텔레그램, 카카오, Supabase)은 테스트에서 monkeypatch로 막는다. 테스트가 네트워크를 타면 안 된다.

## 금지
- 앱 파일(APK/IPA) 열람, 비공개 API 호출, 로그인 우회, 쓰기 요청 자동화
- `.env.local`, `*.har`, 실제 거래 데이터, 캡처 원본(가리지 않은 것) 커밋
- 원격 저장소 설정 변경, Secrets 값 출력, 키를 채팅에 출력하는 것
