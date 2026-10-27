"""알림·직접 입력·답장 파싱. 담당: 조원영. 계약: docs/collab-plan.md 4장. 절차: tasks/parse.md
현재는 스텁이다. "파싱 개발 시작해"로 구현한다."""
from __future__ import annotations


def parse_push(raw: str) -> dict | None:
    """결제 알림 원문 1건 → Txn. 못 읽으면 None."""
    return None  # TODO(tasks/parse.md)


def parse_manual(text: str) -> dict | None:
    """텔레그램 직접 입력 → Txn. 예: "스벅 6500", "+11500 세훈", "50000 홍길동 이체"."""
    return None  # TODO(tasks/parse.md)


def parse_answer(text: str) -> dict:
    """질문에 대한 답장 → Answer."""
    return {"category": None, "split_n": None, "my_share": None,
            "my_share_of_other": False, "skip": False}  # TODO(tasks/parse.md)
