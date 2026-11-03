"""5분마다 GitHub Actions가 실행하는 본체. 담당: 권순오. 절차: tasks/bot.md
입력 수신 → 거래 생성·분류 → 애매한 것만 질문 → 답장·버튼으로 확정 → 엔빵·정산."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from math import ceil

import bot
import db
import classify
import parse
from config import KST, ROOT, categories, env, label, load_env, now

STATE_FILE = ROOT / "state.json"
USAGE = "스벅 6500\n+11500 세훈 (입금)\n50000 상대 이체"


def handle_update(update: dict) -> None:
    """수신된 update 하나를 처리한다. polling은 수행하지 않는다."""
    callback = update.get("callback_query")
    message = callback.get("message") if callback else update.get("message")
    if not message or str(message.get("chat", {}).get("id")) != env("TELEGRAM_CHAT_ID"):
        return
    if callback:
        try:
            _handle_callback(callback.get("data", ""), message["message_id"])
        finally:
            bot.answer_callback(callback["id"])
        return
    text = (message.get("text") or "").strip()
    if not text:
        return
    command = text.split()[0].split("@")[0]
    if command == "/today":
        bot.send(today_summary())
    elif command == "/month":
        bot.send(month_summary())
    elif command in {"/start", "/help"}:
        bot.send(USAGE)
    elif message.get("reply_to_message"):
        rows = db.select("transactions", tg_message_id=message["reply_to_message"]["message_id"])
        if rows:
            # Answer 계약의 필드만 전달: 문서에 없는 새 분할 명령은 해석하지 않는다.
            if text.startswith("/"):
                bot.send("이 답장 명령은 지원하지 않습니다")
                return
            apply_answer(rows[0], parse.parse_answer(text))
        else:
            bot.send("어느 거래인지 모르겠어")
    else:
        txn = parse.parse_manual(text)
        if txn is None:
            bot.send(USAGE)
            return
        if message.get("date") is not None:
            txn["ts"] = datetime.fromtimestamp(message["date"], KST).isoformat(timespec="seconds")
        create_txn(txn, source="tg")


def _handle_callback(data: str, message_id: int) -> None:
    """버튼 응답. 해당 메시지에 묶인 거래만 처리해 오래된 콜백을 막는다."""
    kind, *args = data.split(":")
    if not args or not args[0].isdigit():
        return
    if kind == "c" and len(args) == 2:
        rows = db.select("transactions", id=int(args[0]), tg_message_id=message_id)
        if rows and args[1] == "split":
            bot.edit(message_id, "몇 명이서? 이 메시지에 답장해줘 (예: 4명)")
        elif rows and args[1] in categories():
            apply_answer(rows[0], {"category": args[1]})
    elif kind == "s" and len(args) == 2 and args[1].isdigit():
        rows = db.select("transactions", id=int(args[1]), tg_message_id=message_id)
        splits = db.select("splits", id=int(args[0]), status="open")
        if rows and splits and rows[0]["status"] != "confirmed":
            remaining = _settle(splits[0], rows[0], "user")
            bot.edit(message_id, f"✅ 정산 반영 · 남은 받을 돈 {remaining:,}원")
    elif kind == "g" and len(args) == 1:
        rows = db.select("transactions", id=int(args[0]), tg_message_id=message_id)
        if rows and rows[0]["status"] != "confirmed":
            db.update("transactions", {"id": rows[0]["id"]}, {"category": "income", "status": "confirmed"})
            bot.edit(message_id, f"✅ {label('income')}")


def _is_duplicate(txn: dict, key: str) -> bool:
    ts = datetime.fromisoformat(txn["ts"])
    window = timedelta(minutes=2)
    rows = db.select("transactions", amount=txn["amount"], cp_key=key, direction=txn["direction"],
                     ts=("gte", (ts - window).isoformat(timespec="seconds")))
    return any(datetime.fromisoformat(row["ts"]) <= ts + window for row in rows)


def create_txn(txn: dict, source: str = "tg") -> dict | None:
    """파싱 직후 원문 counterparty가 메모리에 있을 때 호출한다.

    원문은 분류에만 전달하고, 이체 상대 실명은 DB에 저장하지 않는다.
    외부 서비스 호출은 이 함수 실행 시에만 발생한다.
    """
    name = txn["counterparty"]
    method = txn["method"]
    key = db.cp_key(name, method)
    # 같은 알림이 두 번 오는 경우만 막는다. 직접 입력은 사람이 일부러 보낸 것이다(엔빵 입금 ×3).
    if source == "auto" and _is_duplicate(txn, key):
        return None
    parties = db.select("counterparties", cp_key=key)
    if parties:
        party = parties[0]
    else:
        person = method == "transfer"
        alias = (f"상대 #{len(db.select('counterparties', type='person')) + 1}"
                 if person else None)
        party = db.upsert("counterparties", {
            "cp_key": key, "type": "person" if person else "merchant",
            "alias": alias,
        }, on_conflict="cp_key")

    category, confidence, cache_row = classify.classify(
        txn, db.load_rules(), db.load_cache())
    if cache_row is not None:
        columns = ("name", "kakao_code", "kakao_name", "category", "confidence")
        db.upsert("merchant_cache", {k: cache_row[k] for k in columns if k in cache_row},
                  on_conflict="name")
    settings = db.get_settings()
    row = db.insert("transactions", {
        "ts": txn["ts"], "amount": txn["amount"],
        "direction": txn["direction"], "method": method,
        "cp_key": key, "cp_label": party.get("alias") if method == "transfer" else name,
        **_classification_values(txn, category, confidence, settings), "source": source,
    })
    # 내 계좌끼리 옮긴 돈은 정산이 아니다.
    if row["direction"] == "in" and row["category"] != "self":
        match_income(row)
    return row


def confirm_category(txn: dict, category: str) -> None:
    """기존 거래 키로 학습하며 표시명에서 키를 재생성하지 않는다."""
    if category not in categories():
        raise ValueError("알 수 없는 카테고리")
    db.update("transactions", {"id": txn["id"]}, {
        "category": category, "confidence": 1.0, "status": "confirmed",
    })
    classify.learn(txn["cp_key"], category)


def _is_split_suspect(txn: dict, category: str | None, settings: dict) -> bool:
    return (txn["direction"] == "out" and category in {"food", "cafe", "culture"}
            and txn["amount"] >= int(settings.get("split_suspect_min", 30000)))


def _classification_values(txn: dict, category: str, confidence: float, settings: dict) -> dict:
    pending = (confidence < float(settings.get("threshold", 0.7))
               or _is_split_suspect(txn, category, settings))
    return {"category": category, "confidence": confidence,
            "status": "pending" if pending else "auto"}


def classify_new(settings: dict, raw_names: dict | None = None) -> None:
    """미분류 행만 재시도한다. raw_names는 현재 실행 메모리의 {거래 ID: 원문}이다."""
    rules, cache = db.load_rules(), db.load_cache()
    for txn in db.select("transactions", category=("is", "null")):
        try:
            key = txn["cp_key"]
            if key in rules:
                category, confidence, cache_row = rules[key], 0.95, None
            else:
                name = (raw_names or {}).get(txn["id"])
                # m: 뒤에는 db.cp_key가 만든 정규화 가맹점명이 있다.
                if name is None and txn["method"] == "card" and key.startswith("m:"):
                    name = key[2:]
                if not name or db.cp_key(name, txn["method"]) != key:
                    raise ValueError("원문 식별 불가")
                category, confidence, cache_row = classify.classify(
                    {**txn, "counterparty": name}, rules, cache)
            if cache_row is not None:
                columns = ("name", "kakao_code", "kakao_name", "category", "confidence")
                db.upsert("merchant_cache", {k: cache_row[k] for k in columns if k in cache_row}, "name")
                cache[cache_row["name"]] = cache_row
            db.update("transactions", {"id": txn["id"]},
                      _classification_values(txn, category, confidence, settings))
        except Exception as exc:
            # 원문과 API 오류 본문은 로그에 남기지 않는다. category=null을 유지한다.
            print(f"거래 {txn['id']} 분류 실패: {type(exc).__name__}")


def apply_answer(txn: dict, ans: dict) -> None:
    """기존 분할은 보존한다. 명시적인 new_split=True만 재설정을 허용한다.

    새 분할 요청도 이미 정산된 분할에는 적용하지 않는다(이력 보존).
    호출자는 반복 이벤트에서 new_split을 다시 전달하지 않아야 한다.
    """
    rows = db.select("transactions", id=txn["id"])
    if not rows:
        raise ValueError("거래가 없음")
    txn = rows[0]  # 오래된 콜백의 category/status를 사용하지 않는다.
    category = "etc" if ans.get("skip") else ans.get("category") or txn.get("category")
    if category is not None and category not in categories():
        raise ValueError("알 수 없는 카테고리")
    wants_split = (txn["direction"] == "out" and not ans.get("skip")
                   and not ans.get("my_share_of_other")
                   and (ans.get("split_n") is not None or ans.get("my_share") is not None))
    split = None
    if wants_split:
        existing = db.select("splits", txn_id=txn["id"])
        split = existing[0] if existing else None
        if split is None or ans.get("new_split") is True:
            if split and (split["remaining"] != split["receivable"]
                          or db.select("settlements", split_id=split["id"])):
                raise ValueError("정산 이력이 있는 분할은 초기화할 수 없음")
            amount = txn["amount"]
            my = ans.get("my_share")
            n = ans.get("split_n")
            if my is not None and (type(my) is not int or not 0 < my < amount):
                raise ValueError("잘못된 내 몫")
            n = n if n is not None else max(2, round(amount / my))
            if type(n) is not int or n < 2:
                raise ValueError("잘못된 분할 인원")
            my = my if my is not None else ceil(amount / n)
            if my >= amount:
                raise ValueError("잘못된 내 몫")
            split = db.upsert("splits", {
                "txn_id": txn["id"], "total": amount, "n": n, "my_share": my,
                "receivable": amount - my, "remaining": amount - my, "status": "open",
            }, "txn_id")
        if category in (None, "transfer", "etc"):
            category = "food"
    if (category in (None, "transfer", "etc") and not ans.get("category")
            and not ans.get("skip") and not wants_split):
        if txn.get("tg_message_id"):
            bot.edit(txn["tg_message_id"], "카테고리를 못 알아들었어. 카테고리를 다시 답장해줘",
                     _buttons(txn, db.get_settings()))
        return
    if category not in categories():
        raise ValueError("알 수 없는 카테고리")
    if txn.get("status") != "confirmed" or txn.get("category") != category:
        confirm_category(txn, category)
    if txn.get("tg_message_id"):
        suffix = (f" · {split['n']}명 엔빵 (내 몫 {split['my_share']:,}원, 받을 돈 {split['remaining']:,}원)"
                  if split else "")
        bot.edit(txn["tg_message_id"], f"✅ {label(category)}{suffix}")


def _settle(split: dict, txn: dict, matched_by: str) -> int:
    db.insert("settlements", {"split_id": split["id"], "txn_id": txn["id"],
                              "amount": txn["amount"], "matched_by": matched_by})
    remaining = max(0, split["remaining"] - txn["amount"])
    db.update("splits", {"id": split["id"]},
              {"remaining": remaining, "status": "done" if remaining == 0 else "open"})
    db.update("transactions", {"id": txn["id"]}, {"category": "settlement", "status": "confirmed"})
    return remaining


def match_income(txn: dict) -> None:
    """입금을 14일 이내의 열린 엔빵에 연결한다. 후보가 없으면 분류 결과를 그대로 둔다."""
    since = (now() - timedelta(days=14)).isoformat(timespec="seconds")
    amount = txn["amount"]
    candidates = [split for split in db.select("splits", status="open", created_at=("gte", since))
                  if abs(amount - split["total"] / split["n"]) <= 10 or amount <= split["remaining"]]
    if len(candidates) == 1:
        remaining = _settle(candidates[0], txn, "auto")
        bot.send(f"정산 반영 · 남은 받을 돈 {remaining:,}원")
    elif candidates:
        rows = []
        for split in candidates[:3]:
            origin = db.select("transactions", id=split["txn_id"])[0]
            rows.append([(f"{origin['cp_label']} {split['total']:,}원", f"s:{split['id']}:{txn['id']}")])
        rows.append([("일반 입금", f"g:{txn['id']}")])
        message_id = bot.send("어느 정산이야?", rows)
        db.update("transactions", {"id": txn["id"]}, {
            "status": "pending", "asked_at": now().isoformat(timespec="seconds"),
            "tg_message_id": message_id,
        })


def month_summary() -> str:
    t = now()
    rows = db.select("monthly_summary", month=t.strftime("%Y-%m"))
    lines = [f"{label(row['category'])} {row['spent']:,}원" for row in rows]
    total = sum(row["spent"] for row in rows)
    receivable = sum(split["remaining"] for split in db.select("splits", status="open"))
    return "\n".join([f"{t.month}월 지출", *lines, f"합계 {total:,}원", f"받을 돈 {receivable:,}원"])


def today_summary() -> str:
    start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    my_shares = {split["txn_id"]: split["my_share"] for split in db.select("splits")}
    rows = db.select("transactions", direction="out", ts=("gte", start.isoformat(timespec="seconds")))
    spent = sum(my_shares.get(row["id"], row["amount"]) for row in rows if row.get("category") != "self")
    return f"오늘 순지출 {spent:,}원"


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"tg_offset": 0, "last_digest_date": None,
                "asked_today": {"date": None, "count": 0}, "last_run": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _buttons(txn: dict, settings: dict) -> list:
    picks = []
    current = txn.get("category")
    if current in categories() and current not in {"etc", "transfer", "income"} and categories()[current].get("ask", True):
        picks.append(current)
    defaults = ("living", "food", "gift") if txn["method"] == "transfer" else ("food", "shopping")
    for code in defaults:
        if len(picks) < 2 and code not in picks and categories()[code].get("ask", True):
            picks.append(code)
    rows = [[(label(code), f"c:{txn['id']}:{code}") for code in picks]]
    split = ("엔빵", f"c:{txn['id']}:split")
    other = (label("etc"), f"c:{txn['id']}:etc")
    if _is_split_suspect(txn, current, settings):
        rows.insert(0, [split])
        rows.append([other])
    else:
        rows.append([split, other])
    if txn["direction"] == "in":
        rows.append([(label("income"), f"c:{txn['id']}:income")])
    return rows


def _unasked() -> list:
    return db.select("transactions", status="pending", asked_at=("is", "null"), _order="ts.asc")


def _ask(txn: dict, settings: dict, t: datetime) -> None:
    ts = datetime.fromisoformat(txn["ts"]).astimezone(KST)
    direction = "출금" if txn["direction"] == "out" else "입금"
    message_id = bot.send(
        f"[확인] {ts:%m/%d %H:%M} · {txn['cp_label']} {txn['amount']:,}원 {direction}. 뭐였어?\n"
        f"예상 분류: {label(txn.get('category'))}\n버튼을 누르거나 답장해줘 (예: 치킨 4명)", _buttons(txn, settings))
    db.update("transactions", {"id": txn["id"]}, {
        "asked_at": t.isoformat(timespec="seconds"), "tg_message_id": message_id})


def ask_pending(settings: dict, state: dict, t: datetime) -> None:
    start, end = int(settings.get("quiet_start", 23)), int(settings.get("quiet_end", 8))
    quiet = start <= t.hour < end if start <= end else t.hour >= start or t.hour < end
    if quiet:
        return
    for txn in _unasked():
        if state["asked_today"]["count"] >= int(settings.get("daily_ask_cap", 5)):
            break
        _ask(txn, settings, t)
        state["asked_today"]["count"] += 1


def digest(settings: dict, state: dict, t: datetime) -> None:
    today = t.date().isoformat()
    if t.hour < int(settings.get("digest_hour", 21)) or state["last_digest_date"] == today:
        return
    pending = _unasked()
    if pending:
        bot.send(f"오늘 미뤄진 {len(pending)}건")
        for txn in pending:
            _ask(txn, settings, t)
        state["last_digest_date"] = today


def process_inbox() -> None:
    """처리한 원문은 성공·실패와 상관없이 DB에서 지운다. 못 읽은 알림은 한 번만 알린다."""
    for row in db.select("inbox", status="new"):
        try:
            raw = row["raw_text"] or ""
            txn = parse.parse_push(raw)
            if txn is None:
                # 전송이 실패해도 원문이 남지 않게 먼저 지운다.
                db.update("inbox", {"id": row["id"]}, {"status": "failed", "raw_text": None})
                bot.send(f"못 읽었어: {raw[:30]}")
                continue
            create_txn(txn, source="auto")
            db.update("inbox", {"id": row["id"]}, {"status": "done", "raw_text": None})
        except Exception as exc:
            print(f"inbox {row['id']} 처리 실패: {type(exc).__name__}")


def _select_bot() -> None:
    """TEST_ 값이 있으면 테스트 봇과 별도 state 파일을 쓴다. Actions에는 없으므로 본 봇을 쓴다.

    TEST_ 값이 하나만 있으면 본 봇과 섞이지 않게 중단한다. 누락 시 첫 네트워크 호출 전에 멈춘다.
    """
    global STATE_FILE
    if os.environ.get("TEST_TELEGRAM_BOT_TOKEN") or os.environ.get("TEST_TELEGRAM_CHAT_ID"):
        os.environ["TELEGRAM_BOT_TOKEN"] = env("TEST_TELEGRAM_BOT_TOKEN")
        os.environ["TELEGRAM_CHAT_ID"] = env("TEST_TELEGRAM_CHAT_ID")
        STATE_FILE = ROOT / "state.test.json"
    else:
        env("TELEGRAM_BOT_TOKEN")
        env("TELEGRAM_CHAT_ID")


def main() -> None:
    load_env()
    _select_bot()
    state = load_state()
    settings = db.get_settings()
    t = now()
    if state["asked_today"]["date"] != t.date().isoformat():
        state["asked_today"] = {"date": t.date().isoformat(), "count": 0}
    try:
        for update in bot.get_updates(state["tg_offset"]):
            if update["update_id"] < state["tg_offset"]:
                continue
            try:
                handle_update(update)
            except Exception as exc:
                print(f"update {update['update_id']} 처리 실패: {type(exc).__name__}")
            state["tg_offset"] = update["update_id"] + 1
        process_inbox()
        classify_new(settings)
        ask_pending(settings, state, t)
        digest(settings, state, t)
    finally:
        state["last_run"] = t.isoformat(timespec="seconds")
        save_state(state)


if __name__ == "__main__":
    main()
