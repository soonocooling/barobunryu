"""알림·직접 입력·답장 파싱. 담당: 조원영. 계약: docs/collab-plan.md 4장. 절차: tasks/parse.md
순수 함수만 둔다(외부 호출 없음). 알림 포맷 기준은 docs/push-samples.md."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from decimal import Decimal

import config


# ---------------------------------------------------------------- 직접 입력·답장

def _amount(token: str) -> int | None:
    if re.fullmatch(r"\+?[\d,]+원?", token):
        digits = token.lstrip("+").removesuffix("원").replace(",", "")
        return int(digits) if digits else None
    match = re.fullmatch(r"\+?(\d+(?:\.\d+)?)만(?:(\d+)천)?원?", token)
    if match:
        return int(Decimal(match[1]) * 10000 + int(match[2] or 0) * 1000)
    match = re.fullmatch(r"\+?(\d+)천원?", token)
    return int(match[1]) * 1000 if match else None


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
    # 숫자와 인원 접미사 또는 더치페이·엔빵 뒤 숫자를 잡는다.
    match = re.search(r"(\d+)\s*(?:명|빵|인)|(?:더치페이|더치|엔빵)\s*(\d+)", text)
    if match:
        n = int(match[1] or match[2])
        if 2 <= n <= 20:
            answer["split_n"] = n
    # "내 몫 4명"의 4를 내 몫 금액으로 읽지 않는다.
    match = re.search(r"(?:내\s*몫|내꺼)\s*([\d,]*\d)(?!\s*(?:명|빵|인))", text)
    if match:
        answer["my_share"] = int(match[1].replace(",", ""))
    elif re.search(r"내\s*몫|내꺼", text):
        answer["my_share_of_other"] = True
    # "엔빵 3", "3빵"의 '빵'이 카페·간식 키워드(빵)로 잡히지 않게 인원 표현은 빼고 찾는다.
    rest = re.sub(r"(?:더치페이|더치|엔빵)\s*\d*|n빵|\d+\s*(?:명|빵|인)", " ", text)
    best = 0
    for code, category in config.categories().items():
        if category.get("ask", True) is False and code not in {"self", "income"}:
            continue
        for word in [category["label"], *category.get("keywords", [])]:
            if word.lower() in rest and len(word) > best:
                best, answer["category"] = len(word), code
    return answer


# ---------------------------------------------------------------- 알림 원문

def _to_int(digits: str) -> int:
    return int(digits.replace(",", ""))


def _clean(name: str | None) -> str | None:
    if not name:
        return None
    name = re.sub(r"\s+", " ", name).strip()
    return name or None


def _txn(ts: str, amount: int, direction: str, method: str, counterparty: str | None) -> dict | None:
    counterparty = _clean(counterparty)
    if amount <= 0 or not counterparty:
        return None
    return {"ts": ts, "amount": amount, "direction": direction,
            "method": method, "counterparty": counterparty}


def _now_iso() -> str:
    return config.now().isoformat(timespec="seconds")


_AMT = r"([\d,]*\d)\s*원"
_DT_FULL = re.compile(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?(?:\([가-힣]\))?\s*(\d{1,2}):(\d{2})")
_DT_MD = re.compile(r"(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})")
_PERSON = re.compile(r"^[가-힣]{2,4}$")
_MASKED_PERSON = re.compile(r"^[가-힣]\*+[가-힣]?$")
_WALLETS = ("카카오페이", "토스", "네이버페이", "페이코")


def _ts_full(m: re.Match | None) -> str:
    if not m:
        return _now_iso()
    y, mo, d, h, mi = (int(x) for x in m.groups())
    try:
        return datetime(y, mo, d, h, mi, tzinfo=config.KST).isoformat(timespec="seconds")
    except ValueError:
        return _now_iso()


def _ts_md(m: re.Match | None) -> str:
    """연도 없는 `MM/DD H:mm`. 연도는 올해, 미래 날짜면 작년."""
    if not m:
        return _now_iso()
    mo, d, h, mi = (int(x) for x in m.groups())
    now = config.now()
    try:
        dt = datetime(now.year, mo, d, h, mi, tzinfo=config.KST)
        if dt > now + timedelta(days=1):
            dt = dt.replace(year=now.year - 1)
    except ValueError:
        return _now_iso()
    return dt.isoformat(timespec="seconds")


def _merchant_words() -> set[str]:
    words: set[str] = set()
    for code, cat in config.categories().items():
        if code in ("transfer", "self", "income", "settlement"):
            continue
        words.update(w.lower() for w in cat.get("keywords", []) if len(w) >= 2)
    return words


def _guess_method(name: str, direction: str) -> str:
    """알림만으로는 가맹점/사람을 구분할 수 없다. 사람 이름처럼 보이면 transfer(추정)."""
    if direction == "in":
        return "transfer"
    if any(name.startswith(w) for w in _WALLETS):
        return "transfer"
    if _MASKED_PERSON.match(name):
        return "transfer"
    if _PERSON.match(name):
        low = name.lower()
        if not any(w in low for w in _merchant_words()):
            return "transfer"
    return "card"


def _flat(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.replace("\r", "\n")).strip()


def _kakaopay(raw: str) -> dict | None:
    """카카오페이 알림톡 (송금·충전 후 결제). 정산·취소는 None."""
    if "정산금액" in raw or re.search(r"정산이", raw):
        return None
    m = re.search(r"송금금액\s*" + _AMT, raw)
    if m:
        amount = _to_int(m.group(1))
        acct = re.search(r"입금계좌\s*:\s*([^\n]+)", raw)
        name = None
        if acct:
            paren = re.search(r"\(([^)]+)\)", acct.group(1))
            name = paren.group(1) if paren else acct.group(1)
        return _txn(_ts_full(_DT_FULL.search(raw)), amount, "out", "transfer", name)
    m = re.search(r"결제금액\s*" + _AMT, raw)
    if m:
        amount = _to_int(m.group(1))
        shop = re.search(r"구매처\s*:\s*([^\n]+)", raw)
        date = re.search(r"결제일시\s*:\s*([^\n]+)", raw)
        return _txn(_ts_full(_DT_FULL.search(date.group(1)) if date else None),
                    amount, "out", "card", shop.group(1) if shop else None)
    return None


def _arrow_style(raw: str) -> dict | None:
    """카카오뱅크류: 제목 `출금 7,000원`, 본문 `A → B`. 시각은 본문에 없다(수신 시각)."""
    title = re.search(r"(입금|출금)\s*" + _AMT, raw)
    arrow = re.search(r"^(.+?)\s*→\s*(.+?)\s*$", raw, re.M)
    if not (title and arrow):
        return None
    direction = "in" if title.group(1) == "입금" else "out"
    left, right = arrow.group(1), arrow.group(2)
    name = left if direction == "in" else right
    return _txn(_now_iso(), _to_int(title.group(2)), direction,
                _guess_method(_clean(name) or "", direction), name)


_HANA = re.compile(
    r"(입금|출금)\s*" + _AMT + r"\s+(.+?)\s+잔액\s*[\d,]*\d\s*원(?:\s+" + _DT_MD.pattern + r")?")


def _bank_one_line(flat: str) -> dict | None:
    """하나은행류: `출금 6500 원 상대 잔액 80000원 11/03 0:35 ***-...`"""
    m = _HANA.search(flat)
    if not m:
        return None
    direction = "in" if m.group(1) == "입금" else "out"
    name = _clean(m.group(3))
    md = re.search(_DT_MD, flat[m.end(3):])
    return _txn(_ts_md(md), _to_int(m.group(2)), direction,
                _guess_method(name or "", direction), name)


def _general(flat: str) -> dict | None:
    """알려진 포맷이 아닐 때의 일반 규칙."""
    text = re.sub(r"^\[[^\]]*\]\s*", "", flat)
    amount = None
    for m in re.finditer(_AMT, text):
        if re.search(r"잔액\s*$", text[:m.start()]):
            continue
        amount = _to_int(m.group(1))
        break
    if not amount:
        return None
    if re.search(r"입금|받았|들어왔|으로부터", text) or re.search(r"님이.*보냈", text):
        direction = "in"
    elif re.search(r"출금|결제|승인|보냈|이체|송금", text):
        direction = "out"
    else:
        return None
    method = "transfer" if re.search(r"이체|송금|입금|보냈|받았", text) else "card"
    name = None
    for pat in (r"(\S+)에서\s*[\d,]*\d\s*원",
                r"(\S+?)님(?:에게|께|으로부터|이)",
                r"[\d,]*\d\s*원\s*(.+?)\s*(?:결제|승인)"):
        m = re.search(pat, text)
        if m:
            name = m.group(1)
            break
    return _txn(_now_iso(), amount, direction, method, name)


def parse_push(raw: str) -> dict | None:
    """결제 알림 원문 1건 → Txn. 못 읽으면 None. 포맷은 docs/push-samples.md 기준."""
    if not raw or not raw.strip():
        return None
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    if re.search(r"취소|환불", raw):
        return None  # F-02는 v1.1
    if re.search(r"송금금액|결제금액|정산금액", raw):
        return _kakaopay(raw)
    flat = _flat(raw)
    return _bank_one_line(flat) or _arrow_style(raw) or _general(flat)
