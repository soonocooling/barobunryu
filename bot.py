"""텔레그램 봇 API. 담당: 권순오. 절차: tasks/bot.md
send()만 뼈대 확인용으로 동작한다. 나머지는 "봇 개발 시작해"로 구현한다."""
from __future__ import annotations

import requests

from config import env

TIMEOUT = 10


def _url(method: str) -> str:
    return f"https://api.telegram.org/bot{env('BOT_TOKEN')}/{method}"


def send(text: str, buttons: list[list[tuple[str, str]]] | None = None) -> int:
    """CHAT_ID로 메시지를 보내고 message_id를 돌려준다. buttons = [[(라벨, callback_data), ...], ...]"""
    payload: dict = {"chat_id": env("CHAT_ID"), "text": text}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": [
            [{"text": t, "callback_data": d} for t, d in row] for row in buttons
        ]}
    r = requests.post(_url("sendMessage"), json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["result"]["message_id"]


def get_updates(offset: int) -> list[dict]:
    raise NotImplementedError("tasks/bot.md")


def edit(message_id: int, text: str) -> None:
    raise NotImplementedError("tasks/bot.md")


def answer_callback(cb_id: str) -> None:
    raise NotImplementedError("tasks/bot.md")
