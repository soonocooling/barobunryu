"""텔레그램 봇 API. 담당: 권순오. 절차: tasks/bot.md
메시지 수신·전송·수정·콜백 응답을 지원한다."""
from __future__ import annotations

import requests
import json

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
    try:
        response = requests.get(_url("getUpdates"), params={
            "offset": offset, "timeout": 0,
            "allowed_updates": json.dumps(["message", "callback_query"]),
        }, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        result = data.get("result")
        if data.get("ok") is not True or not isinstance(result, list):
            raise ValueError("Invalid updates")
        if any(not isinstance(u, dict) or type(u.get("update_id")) is not int for u in result):
            raise ValueError("Invalid update")
        return result
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        raise RuntimeError("Telegram 업데이트 수신 실패") from None


def edit(message_id: int, text: str, buttons=None) -> None:
    try:
        response = requests.post(_url("editMessageText"), json={
            "chat_id": env("TELEGRAM_CHAT_ID"), "message_id": message_id,
            "text": text, "reply_markup": {"inline_keyboard": [
                [{"text": t, "callback_data": d} for t, d in row] for row in (buttons or [])]},
        }, timeout=TIMEOUT)
        data = response.json()
        if "message is not modified" in str(data.get("description", "")):
            return
        response.raise_for_status()
        if data.get("ok") is not True:
            raise ValueError("Telegram API failure")
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        raise RuntimeError("Telegram 메시지 수정 실패") from None


def answer_callback(cb_id: str) -> None:
    try:
        response = requests.post(_url("answerCallbackQuery"),
                                 json={"callback_query_id": cb_id}, timeout=TIMEOUT)
        response.raise_for_status()
    except (requests.RequestException, RuntimeError):
        pass
