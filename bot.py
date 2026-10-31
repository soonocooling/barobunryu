"""텔레그램 봇 API. 담당: 권순오. 절차: tasks/bot.md
send()만 뼈대 확인용으로 동작한다. 나머지는 "봇 개발 시작해"로 구현한다."""
from __future__ import annotations

import requests

from config import env

TIMEOUT = 10


def _url(method: str) -> str:
    return f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/{method}"


def send(text: str, buttons: list[list[tuple[str, str]]] | None = None) -> int:
    """TELEGRAM_CHAT_ID로 메시지를 보내고 message_id를 돌려준다. buttons = [[(라벨, callback_data), ...], ...]"""
    payload: dict = {"chat_id": env("TELEGRAM_CHAT_ID"), "text": text}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": [
            [{"text": t, "callback_data": d} for t, d in row] for row in buttons
        ]}
    # requests 오류에는 토큰이 포함된 URL이 들어갈 수 있으므로 원문을 전파하지 않는다.
    url = _url("sendMessage")
    try:
        r = requests.post(url, json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if data.get("ok") is not True:
            raise ValueError("Telegram API failure")
        return int(data["result"]["message_id"])
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError):
        raise RuntimeError("Telegram 메시지 전송 실패. 설정과 연결 상태를 확인하세요.") from None


def get_updates(offset: int) -> list[dict]:
    raise NotImplementedError("tasks/bot.md")


def edit(message_id: int, text: str) -> None:
    raise NotImplementedError("tasks/bot.md")


def answer_callback(cb_id: str) -> None:
    raise NotImplementedError("tasks/bot.md")
