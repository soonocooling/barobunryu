"""5분마다 GitHub Actions가 실행하는 본체. 담당: 권순오. 절차: tasks/bot.md
입력 수신 → 거래 생성 → 분류 → 애매한 것만 질문 → 답장·버튼으로 확정 → 엔빵·정산."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from math import ceil

import bot
import classify
import db
import parse
from config import KST, ROOT, categories, env, label, load_env, now

STATE_FILE = ROOT / "state.json"
USAGE = "스벅 6500\n+11500 세훈 (입금)\n50000 상대 이체"
SPLIT_SUSPECT_CATEGORIES = ("food", "cafe", "culture")
UNKNOWN_CATEGORIES = (None, "transfer", "etc")


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"tg_offset": 0, "last_digest_date": None,
                "asked_today": {"date": None, "count": 0}, "last_run": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _log_failure(what: str, e: Exception) -> None:
    # Actions 로그는 공개다. DB 오류 본문에 거래 값이 섞일 수 있어 예외 종류만 남긴다.
    print(f"{what} 처리 실패: {type(e).__name__}")


# ---------- 입력 수신 ----------

def _from_me(msg: dict | None) -> bool:
    return bool(msg) and str(msg["chat"]["id"]) == env("TELEGRAM_CHAT_ID")


def handle_update(u: dict) -> None:
    if "callback_query" in u:
        if _from_me(u["callback_query"].get("message")):
            handle_callback(u["callback_query"])
    elif _from_me(u.get("message")):
        handle_message(u["message"])


def handle_message(msg: dict) -> None:
    text = (msg.get("text") or "").strip()
    command = text.split()[0].split("@")[0] if text else ""
    if command == "/today":
        bot.send(today_summary())
    elif command == "/month":
        bot.send(month_summary())
    elif command in ("/start", "/help"):
        bot.send(USAGE)
    elif msg.get("reply_to_message"):
        rows = db.select("transactions", tg_message_id=msg["reply_to_message"]["message_id"])
        if rows:
            apply_answer(rows[0], parse.parse_answer(text))
        else:
            bot.send("어느 거래인지 모르겠어")
    else:
        txn = parse.parse_manual(text)
        if not txn or not txn.get("counterparty"):
            bot.send(USAGE)
            return
        # 실행이 밀려도 거래 시각이 처리 시각으로 바뀌지 않게 메시지 시각을 쓴다.
        if msg.get("date"):
            txn["ts"] = datetime.fromtimestamp(msg["date"], KST).isoformat(timespec="seconds")
        create_txn(txn, source="tg")


def handle_callback(cb: dict) -> None:
    try:
        kind, *args = cb.get("data", "").split(":")
        if kind == "c":
            txn = _get_txn(args[0])
            if txn and args[1] == "split":
                bot.edit(cb["message"]["message_id"], "몇 명이서? 이 메시지에 답장해줘 (예: 4명)")
            elif txn:
                apply_answer(txn, {"category": args[1]})
        elif kind == "s":
            txn = _get_txn(args[1])
            splits = db.select("splits", id=int(args[0]))
            if txn and splits and txn["status"] != "confirmed":
                remaining = _settle(splits[0], txn, "user")
                bot.edit(cb["message"]["message_id"], f"✅ 정산 반영 · 남은 받을 돈 {remaining:,}원")
        elif kind == "g":
            txn = _get_txn(args[0])
            if txn and txn["status"] != "confirmed":
                db.update("transactions", {"id": txn["id"]}, {"category": "income", "status": "confirmed"})
                bot.edit(cb["message"]["message_id"], f"✅ {label('income')}")
        elif kind == "j":
            txn = _get_txn(args[0])
            if txn:
                apply_answer(txn, {"split_n": int(args[1])})
    finally:
        bot.answer_callback(cb["id"])


def _get_txn(txn_id: str) -> dict | None:
    rows = db.select("transactions", id=int(txn_id))
    return rows[0] if rows else None


# ---------- 거래 생성·분류 ----------

def create_txn(t: dict, source: str) -> dict | None:
    name, method = t["counterparty"], t["method"]
    key = db.cp_key(name, method)
    # 같은 알림이 두 번 오는 경우만 막는다. 직접 입력은 사람이 일부러 보낸 것이다(엔빵 입금 ×3).
    if source == "auto" and _is_duplicate(t, key):
        return None
    alias = _ensure_counterparty(key, method)
    txn = db.insert("transactions", {
        "ts": t["ts"], "amount": t["amount"], "direction": t["direction"], "method": method,
        "cp_key": key,
        "cp_label": alias if method == "transfer" else name,  # 사람 실명은 어디에도 저장하지 않는다.
        "category": None, "status": "auto", "source": source,
    })
    if txn["direction"] == "in":
        match_income(txn)
    return txn


def _is_duplicate(t: dict, key: str) -> bool:
    ts = datetime.fromisoformat(t["ts"])
    window = timedelta(minutes=2)
    rows = db.select("transactions", amount=t["amount"], cp_key=key,
                     ts=("gte", (ts - window).isoformat(timespec="seconds")))
    return any(datetime.fromisoformat(r["ts"]) <= ts + window for r in rows)


def _ensure_counterparty(key: str, method: str) -> str | None:
    rows = db.select("counterparties", cp_key=key)
    if rows:
        return rows[0].get("alias")
    if method == "transfer":
        alias = f"상대 #{len(db.select('counterparties', type='person')) + 1}"
        db.upsert("counterparties", {"cp_key": key, "alias": alias, "type": "person"}, "cp_key")
        return alias
    db.upsert("counterparties", {"cp_key": key, "alias": None, "type": "merchant"}, "cp_key")
    return None


def process_inbox() -> None:
    for row in db.select("inbox", status="new"):
        try:
            txn = parse.parse_push(row["raw_text"])
            if txn and txn.get("counterparty"):
                create_txn(txn, source="auto")
                db.update("inbox", {"id": row["id"]}, {"raw_text": None, "status": "done"})
            else:
                db.update("inbox", {"id": row["id"]}, {"raw_text": None, "status": "failed"})
                bot.send(f"못 읽었어: {row['raw_text'][:30]}")
        except Exception as e:
            _log_failure(f"inbox {row['id']}", e)


def _classify(txn: dict, rules: dict, cache: dict) -> tuple[str, float, dict | None]:
    # DB 행에는 실명이 없어 classify가 사람의 cp_key를 다시 계산하지 못한다. 규칙은 저장된 키로 먼저 본다.
    if txn["cp_key"] in rules:
        return rules[txn["cp_key"]], 0.95, None
    return classify.classify({**txn, "counterparty": txn["cp_label"]}, rules, cache)


def _is_split_suspect(txn: dict, s: dict) -> bool:
    return (txn["direction"] == "out" and txn["category"] in SPLIT_SUSPECT_CATEGORIES
            and txn["amount"] >= s["split_suspect_min"])


def classify_new(s: dict) -> None:
    rules, cache = db.load_rules(), db.load_cache()
    for txn in db.select("transactions", category=("is", "null")):
        category, confidence, cache_row = _classify(txn, rules, cache)
        if cache_row:
            db.upsert("merchant_cache", cache_row, "name")
            cache[cache_row["name"]] = cache_row
        txn["category"] = category
        ambiguous = confidence < s["threshold"] or _is_split_suspect(txn, s)
        db.update("transactions", {"id": txn["id"]}, {
            "category": category, "confidence": confidence,
            "status": "pending" if ambiguous else "auto",
        })


# ---------- 질문 ----------

def _question(txn: dict) -> str:
    ts = datetime.fromisoformat(txn["ts"]).astimezone(KST)
    direction = "출금" if txn["direction"] == "out" else "입금"
    return (f"[확인] {ts:%m/%d %H:%M} · {txn['cp_label']} {txn['amount']:,}원 {direction}. 뭐였어?\n"
            "버튼을 누르거나 이 메시지에 답장해줘 (예: 치킨 4명)")


def _buttons(txn: dict, s: dict) -> list[list[tuple[str, str]]]:
    tid, current = txn["id"], txn.get("category")
    split = ("엔빵", f"c:{tid}:split")
    other = (label("etc"), f"c:{tid}:etc")
    picks = []
    if current not in (*UNKNOWN_CATEGORIES, "income") and categories()[current].get("ask", True):
        picks.append(current)
    for code in ("living", "food", "gift") if txn["method"] == "transfer" else ("food", "shopping"):
        if len(picks) < 2 and code not in picks:
            picks.append(code)
    rows = [[(label(code), f"c:{tid}:{code}") for code in picks]]
    if _is_split_suspect(txn, s):
        rows.insert(0, [split])
        rows.append([other])
    else:
        rows.append([split, other])
    if txn["direction"] == "in":  # 수입은 ask:false라 후보에 없으니 1탭 확정 버튼을 따로 준다.
        rows.append([("일반 입금", f"g:{tid}")])
    return rows


def _unasked() -> list[dict]:
    return db.select("transactions", status="pending", asked_at=("is", "null"), _order="ts.asc")


def _ask(txn: dict, s: dict, t: datetime) -> None:
    message_id = bot.send(_question(txn), _buttons(txn, s))
    # 반복 금지의 기준은 asked_at이다.
    db.update("transactions", {"id": txn["id"]},
              {"asked_at": t.isoformat(timespec="seconds"), "tg_message_id": message_id})


def _is_quiet(s: dict, t: datetime) -> bool:
    start, end = s["quiet_start"], s["quiet_end"]
    return start <= t.hour < end if start <= end else t.hour >= start or t.hour < end


def ask_pending(s: dict, state: dict, t: datetime) -> None:
    if _is_quiet(s, t):
        return
    for txn in _unasked():
        if state["asked_today"]["count"] >= s["daily_ask_cap"]:
            return
        _ask(txn, s, t)
        state["asked_today"]["count"] += 1


def digest(s: dict, state: dict, t: datetime) -> None:
    today = t.date().isoformat()
    if t.hour < s["digest_hour"] or state["last_digest_date"] == today:
        return
    pending = _unasked()
    if not pending:
        return
    bot.send(f"오늘 미뤄진 {len(pending)}건")
    for txn in pending:
        _ask(txn, s, t)
    state["last_digest_date"] = today


# ---------- 답장 적용 ----------

def apply_answer(txn: dict, ans: dict) -> None:
    skip = ans.get("skip")
    wants_split = (txn["direction"] == "out" and not skip and not ans.get("my_share_of_other")
                   and (ans.get("split_n") or ans.get("my_share")))
    category = "etc" if skip else ans.get("category") or txn.get("category")
    # 엔빵 답("4명")은 카테고리가 없어도 아래에서 식비로 확정되므로 되묻지 않는다.
    if not skip and not ans.get("category") and category in UNKNOWN_CATEGORIES and not wants_split:
        bot.edit(txn["tg_message_id"], "카테고리를 못 알아들었어\n" + _question(txn),
                 _buttons(txn, db.get_settings()))
        return

    split_text = ""
    if wants_split:
        amount = txn["amount"]
        n = ans.get("split_n") or max(2, round(amount / ans["my_share"]))
        my = ans.get("my_share") or ceil(amount / n)
        if my < amount:
            receivable = amount - my
            db.upsert("splits", {"txn_id": txn["id"], "total": amount, "n": n, "my_share": my,
                                 "receivable": receivable, "remaining": receivable, "status": "open"},
                      "txn_id")
            split_text = f" · {n}명 엔빵 (내 몫 {my:,}원, 받을 돈 {receivable:,}원)"
            if category in UNKNOWN_CATEGORIES:
                category = "food"

    db.update("transactions", {"id": txn["id"]},
              {"category": category, "status": "confirmed", "confidence": 1.0})
    classify.learn(txn["cp_key"], category)
    bot.edit(txn["tg_message_id"], f"✅ {label(category)}{split_text}")


# ---------- 정산 ----------

def _settle(split: dict, txn: dict, matched_by: str) -> int:
    db.insert("settlements", {"split_id": split["id"], "txn_id": txn["id"],
                              "amount": txn["amount"], "matched_by": matched_by})
    remaining = max(0, split["remaining"] - txn["amount"])
    db.update("splits", {"id": split["id"]},
              {"remaining": remaining, "status": "done" if remaining == 0 else "open"})
    db.update("transactions", {"id": txn["id"]}, {"category": "settlement", "status": "confirmed"})
    return remaining


def match_income(txn: dict) -> None:
    since = (now() - timedelta(days=14)).isoformat(timespec="seconds")
    amount = txn["amount"]
    candidates = [sp for sp in db.select("splits", status="open", created_at=("gte", since))
                  if abs(amount - sp["total"] / sp["n"]) <= 10 or amount <= sp["remaining"]]
    if len(candidates) == 1:
        remaining = _settle(candidates[0], txn, "auto")
        bot.send(f"정산 반영 · 남은 받을 돈 {remaining:,}원")
    elif candidates:
        rows = []
        for sp in candidates[:3]:
            origin = _get_txn(sp["txn_id"])
            rows.append([(f"{origin['cp_label']} {sp['total']:,}원", f"s:{sp['id']}:{txn['id']}")])
        rows.append([("일반 입금", f"g:{txn['id']}")])
        message_id = bot.send("어느 정산이야?", rows)
        db.update("transactions", {"id": txn["id"]}, {
            "status": "pending", "asked_at": now().isoformat(timespec="seconds"),
            "tg_message_id": message_id,
        })


# ---------- 요약 ----------

def month_summary() -> str:
    t = now()
    rows = db.select("monthly_summary", month=t.strftime("%Y-%m"))
    lines = [f"{label(r['category'])} {r['spent']:,}원" for r in rows]
    total = sum(r["spent"] for r in rows)
    receivable = sum(sp["remaining"] for sp in db.select("splits", status="open"))
    return "\n".join([f"{t.month}월 지출", *lines, f"합계 {total:,}원", f"받을 돈 {receivable:,}원"])


def today_summary() -> str:
    start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    my_shares = {sp["txn_id"]: sp["my_share"] for sp in db.select("splits")}
    rows = db.select("transactions", direction="out", ts=("gte", start.isoformat(timespec="seconds")))
    spent = sum(my_shares.get(r["id"], r["amount"]) for r in rows if r.get("category") != "self")
    return f"오늘 순지출 {spent:,}원"


# ---------- 실행 ----------

def main() -> None:
    load_env()
    state = load_state()
    s = db.get_settings()
    t = now()
    today = t.date().isoformat()
    if state["asked_today"]["date"] != today:
        state["asked_today"] = {"date": today, "count": 0}
    # 뒤 단계가 실패해도 offset은 저장한다. 안 그러면 같은 입력이 다음 실행에서 또 처리된다.
    try:
        for u in bot.get_updates(state["tg_offset"]):
            try:
                handle_update(u)
            except Exception as e:  # 한 건 실패가 나머지를 막지 않는다
                _log_failure(f"update {u['update_id']}", e)
            state["tg_offset"] = u["update_id"] + 1  # 실패해도 넘긴다(무한 재처리 방지)
        process_inbox()
        classify_new(s)
        ask_pending(s, state, t)
        digest(s, state, t)
    finally:
        state["last_run"] = t.isoformat(timespec="seconds")
        save_state(state)


if __name__ == "__main__":
    main()
