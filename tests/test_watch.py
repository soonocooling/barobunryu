"""watch.py 시나리오 테스트. 네트워크 없이 fakedb와 가짜 bot·parse·classify로 돌린다."""
import json
from datetime import datetime
from unittest.mock import Mock

import pytest

import bot
import classify as real_classify
import parse as real_parse
import watch
from config import KST
from fakedb import FakeDB

CHAT_ID = "1000"
NOON = datetime(2026, 10, 27, 12, 0, tzinfo=KST)
EMPTY_ANSWER = {"category": None, "split_n": None, "my_share": None,
                "my_share_of_other": False, "skip": False}
MERCHANT_CATEGORIES = {"스벅": ("cafe", 0.8), "교촌치킨": ("food", 0.85), "모르는가게": ("etc", 0.2)}


class FakeBot:
    def __init__(self):
        self.updates, self.sent, self.edits, self.answered = [], [], [], []

    def get_updates(self, offset):
        pending, self.updates = self.updates, []
        return pending

    def send(self, text, buttons=None):
        self.sent.append({"id": 500 + len(self.sent), "text": text, "buttons": buttons})
        return self.sent[-1]["id"]

    def edit(self, message_id, text, buttons=None):
        self.edits.append({"id": message_id, "text": text, "buttons": buttons})

    def answer_callback(self, cb_id, text=None):
        self.answered.append(cb_id)


class FakeParse:
    """"+금액 이름", "금액 이름 이체", "이름 금액"만 읽는다. 진짜 parse.py가 머지돼도 이 테스트는 그대로 돈다."""

    @staticmethod
    def parse_manual(text):
        tokens = text.split()
        amounts = [tok for tok in tokens if tok.lstrip("+").isdigit()]
        if len(amounts) != 1:
            return None
        names = [tok for tok in tokens if tok != amounts[0] and tok != "이체"]
        incoming = amounts[0].startswith("+")
        return {"ts": NOON.isoformat(timespec="seconds"), "amount": int(amounts[0].lstrip("+")),
                "direction": "in" if incoming else "out",
                "method": "transfer" if incoming or "이체" in tokens else "card",
                "counterparty": " ".join(names)}

    @staticmethod
    def parse_answer(text):
        return {"4명": {**EMPTY_ANSWER, "split_n": 4},
                "몰라": {**EMPTY_ANSWER, "category": "etc", "skip": True},
                "내 몫 16000": {**EMPTY_ANSWER, "my_share": 16000}}.get(text, EMPTY_ANSWER)

    @staticmethod
    def parse_push(raw):
        return None if raw.startswith("못읽음") else FakeParse.parse_manual(raw)


class FakeClassify:
    def __init__(self, fake_db):
        self.db = fake_db
        self.learned = []

    def classify(self, txn, rules, cache):
        key = self.db.cp_key(txn["counterparty"], txn["method"])
        if key in rules:
            return rules[key], 0.95, None
        if txn["direction"] == "in":
            return "income", 0.5, None
        if txn["method"] == "transfer":
            return "transfer", 0.3, None
        category, confidence = MERCHANT_CATEGORIES.get(txn["counterparty"], ("etc", 0.2))
        return category, confidence, {"name": txn["counterparty"], "category": category, "confidence": confidence}

    def learn(self, cp_key, category):
        self.learned.append((cp_key, category))


class World:
    def __init__(self, monkeypatch, tmp_path, t=NOON, settings=None, rules=None):
        self.t = t
        self.db = FakeDB(lambda: self.t, settings, rules)
        self.bot = FakeBot()
        self.classify = FakeClassify(self.db)
        self.state_file = tmp_path / "state.json"
        self._update_id = 100
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-placeholder")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", CHAT_ID)
        monkeypatch.delenv("TEST_TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TEST_TELEGRAM_CHAT_ID", raising=False)
        monkeypatch.setattr(watch, "STATE_FILE", self.state_file)
        monkeypatch.setattr(watch, "load_env", lambda: None)
        monkeypatch.setattr(watch, "now", lambda: self.t)
        monkeypatch.setattr(watch, "db", self.db)
        monkeypatch.setattr(watch, "bot", self.bot)
        monkeypatch.setattr(watch, "parse", FakeParse)
        monkeypatch.setattr(watch, "classify", self.classify)

    def _next_update(self, **body):
        self._update_id += 1
        self.bot.updates.append({"update_id": self._update_id, **body})

    def say(self, text, reply_to=None, chat_id=CHAT_ID):
        msg = {"message_id": self._update_id, "chat": {"id": int(chat_id)}, "text": text,
               "date": int(self.t.timestamp())}
        if reply_to:
            msg["reply_to_message"] = {"message_id": reply_to}
        self._next_update(message=msg)

    def tap(self, data, message_id=500, chat_id=CHAT_ID):
        self._next_update(callback_query={
            "id": f"cb{self._update_id}", "data": data,
            "message": {"message_id": message_id, "chat": {"id": int(chat_id)}},
        })

    def run(self):
        watch.main()

    def state(self):
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def txns(self):
        return self.db.rows("transactions")

    def split_row(self):
        return self.db.rows("splits")[0]


