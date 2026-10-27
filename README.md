# 바로분류

결제 직후 애매한 거래만 텔레그램으로 물어보고, "치킨 4명"처럼 대충 쓴 답으로 분류와 엔빵 차감까지 끝내는 가계부 봇.

- 5분마다 GitHub Actions가 `watch.py`를 실행한다(서버 없음).
- 가맹점 분류는 카카오 로컬 API, 저장은 Supabase, 대시보드는 Vercel에서 돈다.
- 확실한 거래는 조용히 분류하고, 애매한 이체나 큰 식비는 버튼 1탭 또는 한 줄 답장으로 확정한다.
- 엔빵이면 내 몫만 지출로 잡고, 친구의 정산 입금은 수입이 아니라 받을 돈 상환으로 처리한다.

## 사용법 (텔레그램)
| 입력 | 뜻 |
|---|---|
| `스벅 6500` | 6,500원 결제 |
| `50000 상대A 이체` | 50,000원 송금 |
| `+11500 상대B` | 11,500원 입금 |
| 질문에 답장 `치킨 4명` | 식비, 4명 엔빵 |
| `/today`, `/month` | 오늘·이번 달 순지출 |

## 처음 받는 사람
```bash
git clone <저장소 URL> && cd barobunryu
python -m pip install -r requirements-dev.txt
cp .env.example .env.local      # 값 채우기: HUMAN_TODO.md 5번
python -m pytest -q
```
그다음 Cursor 터미널에서 `claude`를 실행하고 자기 파트를 시킨다. 예: `파싱 개발 시작해` 또는 `/start parse`
파트 목록과 담당자는 `CLAUDE.md`에 있다.

## 문서
- `CLAUDE.md` — Claude Code 작업 규칙과 파트 명령표
- `tasks/` — 파트별 개발 절차
- `HUMAN_TODO.md` — 사람이 해야 하는 일(키, 계정, 캡처)
- `plan.md` — 해커톤 제출 양식
- `docs/product-spec.md` — 기능 명세
- `docs/collab-plan.md` — 협업 계획, 인터페이스 계약

## 대시보드
(dashboard 파트 완료 후 배포 URL과 로컬 실행 방법을 추가한다)

---
장소 분류 데이터: Kakao Local API
