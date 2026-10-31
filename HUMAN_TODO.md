# 사람이 해야 하는 일 (Claude Code가 못 하는 것)

계정, 키, 캡처, 승인은 사람만 할 수 있다. 번호는 tasks/ 문서에서 참조한다.
**키는 채팅(카톡·디스코드·PR)에 붙여넣지 않는다.** 각자 콘솔에서 직접 복사한다.

## 지금 바로 (시작 10분 안)

| # | 담당 | 할 일 | 끝 기준 |
|---|---|---|---|
| 11 | 권순오 | 멘토에게 확인받기: "거래 데이터는 본인 결제 알림을 본인이 텔레그램에 입력하고, 공개 API는 카카오 로컬로 가맹점 분류에 씁니다. 괜찮나요?" | OK, 또는 불허(불허면 더미 데이터 데모로 전환) |
| 1 | 권순오 | 텔레그램 BotFather → `/newbot` → 이름 `바로분류`, 아이디 `barobunryu_xxx_bot`(원본 이름 금지) → 토큰 확보 → 봇에게 "안녕" → 환경변수를 사용하는 비공개 도구로 대화 ID 확인. 토큰 URL·응답 로그 공유 금지 | 토큰과 TELEGRAM_CHAT_ID 확보 |
| 12 | 전원 | 각자 **테스트 봇**도 하나 만든다(같은 방법). 로컬 실행은 테스트 봇으로만 한다 | 각자 토큰과 TELEGRAM_CHAT_ID |
| 2 | 박세훈 | supabase.com → New project(리전 Seoul) → SQL Editor에 `supabase/schema.sql` 전체 붙여넣기 → Run → Project Settings → Team에서 팀원 둘 초대 | 테이블 8개, view 1개 생성 |
| 3 | 박세훈 | developers.kakao.com → 내 애플리케이션 → 추가 → 앱 키의 **REST API 키** 복사. 콘솔에서 로컬 API 일일 쿼터를 확인해 `plan.md` '데이터 → 일일 한도'에 적는다. 막히면 운영진 공용 키 ⑧ | 키 확보, 한도 기입 |
| 4 | 권순오 | GitHub 로그인. 터미널에서 `gh auth login`(gh 없으면 cli.github.com에서 설치). 저장소가 생기면 Settings → Collaborators에서 조원영·박세훈 초대 | `gh auth status` 성공 |

## 저장소가 생긴 뒤

| # | 담당 | 할 일 |
|---|---|---|
| 5 | 전원 | 저장소 clone → 일반 로컬 실행에서만 필요하면 `.env.example`을 `.env.local`로 복사 → 값 채우기. Actions/Codespaces Secrets를 쓰면 로컬 파일은 필요 없다. SUPABASE_URL과 SERVICE_KEY는 Supabase → Project Settings → API에서 각자 복사한다. CP_SALT는 권순오가 정해서 **직접 말로** 전달한다. TELEGRAM_BOT_TOKEN과 TELEGRAM_CHAT_ID는 각자 테스트 봇 값. [설정 절차](docs/telegram-secrets.md) |
| 6 | 권순오 | GitHub 저장소 Settings → Secrets and variables → Actions → New repository secret 6개: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `KAKAO_REST_KEY`, `TELEGRAM_BOT_TOKEN`(**본 봇**), `TELEGRAM_CHAT_ID`(본인), `CP_SALT` |
| 7 | 권순오 | 저장소 Actions 탭 → 워크플로 활성화. Settings → Actions → General → Workflow permissions → **Read and write** → Save |
| 8 | 조원영 | 원본 앱 캡처 4~6장(소비 요약, 내역, 상세·카테고리 변경, 정산). **금액·잔액·이름·계좌번호를 가린 뒤** `docs/원본캡처/`에 넣는다. 결제·이체·입금·취소 알림 각 2~5건은 금액과 이름을 가짜로 바꿔 텍스트나 캡처로 넣는다. 크롬 Wappalyzer로 toss.im을 찍어 `docs/stack.png`에 넣는다 |
| 9 | 조원영 | vercel.com → Add New Project → 이 저장소 → Root Directory `dashboard` → 환경변수 `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `DASH_PASSWORD` → Deploy → URL을 팀장에게 전달 |
| 13 | 전원 | 단계가 끝날 때마다 Claude Code 대화를 내보내 `prompts/내이름/`에 저장한다. 키·실명·금액은 지운다 |

## 사고 났을 때

| # | 상황 | 조치 |
|---|---|---|
| 10 | 키·토큰이 커밋되거나 채팅에 노출됨 | 즉시 재발급한다. 봇: BotFather `/revoke`. 카카오: 앱 키 재발급. Supabase: API Keys rotate. 그다음 Secrets와 각자 `.env.local`을 갱신한다. 지운 커밋도 기록에 남으므로 재발급이 유일한 해결책이다 |
