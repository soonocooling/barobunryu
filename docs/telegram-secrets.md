# 텔레그램 실행과 Secrets 설정

## 확인한 실행 환경

`.github/workflows/watch.yml`은 GitHub Actions의 Ubuntu 러너에서 `watch.py`를
5분 간격의 schedule 또는 workflow_dispatch로 실행하도록 설정되어 있다.
실제 원격 실행 이력과 Secrets 등록 여부는 이 로컬 점검에서 확인하지 않았다.
현재 코드는 수동 실행과 로컬 실행 때만 생존 확인 메시지를 보내며,
예약 실행은 상태만 갱신한다. 수신 처리 등은 아직 초기 구현이다.
노트북과 devcontainer 설정은 없으며 Codespaces 운영 근거도 없다.
`.env.local`은 없어도 된다. 환경변수가 우선이며 로컬 파일은 선택 사항이다.

## GitHub Actions: 웹사이트에서 할 일

1. GitHub에서 이 저장소를 열고 **Settings → Secrets and variables → Actions**로 이동한다.
2. **Secrets → New repository secret**을 선택한다.
3. Name에 `TELEGRAM_BOT_TOKEN`을 입력하고 Secret 입력란에 운영 봇 토큰을 직접 입력한 뒤 **Add secret**을 누른다.
4. 같은 방법으로 `TELEGRAM_CHAT_ID`를 추가한다. 값은 해당 웹 입력란에서만 입력한다.
5. 기존 이름으로 등록해 두었더라도 새 이름의 Secrets가 필요하다. 다른 workflow에서 사용하지 않는지 확인한 뒤 이전 항목을 정리한다.
6. 변경된 workflow가 GitHub에 반영된 뒤 **Actions → watch → Run workflow**에서 실행한다.
   메시지 수신과 작업 성공 여부를 확인한다. 값 확인용 출력 명령은 사용하지 않는다.

저장소 Secrets는 한 번 등록하면 이 저장소의 workflow가 함께 사용하므로 협업자마다
동일한 운영 Secrets를 만들 필요가 없다. 메뉴 접근 또는 생성 권한이 없으면 저장소 관리자에게
위 두 이름의 등록을 요청한다. 이 작업에서 GitHub Secrets를 직접 등록하지 않았다.
workflow가 참조하는 `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `KAKAO_REST_KEY`, `CP_SALT`는
기존 기능용 별도 설정이다. 텔레그램 이름 변경으로 대체되지 않는다.

## Codespaces에서 개발할 경우

Actions Secrets와 Codespaces Secrets는 별개다. 개인 테스트 봇을 사용할 때는 각 협업자가
**프로필 사진 → Settings → Codespaces → Codespaces secrets → New secret**에서
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`를 등록하고 **Repository access**에 이 저장소를 선택한다.

저장소 관리자도 **저장소 Settings → Secrets and variables → Codespaces → New repository secret**에서
공용 개발용 Secrets를 등록할 수 있다. 공용 Secrets를 이용하는 팀원은 같은 값을 개인 설정에
반복 등록할 필요가 없다. 다만 이 프로젝트는 운영 봇과 개발 봇을 분리하고, 각자 테스트 봇을
사용하는 방식을 권장한다. 개인 Secrets는 각자가 관리한다.

추가·변경 후 실행 중인 Codespace를 중지했다가 다시 시작한다. 터미널에서 다음을 실행한다.
Secrets는 환경변수로 전달되므로 `.env.local`을 만들 필요가 없다.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python watch.py
```

마지막 명령은 테스트 봇 메시지를 실제 전송하고 `state.json`을 갱신한다.
운영 봇으로 여러 개발 환경을 동시에 실행하지 않는다.

## 일반 로컬 개발

환경변수가 이미 있으면 그대로 사용한다. 파일로 설정하려는 경우에만 `.env.example`을
`.env.local`로 복사하고 편집기에서 개인 테스트용 값을 입력한다. 이 파일은 커밋하지 않는다.
예시 파일에는 빈 값만 유지한다. 토큰을 URL에 채워 브라우저나 터미널에 입력하거나,
환경변수 목록·요청 URL·응답 본문을 로그에 출력하지 않는다.

## 점검 범위와 노출 대응

현재 작업 트리의 코드에서 실제 토큰/채팅 ID 하드코딩은 발견하지 않았다.
참고 PDF에서 토큰 형식 문자열이 발견됐다. 유효성은 검증하지 않았다.
실제 토큰이었다면 소유자가 BotFather에서 폐기·재발급하고 Secrets를 갱신해야 한다.
참고 PDF와 과거 커밋의 노출 자료 정리도 필요하며, 파일을 삭제하는 것만으로 토큰이 무효화되지는 않는다.
과거 Git 이력 전체와 원격 로그는 이 점검 범위에 포함되지 않았다.

## GitHub 공식 안내

- [Actions Secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
- [개인 Codespaces Secrets](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces)
- [저장소·조직 Codespaces Secrets](https://docs.github.com/en/codespaces/managing-codespaces-for-your-organization/managing-development-environment-secrets-for-your-repository-or-organization)