@pytest.fixture
def world(monkeypatch, tmp_path):
    return World(monkeypatch, tmp_path)


def chicken_question(world):
    world.say("46000 교촌치킨")
    world.run()
    return world.bot.sent[-1]


def test_scenario1_certain_txn_stays_silent(world):
    world.say("스벅 6500")
    world.run()
    txn = world.txns()[0]
    assert (txn["category"], txn["status"]) == ("cafe", "auto")
    assert world.bot.sent == []


def test_scenario2_split_suspect_asks_once(world):
    question = chicken_question(world)
    txn = world.txns()[0]
    assert (txn["category"], txn["status"]) == ("food", "pending")
    assert txn["asked_at"] and txn["tg_message_id"] == question["id"]
    assert len(world.bot.sent) == 1
    assert question["text"].startswith("[확인] 10/27 12:00 · 교촌치킨 46,000원 출금. 뭐였어?")
    assert question["buttons"][0] == [("엔빵", f"c:{txn['id']}:split")]


def test_scenario3_reply_creates_split(world):
    question = chicken_question(world)
    world.say("4명", reply_to=question["id"])
    world.run()
    split = world.split_row()
    assert (split["my_share"], split["receivable"], split["remaining"]) == (11500, 34500, 34500)
    assert world.txns()[0]["status"] == "confirmed"
    edit = world.bot.edits[-1]
    assert edit["id"] == question["id"] and edit["buttons"] is None
    assert edit["text"] == "✅ 식비 · 4명 엔빵 (내 몫 11,500원, 받을 돈 34,500원)"


def test_scenario4_never_asks_twice(world):
    chicken_question(world)
    world.run()
    world.run()
    assert len(world.bot.sent) == 1


def test_scenario5_income_settles_split(world):
    question = chicken_question(world)
    world.say("4명", reply_to=question["id"])
    world.run()
    for _ in range(3):
        world.say("+11500 상대B")
    world.run()
    split = world.split_row()
    assert (split["remaining"], split["status"]) == (0, "done")
    incomes = [t for t in world.txns() if t["direction"] == "in"]
    assert [t["category"] for t in incomes] == ["settlement"] * 3
    assert [t["status"] for t in incomes] == ["confirmed"] * 3
    assert [m["text"] for m in world.bot.sent[-3:]] == [
        "정산 반영 · 남은 받을 돈 23,000원",
        "정산 반영 · 남은 받을 돈 11,500원",
        "정산 반영 · 남은 받을 돈 0원",
    ]


def test_scenario6_transfer_button_confirms_and_learns(world):
    world.say("50000 상대A 이체")
    world.run()
    txn = world.txns()[0]
    assert (txn["category"], txn["status"], txn["cp_label"]) == ("transfer", "pending", "상대 #1")
    assert len(world.bot.sent) == 1
    world.tap(f"c:{txn['id']}:living", message_id=txn["tg_message_id"])
    world.run()
    assert (txn["category"], txn["status"]) == ("living", "confirmed")
    assert world.classify.learned == [(txn["cp_key"], "living")]
    assert world.bot.edits[-1]["text"] == "✅ 주거·통신"
    assert len(world.bot.answered) == 1


def test_scenario7_daily_cap(world):
    for i in range(7):
        world.say(f"{1000 + i} 모르는가게")
    world.run()
    assert len(world.bot.sent) == 5
    assert world.state()["asked_today"]["count"] == 5
    assert sum(1 for t in world.txns() if t["asked_at"] is None) == 2


