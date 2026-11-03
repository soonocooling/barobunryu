"""Supabase PostgREST 래퍼. 담당: 박세훈. 절차: tasks/classify.md.

환경변수는 호출할 때 읽는다. 로컬 파일을 쓰는 실행 진입점은 config.load_env()를
먼저 호출한다. 테이블 컬럼명과 제약 조건은 supabase/schema.sql을 따른다.
"""
from __future__ import annotations

import hashlib
import re

import requests

from config import env

TIMEOUT = 10


def _params(filters: dict) -> dict:
    """호출자의 필터를 변경하지 않고 PostgREST 쿼리로 변환한다."""
    special = {"_order": "order", "_limit": "limit", "_select": "select", "_and": "and"}
    params = {}
    for key, value in filters.items():
        if key in special:
            params[special[key]] = value
            continue
        if key.startswith("_"):
            raise ValueError(f"지원하지 않는 조회 옵션: {key}")
        op = "eq"
        if isinstance(value, tuple):
            if len(value) != 2:
                raise ValueError("필터 튜플은 (연산자, 값)이어야 합니다.")
            op, value = value
        if value is None:
            value = "null"
        elif isinstance(value, bool):
            value = str(value).lower()
        params[key] = f"{op}.{value}"
    return params


def _request(method: str, table: str, *, params=None, row=None, prefer=None):
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", table):
        raise ValueError("올바른 테이블 또는 뷰 이름이 필요합니다.")
    base = env("SUPABASE_URL").rstrip("/")
    key = env("SUPABASE_SERVICE_KEY")
    headers = {"apikey": key, "Authorization": f"Bearer {key}",
               "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    try:
        response = requests.request(method, f"{base}/rest/v1/{table}",
                                    headers=headers, params=params, json=row,
                                    timeout=TIMEOUT)
    except requests.RequestException:
        # 요청 예외의 원문에는 URL이나 인증 정보가 들어갈 수 있다.
        raise RuntimeError("Supabase 요청 실패. 연결 상태를 확인하세요.") from None
    if not 200 <= response.status_code < 300:
        # 키를 먼저 가린 다음 자른다(잘린 키 일부가 노출되지 않게 한다).
        detail = response.text.replace(key, "[REDACTED]")[:300]
        raise RuntimeError(f"Supabase {method} {table} 실패 ({response.status_code}): {detail}")
    if method in ("PATCH", "DELETE"):
        return None
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("Supabase 응답이 올바른 JSON이 아닙니다.") from None
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise RuntimeError("Supabase 응답은 행 객체의 목록이어야 합니다.")
    return data


def select(table: str, **filters) -> list[dict]:
    """테이블/뷰 조회. k=v, k=(op, v), _order/_limit/_select/_and 지원.

    예: select("transactions", status="pending", asked_at=("is", "null"))
    반환은 행 dict 목록이며 일치하는 행이 없으면 []이다.
    """
    return _request("GET", table, params=_params(filters))


def insert(table: str, row: dict) -> dict:
    """컬럼명:값 dict 한 행을 저장하고 DB 기본값을 포함한 행을 반환한다."""
    rows = _request("POST", table, row=row, prefer="return=representation")
    if len(rows) != 1:
        raise RuntimeError("Supabase insert 응답에 저장된 행 하나가 필요합니다.")
    return rows[0]


def upsert(table: str, row: dict, on_conflict: str) -> dict:
    """PK/UNIQUE 컬럼(예: merchant_cache의 name)을 기준으로 저장/갱신한다."""
    if not on_conflict.strip():
        raise ValueError("on_conflict에 PK 또는 UNIQUE 컬럼을 지정하세요.")
    rows = _request("POST", table, params={"on_conflict": on_conflict}, row=row,
                    prefer="resolution=merge-duplicates,return=representation")
    if len(rows) != 1:
        raise RuntimeError("Supabase upsert 응답에 저장된 행 하나가 필요합니다.")
    return rows[0]


def update(table: str, match: dict, values: dict) -> None:
    """match에 맞는 행의 values 컬럼을 수정한다. 반환값은 없다."""
    _require_match(match)
    _request("PATCH", table, params=_params(match), row=values, prefer="return=minimal")


def delete(table: str, match: dict) -> None:
    """match에 맞는 행을 삭제한다. 반환값은 없다."""
    _require_match(match)
    _request("DELETE", table, params=_params(match), prefer="return=minimal")


def _require_match(match: dict) -> None:
    if not any(not key.startswith("_") or (key == "_and" and value)
               for key, value in match.items()):
        raise ValueError("수정·삭제에는 대상 행을 제한하는 조건이 필요합니다.")


def cp_key(name: str, method: str) -> str:
    """공백 제거·소문자화. 이체는 CP_SALT를 더한 SHA-256 앞 16자로 익명화."""
    norm = re.sub(r"\s+", "", name).lower()
    if method == "transfer":
        digest = hashlib.sha256((norm + env("CP_SALT")).encode("utf-8")).hexdigest()
        return "p:" + digest[:16]
    return "m:" + norm


def get_settings() -> dict:
    """settings → {key: value}. 숫자 문자열은 int, 그다음 float로 변환한다."""
    settings = {}
    for row in select("settings"):
        value = row["value"]
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                pass
        settings[row["key"]] = value
    return settings


def load_rules() -> dict:
    """활성 규칙만 {cp_key: category}로 반환한다."""
    return {row["cp_key"]: row["category"] for row in select("rules", active=True)}


def load_cache() -> dict:
    """merchant_cache를 {정규화한 가맹점명: 전체 행 dict}로 반환한다."""
    return {row["name"]: row for row in select("merchant_cache")}
