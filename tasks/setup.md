# 파트: setup — 뼈대 세우기 (담당 권순오, 매뉴얼 5단계)

## 목표
저장소가 GitHub에 올라가고, Actions 수동 실행 한 번에 폰으로 "봇이 살아 있습니다"가 온다.

## 선행 조건 (사람)
- HUMAN_TODO 1번(BotFather 본 봇·TELEGRAM_CHAT_ID), 2번(Supabase 프로젝트), 4번(GitHub 로그인)
- 없어도 1~4단계는 진행한다.

## 절차
1. 환경 확인: `python --version`(3.10 이상), `git --version`, `gh --version`(없으면 건너뛴다). 결과를 보고에 넣는다.
2. `python -m pip install -r requirements-dev.txt` → `python -m pytest -q`가 통과하는지 확인한다.
3. `.env.local`이 없으면 `.env.example`을 복사해 만든다. 값은 채우지 않는다. 사용자에게 HUMAN_TODO 5번을 안내한다.
4. git 초기화:
   - `.git`이 없으면 `git init -b main` → `git add -A` → `git commit -m "chore: 프로젝트 뼈대"`.
   - 커밋 전에 `git status`로 `.env.local`과 `*.har`가 포함되지 않았는지 확인한다.
5. 원격 저장소:
   - `git remote -v`에 origin이 있으면 `git push -u origin main`.
   - 없고 `gh auth status`가 성공하면 `gh repo create barobunryu --public --source . --push`를 실행한다. 사용자 승인을 받는다.
   - 둘 다 안 되면 HUMAN_TODO 4번을 안내하고 멈춘다.
   - 이 단계만 예외로 main에 직접 push한다(첫 커밋).
6. `.env.local`에 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`가 있으면 `python watch.py`로 로컬 확인을 한다. 폰에 메시지가 와야 한다. 이때는 테스트 봇 토큰이어도 된다.
7. 사용자에게 다음을 안내한다(사람만 가능):
   - HUMAN_TODO 6번(Secrets 6개 등록)
   - HUMAN_TODO 7번(Actions 켜기, Workflow permissions를 Read and write로)
   - 등록이 끝나면 `gh workflow run watch` 또는 Actions 탭의 Run workflow를 실행한다. `gh`가 있으면 사용자가 "됐어"라고 할 때 대신 실행하고 `gh run watch`로 결과를 확인한다.
8. GitHub 이슈를 만든다(`gh`가 있을 때만). 라벨 `mvp`를 붙인다.
   - 이슈 목록: dissect / parse / classify / bot / dashboard / integrate / check
   - 각 이슈 본문은 `tasks/<파트>.md 참고` 한 줄과 담당자 이름이다.

## 완료 기준
- [ ] GitHub에 저장소가 있고 main에 뼈대가 올라감
- [ ] `python -m pytest -q` 통과
- [ ] Actions 수동 실행이 초록이고, 폰에 "봇이 살아 있습니다"가 옴. 저장소에 `update state` 커밋이 생김
- [ ] 팀원 둘이 `git clone` 후 바로 자기 파트를 시작할 수 있음 (README의 "처음 받는 사람" 절차가 맞는지 확인)

## 보고
저장소 URL, 테스트 결과, 남은 HUMAN_TODO 번호, "팀원에게 clone 링크 공유" 안내.