def test_scenario8_other_chat_ignored(world):
    world.say("스벅 6500", chat_id="999")
    world.tap("c:1:food", chat_id="999")
    world.run()
    assert world.txns() == [] and world.bot.sent == [] and world.bot.answered == []
    assert world.state()["tg_offset"] == world._update_id + 1


def test_scenario9_failed_update_does_not_block_others(world, monkeypatch, capsys):
    original = FakeParse.parse_manual

    def explode_once(text):
        if text == "터짐":
            raise RuntimeError("홍길동 50000")
        return original(text)

    monkeypatch.setattr(FakeParse, "parse_manual", staticmethod(explode_once))
    world.say("터짐")
    world.say("스벅 6500")
    world.run()
    assert len(world.txns()) == 1
    assert world.state()["tg_offset"] == world._update_id + 1
    assert "홍길동" not in capsys.readouterr().out  # 공개 로그에 값이 남지 않는다


def test_later_stage_failure_still_saves_offset(world, monkeypatch):
    monkeypatch.setattr(world.db, "load_rules", Mock(side_effect=RuntimeError("db down")))
    world.say("스벅 6500")
    with pytest.raises(RuntimeError):
        world.run()
    assert world.state()["tg_offset"] == world._update_id + 1


def test_real_name_is_never_stored(world):
    world.say("50000 홍길동 이체")
    world.run()
    assert "홍길동" not in json.dumps(world.db.tables, ensure_ascii=False)
    assert "홍길동" not in world.bot.sent[0]["text"]


def test_person_rule_applies_by_stored_key(monkeypatch, tmp_path):
    key = FakeDB(lambda: NOON).cp_key("상대A", "transfer")
    world = World(monkeypatch, tmp_path, rules={key: "living"})
    world.say("50000 상대A 이체")
    world.run()
    assert world.txns()[0]["category"] == "living"
    assert world.bot.sent == []


def test_counterparty_alias_is_stable(world):
    world.say("50000 상대A 이체")
    world.say("30000 상대C 이체")
    world.say("20000 상대A 이체")
    world.run()
    assert [t["cp_label"] for t in world.txns()] == ["상대 #1", "상대 #2", "상대 #1"]


def test_manual_ts_comes_from_message_date(world):
    world.say("스벅 6500")
    world.t = datetime(2026, 10, 27, 15, 0, tzinfo=KST)  # 실행이 3시간 밀렸다
    world.run()
    assert world.txns()[0]["ts"] == NOON.isoformat(timespec="seconds")


def test_inbox_success_clears_raw_and_dedupes(world):
    world.db.insert("inbox", {"raw_text": "스벅 6500", "status": "new"})
    world.db.insert("inbox", {"raw_text": "스벅 6500", "status": "new"})
    world.run()
    assert len(world.txns()) == 1
    assert world.txns()[0]["source"] == "auto"
    assert [(r["raw_text"], r["status"]) for r in world.db.rows("inbox")] == [(None, "done")] * 2


def test_inbox_failure_clears_raw_and_notifies_once(world):
    raw = "못읽음 " + "가" * 40
    world.db.insert("inbox", {"raw_text": raw, "status": "new"})
    world.run()
    world.run()
    assert [m["text"] for m in world.bot.sent] == [f"못 읽었어: {raw[:30]}"]
    row = world.db.rows("inbox")[0]
    assert (row["raw_text"], row["status"]) == (None, "failed")


def test_inbox_send_failure_still_clears_raw_and_hides_it_from_logs(world, monkeypatch, capsys):
    monkeypatch.setattr(world.bot, "send", Mock(side_effect=RuntimeError("전송 실패")))
    world.db.insert("inbox", {"raw_text": "못읽음 홍길동", "status": "new"})
    world.run()
    world.run()
    world.bot.send.assert_called_once()
    row = world.db.rows("inbox")[0]
    assert (row["raw_text"], row["status"]) == (None, "failed")
    assert "홍길동" not in capsys.readouterr().out


def test_inbox_empty_raw_is_marked_failed(world):
    world.db.insert("inbox", {"raw_text": None, "status": "new"})
    world.run()
    assert world.db.rows("inbox")[0]["status"] == "failed"
    assert [m["text"] for m in world.bot.sent] == ["못 읽었어: "]


