"""알림·직접 입력·답장 파싱. 담당: 조원영. 계약: docs/collab-plan.md 4장. 절차: tasks/parse.md
직접 입력·답장은 구현됨. 알림 원문 파싱은 아직 스텁이다."""
from __future__ import annotations
import re
from decimal import Decimal

import config


def _amount(token: str) -> int | None:
    if re.fullmatch(r"\+?[\d,]+원?", token):
        digits = token.lstrip("+").removesuffix("원").replace(",", "")
        return int(digits) if digits else None
    match = re.fullmatch(r"\+?(\d+(?:\.\d+)?)만(?:(\d+)천)?원?", token)
    if match:
        return int(Decimal(match[1]) * 10000 + int(match[2] or 0) * 1000)
    match = re.fullmatch(r"\+?(\d+)천원?", token)
    return int(match[1]) * 1000 if match else None


def parse_push(raw: str) -> dict | None:
    """결제 알림 원문 1건 → Txn. 못 읽으면 None."""
    return None  # TODO(tasks/parse.md)


def parse_manual(text: str) -> dict | None:
    """텔레그램 직접 입력 → Txn. 예: "스벅 6500", "+11500 세훈", "50000 홍길동 이체"."""
    if text.strip().startswith("/"):
        return None
    tokens = text.split()
    amounts = [(i, _amount(token)) for i, token in enumerate(tokens) if _amount(token) is not None]
    if len(amounts) != 1 or amounts[0][1] <= 0:
        return None
    index, amount = amounts[0]
    transfer_words = {"이체", "송금", "보냄", "계좌"}
    direction = "in" if tokens[index].startswith("+") else "out"
    method = "transfer" if direction == "in" or transfer_words.intersection(tokens) else "card"
    name = " ".join(token for i, token in enumerate(tokens) if i != index and token not in transfer_words)
    if not name:
        return None
    return {"ts": config.now().isoformat(timespec="seconds"), "amount": amount,
            "direction": direction, "method": method, "counterparty": name}


def parse_answer(text: str) -> dict:
    """질문에 대한 답장 → Answer."""
    answer = {"category": None, "split_n": None, "my_share": None,
              "my_share_of_other": False, "skip": False}
    text = text.lower()
    if any(word.lower() in text for word in config.keywords().get("skip_words", [])):
        return {**answer, "skip": True, "category": "etc"}
    # 숫자와 인원 접미사 또는 엔빵 뒤 숫자를 잡는다.
    match = re.search(r"(\d+)\s*(?:명|빵|인)|엔빵\s*(\d+)", text)
    if match:
        n = int(match[1] or match[2])
        if 2 <= n <= 20:
            answer["split_n"] = n
    match = re.search(r"(?:내\s*몫|내꺼)\s*([\d,]+)", text)
    if match:
        digits = match[1].replace(",", "")
        answer["my_share"] = int(digits) if digits else None
    elif re.search(r"내\s*몫|내꺼", text):
        answer["my_share_of_other"] = True
    best = 0
    for code, category in config.categories().items():
        if category.get("ask", True) is False and code not in {"self", "income"}:
            continue
        for word in [category["label"], *category.get("keywords", [])]:
            if word.lower() in text and len(word) > best:
                best, answer["category"] = len(word), code
    return answer
