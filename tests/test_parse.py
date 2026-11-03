import json
from datetime import datetime
from pathlib import Path

import pytest

import config
import parse

SAMPLES = json.loads(
    (Path(__file__).parent / "fixtures" / "push_samples.json").read_text(encoding="utf-8")
)["samples"]


# ---------------------------------------------------------------- parse_manual
@pytest.mark.parametrize("text,amount,direction,method,counterparty", [
    ("스벅 6500", 6500, "out", "card", "스벅"),
    ("6500 스벅", 6500, "out", "card", "스벅"),
    ("6,500원 스벅", 6500, "out", "card", "스벅"),
    ("+11500 세훈", 11500, "in", "transfer", "세훈"),
    ("50000 홍길동 이체", 50000, "out", "transfer", "홍길동"),
    ("홍길동 송금 50000", 50000, "out", "transfer", "홍길동"),
    ("교촌치킨 신촌점 46000", 46000, "out", "card", "교촌치킨 신촌점"),
    ("3만 고기집", 30000, "out", "card", "고기집"),
    ("1만2천 고기집", 12000, "out", "card", "고기집"),
    ("1.5만 커피", 15000, "out", "card", "커피"),
    ("3만원 택시", 30000, "out", "card", "택시"),
    ("6천 간식", 6000, "out", "card", "간식"),
    ("10000", 10000, "out", "card", None),
])
def test_parse_manual_ok(text, amount, direction, method, counterparty):
    t = parse.parse_manual(text)
    assert t is not None
    assert (t["amount"], t["direction"], t["method"], t["counterparty"]) == (
        amount, direction, method, counterparty)
    assert t["ts"].endswith("+09:00")


@pytest.mark.parametrize("text", ["안녕", "100 200 가게", "", "   ", "/start", "/help 1000", "0 가게"])
def test_parse_manual_none(text):
    assert parse.parse_manual(text) is None


# ---------------------------------------------------------------- parse_answer
def _ans(**kw):
    base = {"category": None, "split_n": None, "my_share": None,
            "my_share_of_other": False, "skip": False}
    base.update(kw)
    return base


@pytest.mark.parametrize("text,expected", [
    ("치킨 4명", _ans(category="food", split_n=4)),
    ("4명", _ans(split_n=4)),
    ("엔빵 3", _ans(split_n=3)),
    ("3빵", _ans(split_n=3)),
    ("내 몫 15,000", _ans(my_share=15000)),
    ("내꺼 8000", _ans(my_share=8000)),
    ("고기 내 몫", _ans(category="food", my_share_of_other=True)),
    ("월세", _ans(category="living")),
    ("몰라", _ans(category="etc", skip=True)),
    ("ㅋㅋ", _ans()),
    ("1명", _ans()),          # 2~20만 인정
    ("30명", _ans()),
    ("내 몫 4명", _ans(my_share_of_other=True, split_n=4)),
    ("용돈", _ans(category="income")),
    ("스타벅스", _ans(category="cafe")),
    ("", _ans()),
])
def test_parse_answer(text, expected):
    assert parse.parse_answer(text) == expected


def test_parse_answer_skips_transfer_category():
    # transfer·settlement는 ask:false라 라벨로 매칭되지 않는다
    assert parse.parse_answer("송금(용도 불명)")["category"] is None


# ---------------------------------------------------------------- parse_push
@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s["raw"].replace("\n", " ")[:30])
def test_parse_push_samples(sample):
    if not SAMPLES:
        pytest.skip("샘플 없음 (HUMAN_TODO 8)")
    got = parse.parse_push(sample["raw"])
    if sample["expected"] is None:
        assert got is None
    else:
        assert got is not None
        got.pop("ts")
        assert got == sample["expected"]


def test_parse_push_ts_hana(monkeypatch):
    monkeypatch.setattr(config, "now", lambda: datetime(2026, 11, 3, 12, 0, tzinfo=config.KST))
    t = parse.parse_push("하나은행\n출금 6500 원 테스트마트 잔액 80000원 11/03 0:35 ***-******-*****")
    assert t["ts"] == "2026-11-03T00:35:00+09:00"
    # 연말 알림이 연초에 처리되면 작년 날짜가 된다
    monkeypatch.setattr(config, "now", lambda: datetime(2027, 1, 1, 0, 5, tzinfo=config.KST))
    t = parse.parse_push("하나은행\n출금 6500 원 테스트마트 잔액 80000원 12/31 23:50 ***")
    assert t["ts"] == "2026-12-31T23:50:00+09:00"


def test_parse_push_ts_kakaopay():
    raw = next(s["raw"] for s in SAMPLES if "송금금액" in s["raw"])
    assert parse.parse_push(raw)["ts"] == "2026-11-01T18:32:00+09:00"


def test_parse_push_balance_not_amount():
    t = parse.parse_push("하나은행\n출금 6500 원 테스트마트 잔액 80000원 11/03 0:35")
    assert t["amount"] == 6500


def test_parse_push_without_title():
    t = parse.parse_push("출금 6500 원 테스트마트 잔액 80000원 11/03 0:35 ***-******-*****")
    assert (t["amount"], t["counterparty"]) == (6500, "테스트마트")


@pytest.mark.parametrize("raw,expected", [
    ("[테스트카드] 테스트카페에서 6,500원 결제", (6500, "out", "card", "테스트카페")),
    ("홍길동님에게 30,000원 보냈어요", (30000, "out", "transfer", "홍길동")),
    ("홍길동님이 50,000원을 보냈어요", (50000, "in", "transfer", "홍길동")),
])
def test_parse_push_general(raw, expected):
    t = parse.parse_push(raw)
    assert t is not None
    assert (t["amount"], t["direction"], t["method"], t["counterparty"]) == expected


@pytest.mark.parametrize("raw", [
    "", "안녕하세요", "하나은행\n결제가 취소되었어요 6,500원", "환불 3,000원 입금", "출금 원",
])
def test_parse_push_none(raw):
    assert parse.parse_push(raw) is None