def test_split_button_then_reply(world):
    question = chicken_question(world)
    txn = world.txns()[0]
    world.tap(f"c:{txn['id']}:split", message_id=question["id"])
    world.run()
    assert world.bot.edits[-1]["text"].startswith("몇 명이서?")
    assert txn["status"] == "pending"
    world.say("4명", reply_to=question["id"])
    world.run()
    assert world.split_row()["receivable"] == 34500


def test_my_share_answer_derives_n(world):
    question = chicken_question(world)
    world.say("내 몫 16000", reply_to=question["id"])
    world.run()
    split = world.split_row()
    assert (split["n"], split["my_share"], split["receivable"]) == (3, 16000, 30000)


def test_split_answer_on_unknown_category_defaults_to_food(world):
    world.say("50000 모르는가게")
    world.run()
    world.say("4명", reply_to=world.txns()[0]["tg_message_id"])
    world.run()
    assert world.txns()[0]["category"] == "food"
    assert world.split_row()["my_share"] == 12500


def test_unclear_answer_keeps_buttons_and_does_not_confirm(world):
    world.say("50000 상대A 이체")
    world.run()
    txn = world.txns()[0]
    world.say("ㅋㅋ", reply_to=txn["tg_message_id"])
    world.run()
    assert txn["status"] == "pending"
    assert world.bot.edits[-1]["text"].startswith("카테고리를 못 알아들었어")
    assert world.bot.edits[-1]["buttons"]
    assert len(world.bot.sent) == 1


def test_skip_answer_confirms_etc(world):
    question = chicken_question(world)
    world.say("몰라", reply_to=question["id"])
    world.run()
    assert (world.txns()[0]["category"], world.txns()[0]["status"]) == ("etc", "confirmed")


def test_reply_to_unknown_message(world):
    world.say("4명", reply_to=12345)
    world.run()
    assert world.bot.sent[-1]["text"] == "어느 거래인지 모르겠어"


def test_unknown_income_offers_income_button(world):
    world.say("+70000 상대D")
    world.run()
    txn = world.txns()[0]
    assert (txn["category"], txn["status"]) == ("income", "pending")
    data = f"c:{txn['id']}:income"
    assert world.bot.sent[0]["buttons"][-1][0][1] == data
    world.tap(data, message_id=txn["tg_message_id"])
    world.run()
    assert (txn["category"], txn["status"]) == ("income", "confirmed")


def two_open_splits(world):
    for text in ("46000 교촌치킨", "40000 교촌치킨"):
        world.say(text)
    world.run()
    for txn in world.txns():
        world.say("4명", reply_to=txn["tg_message_id"])
    world.run()


def test_multiple_split_candidates_ask_then_user_picks(world):
    two_open_splits(world)
    world.say("+5000 상대B")
    world.run()
    income = world.txns()[-1]
    assert income["status"] == "pending" and income["asked_at"]
    question = world.bot.sent[-1]
    assert question["text"] == "어느 정산이야?"
    first_split = world.db.rows("splits")[0]
    data = f"s:{first_split['id']}:{income['id']}"
    assert question["buttons"][0] == [("교촌치킨 46,000원", data)]
    assert question["buttons"][-1] == [("일반 입금", f"g:{income['id']}")]

    world.tap(data, message_id=question["id"])
    world.tap(data, message_id=question["id"])  # 두 번 눌러도 한 번만 반영된다
    world.run()
    assert (income["category"], income["status"]) == ("settlement", "confirmed")
    assert first_split["remaining"] == 34500 - 5000
    assert [(r["matched_by"], r["amount"]) for r in world.db.rows("settlements")] == [("user", 5000)]


def test_general_income_button_keeps_split_open(world):
    two_open_splits(world)
    world.say("+5000 상대B")
    world.run()
    income = world.txns()[-1]
    world.tap(f"g:{income['id']}", message_id=income["tg_message_id"])
    world.run()
    assert (income["category"], income["status"]) == ("income", "confirmed")
    assert world.db.rows("settlements") == []
    assert world.bot.edits[-1]["text"] == "✅ 수입"


def real_modules_world(monkeypatch, tmp_path):
    """실제 parse·classify와 메모리 DB. 카카오 호출만 막는다."""
    world = World(monkeypatch, tmp_path)
    monkeypatch.setattr(watch, "parse", real_parse)
    monkeypatch.setattr(watch, "classify", real_classify)
    monkeypatch.setattr(real_classify, "db", world.db)
    monkeypatch.setattr(real_classify.kakao, "kakao_lookup",
                        lambda name: {"code": "FD6", "name": "음식점 > 치킨"})
    return world


