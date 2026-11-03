"""텔레그램 봇 API. 담당: 권순오. 절차: tasks/bot.md"""
from __future__ import annotations

import json

import requests

from config import env

TIMEOUT = 10


def _url(method: str) -> str:
    return f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/{method}"


def _keyboard(buttons: list[list[tuple[str, str]]]) -> dict:
    return {"inline_keyboard": [
        [{"text": t, "callback_data": d} for t, d in row] for row in buttons
    ]}


def _call(http, method: str, **kwargs):
    # requests 오류에는 토큰이 포함된 URL이 들어갈 수 있으므로 원문을 전파하지 않는다.
    url = _url(method)
    try:
        r = http(url, timeout=TIMEOUT, **kwargs)
        if not r.ok:
            raise RuntimeError(f"Telegram {method} 실패 {r.status_code}: {r.text[:200]}")
        data = r.json()
        if data.get("ok") is not True:
            raise ValueError("Telegram API failure")
        return data["result"]
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError):
        raise RuntimeError("Telegram 요청 실패. 설정과 연결 상태를 확인하세요.") from None


def get_updates(offset: int) -> list[dict]:
    return _call(requests.get, "getUpdates", params={
        "offset": offset,
        "timeout": 0,
        "allowed_updates": json.dumps(["message", "callback_query"]),
    })


def send(text: str, buttons: list[list[tuple[str, str]]] | None = None) -> int:
    """TELEGRAM_CHAT_ID로 메시지를 보내고 message_id를 돌려준다. buttons = [[(라벨, callback_data), ...], ...]"""
    payload: dict = {"chat_id": env("TELEGRAM_CHAT_ID"), "text": text}
    if buttons:
        payload["reply_markup"] = _keyboard(buttons)
    return int(_call(requests.post, "sendMessage", json=payload)["message_id"])


def edit(message_id: int, text: str, buttons: list[list[tuple[str, str]]] | None = None) -> None:
    """메시지를 고친다. buttons가 None이면 키보드를 제거한다."""
    payload: dict = {"chat_id": env("TELEGRAM_CHAT_ID"), "message_id": message_id, "text": text}
    if buttons:
        payload["reply_markup"] = _keyboard(buttons)
    try:
        _call(requests.post, "editMessageText", json=payload)
    except RuntimeError as e:
        if "message is not modified" not in str(e):
            raise


def answer_callback(cb_id: str, text: str | None = None) -> None:
    """버튼 응답. 만료(query is too old) 등 모든 오류를 무시한다."""
    payload: dict = {"callback_query_id": cb_id}
    if text:
        payload["text"] = text
    try:
        _call(requests.post, "answerCallbackQuery", json=payload)
    except RuntimeError:
        pass
