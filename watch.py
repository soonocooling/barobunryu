"""5분마다 GitHub Actions가 실행하는 본체. 담당: 권순오. 절차: tasks/bot.md
현재는 뼈대: 수동 실행(workflow_dispatch) 또는 로컬 실행일 때만 "봇이 살아 있습니다"를 보낸다."""
from __future__ import annotations

import json
import os

import bot
from config import ROOT, env, load_env, now

STATE_FILE = ROOT / "state.json"


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"tg_offset": 0, "last_digest_date": None,
                "asked_today": {"date": None, "count": 0}, "last_run": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    load_env()
    for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        env(name)  # 누락된 이름만 알리고 값은 출력하지 않는다.
    state = load_state()
    event = os.environ.get("GITHUB_EVENT_NAME", "local")
    if event in ("workflow_dispatch", "local"):
        bot.send("봇이 살아 있습니다")
    state["last_run"] = now().isoformat(timespec="seconds")
    save_state(state)


if __name__ == "__main__":
    main()