def test_demo_scenario_with_real_modules(monkeypatch, tmp_path):
    world = real_modules_world(monkeypatch, tmp_path)
    # 1. 확실한 건 조용히 처리
    world.say("스벅 6500")
    world.run()
    assert (world.txns()[0]["category"], world.txns()[0]["status"]) == ("cafe", "auto")
    assert world.bot.sent == []
    # 2~3. 엔빵 의심 질문 → 답장
    world.say("46000 교촌치킨")
    world.run()
    chicken = world.txns()[1]
    assert (chicken["category"], chicken["status"]) == ("food", "pending")
    assert world.bot.sent[-1]["buttons"][0] == [("엔빵", f"c:{chicken['id']}:split")]
    world.say("4명", reply_to=chicken["tg_message_id"])
    world.run()
    assert world.bot.edits[-1]["text"] == "✅ 식비 · 4명 엔빵 (내 몫 11,500원, 받을 돈 34,500원)"
    # 4~5. 이체 질문 → 버튼 → 규칙 학습
    world.say("50000 상대A 이체")
    world.run()
    transfer = world.txns()[2]
    assert (transfer["category"], transfer["cp_label"]) == ("transfer", "상대 #1")
    world.tap(f"c:{transfer['id']}:living", message_id=transfer["tg_message_id"])
    world.run()
    assert (transfer["category"], transfer["status"]) == ("living", "confirmed")
    assert world.db.rows("rules")[0]["hits"] == 1
    # 6. 입금 3회로 정산 완료
    for _ in range(3):
        world.say("+11500 상대B")
    world.run()
    assert world.bot.sent[-1]["text"] == "정산 반영 · 남은 받을 돈 0원"
    assert world.split_row()["status"] == "done"
    assert [t["category"] for t in world.txns()[3:]] == ["settlement"] * 3
    # 7. 다시 돌려도 재질문 없음
    sent = len(world.bot.sent)
    world.run()
    assert len(world.bot.sent) == sent


def test_self_transfer_income_is_not_a_settlement(monkeypatch, tmp_path):
    world = real_modules_world(monkeypatch, tmp_path)
    world.say("46000 교촌치킨")
    world.run()
    world.say("4명", reply_to=world.txns()[0]["tg_message_id"])
    world.run()
    world.say("+11500 내 통장")
    world.run()
    assert world.txns()[1]["category"] == "self"
    assert world.db.rows("settlements") == []
    assert world.split_row()["remaining"] == 34500


def test_no_split_candidate_leaves_income_to_classify(world):
    world.db.insert("splits", {"txn_id": 1, "total": 46000, "n": 4, "my_share": 11500,
                               "receivable": 34500, "remaining": 34500,
                               "created_at": "2026-10-01T12:00:00+09:00"})  # 14일 넘음
    world.say("+11500 상대B")
    world.run()
    assert world.txns()[0]["category"] == "income"
    assert world.db.rows("settlements") == []


def test_quiet_hours_hold_questions(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path, t=datetime(2026, 10, 27, 23, 30, tzinfo=KST),
                  settings={"digest_hour": 24})
    world.say("50000 모르는가게")
    world.run()
    assert world.bot.sent == []
    world.t = datetime(2026, 10, 28, 7, 59, tzinfo=KST)
    world.run()
    assert world.bot.sent == []
    world.t = datetime(2026, 10, 28, 8, 0, tzinfo=KST)
    world.run()
    assert len(world.bot.sent) == 1


def test_asked_today_resets_on_new_day(world):
    world.state_file.write_text(json.dumps({
        "tg_offset": 0, "last_digest_date": None, "last_run": None,
        "asked_today": {"date": "2026-10-26", "count": 5},
    }), encoding="utf-8")
    world.say("50000 모르는가게")
    world.run()
    assert world.state()["asked_today"] == {"date": "2026-10-27", "count": 1}


def test_digest_sends_overflow_once(world):
    for i in range(7):
        world.say(f"{1000 + i} 모르는가게")
    world.run()
    world.t = datetime(2026, 10, 27, 21, 5, tzinfo=KST)
    world.run()
    world.run()
    assert [m["text"] for m in world.bot.sent].count("오늘 미뤄진 2건") == 1
    assert len(world.bot.sent) == 5 + 1 + 2
    assert world.state()["last_digest_date"] == "2026-10-27"


