# 파트: dashboard — 배포 URL 1장 (담당 조원영)

## 목표
Vercel에 배포된 비밀번호 보호 페이지 1장을 만든다. 이번 달 순지출, 받을 돈, 미분류 목록, 규칙, 설정을 보여준다. 제출 조건 "배포 URL"을 충족한다.

## 소유 파일
`dashboard/` 전체

## 선행 조건 (사람)
- HUMAN_TODO 2번 (Supabase 키)
- HUMAN_TODO 9번 (Vercel 연결) — 코드가 먼저 있어야 하므로 2~6단계 이후에 한다
- Node.js 20 이상: `node --version`으로 확인하고, 없으면 사용자에게 안내한다

## 1. 생성
- `dashboard/.gitkeep`를 지운다.
- `cd dashboard && npx create-next-app@latest . --ts --app --eslint --no-tailwind --no-src-dir --import-alias "@/*" --use-npm --yes`
  - 묻는 항목이 있으면 기본값으로 진행한다.
- 추가 패키지는 설치하지 않는다(Supabase JS도 쓰지 않는다). PostgREST를 `fetch`로 직접 호출한다.
- `dashboard/.env.local.example`: `SUPABASE_URL=`, `SUPABASE_SERVICE_KEY=`, `DASH_PASSWORD=`

## 2. 서버 전용 데이터 접근 — `dashboard/lib/db.ts`
- 파일 첫 줄에 `import "server-only";`를 쓴다(필요하면 `npm i server-only`). 서비스 키가 브라우저 번들로 새면 안 된다.
- `rest(path, init)`: `${SUPABASE_URL}/rest/v1/${path}`로 요청한다. 헤더는 apikey와 Bearer 서비스 키, `cache: "no-store"`.
- 함수:
  - `monthly(month)` → `monthly_summary?month=eq.{YYYY-MM}`
  - `openSplits()` → `splits?status=eq.open&select=*,transactions(cp_label,ts)`
  - `pending()` → `transactions?status=eq.pending&order=ts.desc&limit=20`
  - `rules()` → `rules?active=eq.true&select=*,counterparties(alias)`
  - `settings()`
  - `updateSetting(key, value)`
  - `deleteRule(id)`
- 카테고리 라벨: 저장소 루트의 `keywords.json`을 빌드 시 import한다(`../keywords.json`). 경로 문제가 생기면 `dashboard/lib/categories.ts`로 복사하지 말고 `next.config`의 `outputFileTracingRoot` 또는 상대 import로 해결한다. 단일 출처 원칙 때문이다.

## 3. 기본 인증 — `dashboard/middleware.ts`
- 모든 경로에서 `Authorization: Basic ...`을 검사한다. 비밀번호가 `DASH_PASSWORD`와 다르면 `401`과 `WWW-Authenticate: Basic realm="dashboard"`를 반환한다.
- 사용자 이름은 무엇이든 허용한다.
- `DASH_PASSWORD`가 설정되지 않았으면 전부 401이다(실수로 열리는 것 방지).

## 4. 페이지 — `dashboard/app/page.tsx` (서버 컴포넌트, `export const dynamic = "force-dynamic"`)
위에서 아래로:
1. **이번 달 순지출** 큰 숫자 + 카테고리별 가로 막대(순수 CSS, 라벨과 금액 표시). 금액 내림차순
2. **받을 돈**: open splits 목록(원거래 이름, 총액, n명, 남은 금액). 합계
3. **미분류** (pending 20건): 날짜, 이름, 금액. "텔레그램에서 답장하면 분류된다" 안내 1줄
4. **학습된 규칙**: 별칭 또는 가맹점, 카테고리, 횟수, [삭제] 버튼 (server action → deleteRule → `revalidatePath("/")`)
5. **설정** 폼: threshold(0~1), daily_ask_cap, digest_hour, split_suspect_min. server action으로 저장한다. 숫자 범위를 검증한다.
6. 푸터: "장소 분류 데이터: Kakao Local API"

디자인: 단색 배경, 시스템 폰트, 모바일 폭 우선(최대 폭 640px), 다크모드는 `prefers-color-scheme`. **원본 서비스의 이름·로고·브랜드 색을 쓰지 않는다.** 제목은 "바로분류".

## 5. 로컬 확인
- `dashboard/.env.local`을 만든다. 값은 사람이 채운다(HUMAN_TODO 5번과 같은 값 + DASH_PASSWORD).
- `npm run build` 성공 → `npm run dev` → 비밀번호 없이 접속하면 401, 넣으면 페이지가 뜬다.
- 데이터가 비어 있어도 깨지지 않아야 한다(빈 상태 문구 표시).

## 6. 커밋·PR
- `dashboard/.env.local`과 `node_modules`가 커밋되지 않았는지 확인한다(루트 .gitignore가 처리).
- 루트 `README.md`의 "대시보드" 항목에 로컬 실행 방법 3줄을 추가한다. README는 팀장 파일이므로 PR 설명에 적는다.

## 7. 배포 안내 (사람: HUMAN_TODO 9번)
사용자에게 그대로 전달한다.
- Vercel → Add New Project → 이 저장소 → **Root Directory: `dashboard`**
- Environment Variables: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `DASH_PASSWORD`
- Deploy → URL을 `plan.md` '설정 화면'과 README에 적는다.

## 완료 기준
- [ ] `npm run build` 성공
- [ ] 비밀번호 없이 401, 있으면 페이지 표시
- [ ] 브라우저 개발자 도구 Sources에서 서비스 키 문자열이 검색되지 않음
- [ ] PR 생성, 배포 URL 확보
