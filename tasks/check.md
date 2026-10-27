# 파트: check — 제출 전 검사 (담당 권순오)

## 목표
매뉴얼 5.4 제출 체크리스트와 "선 지키기" ⑤를 자동으로 검사하고, 결과를 `docs/submit-check.md`로 남긴다. 고칠 수 있는 것은 고친다.

## 절차
1. **비밀값 검사** (하나라도 나오면 ❌. 즉시 사용자에게 알리고 HUMAN_TODO 10번 키 재발급 절차를 안내한다)
   - `git ls-files`에 `.env.local`, `*.har`가 있는지
   - 추적 파일 전체를 grep한다.
     - `KakaoAK [A-Za-z0-9]{10,}`
     - `eyJ[A-Za-z0-9_-]{20,}` (Supabase JWT)
     - `[0-9]{8,10}:AA[A-Za-z0-9_-]{20,}` (봇 토큰)
     - `sb_secret_`, `service_role`가 키 값과 함께 쓰인 곳
   - `git log -p --all`에도 같은 패턴을 검사한다(지워도 기록에 남는다).
2. **원본 이름 검사**: `README.md`, `bot.py`, `watch.py`, `dashboard/app/`, `keywords.json`에서 원본 서비스 이름(한글·영문, 대소문자 무시)을 grep한다. 0건이어야 한다. `plan.md`, `docs/`는 예외.
3. **개인정보 검사**
   - `docs/원본캡처/`, `docs/demo/` 이미지를 직접 열어 금액·잔액·실명·계좌번호가 가려졌는지 본다. 의심되면 ❌로 표시하고 파일명을 적는다.
   - `prompts/` 아래 파일에서 1번 패턴과 전화번호·계좌번호 패턴(`\d{3,6}-\d{2,6}-\d{2,6}`)을 검사한다.
4. **해커톤 조건 점검** (`plan.md`와 저장소 상태로 판정)
   - ① `plan.md` '원본 해부'가 채워져 있고 `docs/stack.png` 또는 `docs/screen-flow.md`가 존재
   - ② `plan.md` '데이터'에 API 이름·일일 한도·호출 간격 기입. 한도가 빈칸이면 ❌ + HUMAN_TODO 3번
   - ③ `gh run list --workflow watch --limit 5`로 최근 성공 기록 확인. `git log --oneline --author=watch-bot | head`로 update state 커밋 확인
   - ④ `plan.md` '비틀기' 기입
   - 배포 URL: `plan.md` '설정 화면'과 README에 URL이 있는지
   - README 출처 문구 "장소 분류 데이터: Kakao Local API"
   - `prompts/권순오`, `prompts/조원영`, `prompts/박세훈`에 각각 파일 1개 이상
5. `python -m pytest -q` 통과
6. `plan.md` '선 지키기 확인' 체크박스를 검사 결과에 맞게 체크한다. 확인 못 한 항목은 비워 둔다.
7. `docs/submit-check.md`에 ✅/❌ 표와 남은 조치(누가, 무엇을)를 쓴다.
8. 커밋 → PR.

## 보고
❌ 항목만 먼저, 담당자와 함께. 전부 ✅면 발표 1분 문장(`docs/collab-plan.md` 1장)을 다시 보여준다.