def test_digest_without_pending_sends_nothing(monkeypatch, tmp_path):
    world = World(monkeypatch, tmp_path, t=datetime(2026, 10, 27, 21, 5, tzinfo=KST))
    world.run()
    assert world.bot.sent == []
    assert world.state()["last_digest_date"] is None


def test_today_summary_counts_my_share_and_skips_self(world):
    question = chicken_question(world)
    world.say("4명", reply_to=question["id"])
    world.say("스벅 6500")
    world.run()
    world.db.insert("transactions", {"ts": NOON.isoformat(), "amount": 100000, "direction": "out",
                                     "method": "transfer", "cp_key": "p:self", "cp_label": "내 통장",
                                     "category": "self"})
    world.say("/today")
    world.run()
    assert world.bot.sent[-1]["text"] == "오늘 순지출 18,000원"


def test_month_summary(world):
    world.db.rows("monthly_summary").extend([
        {"month": "2026-10", "category": "food", "spent": 11500, "n": 1},
        {"month": "2026-09", "category": "food", "spent": 99999, "n": 1},
    ])
    world.db.insert("splits", {"txn_id": 1, "total": 46000, "n": 4, "my_share": 11500,
                               "receivable": 34500, "remaining": 23000})
    world.say("/month")
    world.run()
    assert world.bot.sent[-1]["text"] == "10월 지출\n식비 11,500원\n합계 11,500원\n받을 돈 23,000원"


@pytest.mark.parametrize("text", ["/start", "/help", "안녕"])
def test_usage(world, text):
    world.say(text)
    world.run()
    assert world.bot.sent[-1]["text"] == watch.USAGE
    assert len(watch.USAGE.splitlines()) == 3


# ---------- bot.py ----------

@pytest.fixture
def telegram_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-placeholder")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", CHAT_ID)


def response(ok=True, status=200, text="", result=None):
    r = Mock(ok=ok, status_code=status, text=text)
    r.json.return_value = {"ok": True, "result": result}
    return r


def test_get_updates_params(telegram_env, monkeypatch):
    get = Mock(return_value=response(result=[{"update_id": 1}]))
    monkeypatch.setattr(bot.requests, "get", get)
    assert bot.get_updates(7) == [{"update_id": 1}]
    params = get.call_args.kwargs["params"]
    assert (params["offset"], params["timeout"]) == (7, 0)
    assert json.loads(params["allowed_updates"]) == ["message", "callback_query"]
    assert get.call_args.kwargs["timeout"] == 10


def test_edit_without_buttons_removes_keyboard(telegram_env, monkeypatch):
    post = Mock(return_value=response(result=True))
    monkeypatch.setattr(bot.requests, "post", post)
    bot.edit(5, "수정")
    payload = post.call_args.kwargs["json"]
    assert payload["message_id"] == 5 and "reply_markup" not in payload


def test_edit_ignores_not_modified_only(telegram_env, monkeypatch):
    body = '{"description":"Bad Request: message is not modified"}'
    monkeypatch.setattr(bot.requests, "post", Mock(return_value=response(False, 400, body)))
    bot.edit(5, "수정")
    monkeypatch.setattr(bot.requests, "post", Mock(return_value=response(False, 400, "chat not found")))
    with pytest.raises(RuntimeError, match="chat not found"):
        bot.edit(5, "수정")


def test_answer_callback_swallows_errors(telegram_env, monkeypatch):
    monkeypatch.setattr(bot.requests, "post", Mock(return_value=response(False, 400, "query is too old")))
    bot.answer_callback("cb")
    monkeypatch.setattr(bot.requests, "post", Mock(side_effect=bot.requests.ConnectionError("x")))
    bot.answer_callback("cb")


def test_4xx_error_has_body_prefix_without_token(telegram_env, monkeypatch):
    monkeypatch.setattr(bot.requests, "post", Mock(return_value=response(False, 403, "x" * 500)))
    with pytest.raises(RuntimeError) as e:
        bot.send("hi")
    assert "x" * 200 in str(e.value) and "x" * 201 not in str(e.value)
    assert "test-token-placeholder" not in str(e.value)
