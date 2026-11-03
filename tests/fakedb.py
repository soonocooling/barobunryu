"""db.py를 메모리 dict로 흉내 낸다. monkeypatch.setattr(watch, "db", FakeDB(...))로 주입한다."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime


def _comparable(value):
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return value


OPS = {
    "gte": lambda a, b: a >= b,
    "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "lt": lambda a, b: a < b,
}


def _matches(row: dict, filters: dict) -> bool:
    for key, cond in filters.items():
        value = row.get(key)
        if isinstance(cond, tuple):
            op, operand = cond
            if op == "is":
                assert operand == "null", "fakedb는 is.null만 지원한다"
                if value is not None:
                    return False
            elif value is None or not OPS[op](_comparable(value), _comparable(operand)):
                return False
        elif value != cond:
            return False
    return True


class FakeDB:
    DEFAULTS = {
        "transactions": {"status": "auto", "asked_at": None, "tg_message_id": None, "confidence": None},
        "splits": {"status": "open"},
    }

    def __init__(self, clock, settings: dict | None = None, rules: dict | None = None):
        self.clock = clock
        self.settings = {"threshold": 0.7, "daily_ask_cap": 5, "digest_hour": 21,
                         "quiet_start": 23, "quiet_end": 8, "split_suspect_min": 30000,
                         **(settings or {})}
        self.rules = rules or {}
        self.tables: dict[str, list[dict]] = {}
        self._next_id = 0

    def rows(self, table: str) -> list[dict]:
        return self.tables.setdefault(table, [])

    def select(self, table: str, **filters) -> list[dict]:
        order = filters.pop("_order", None)
        limit = filters.pop("_limit", None)
        filters.pop("_select", None)
        found = [dict(r) for r in self.rows(table) if _matches(r, filters)]
        if order:
            column, _, direction = order.partition(".")
            found.sort(key=lambda r: _comparable(r[column]), reverse=direction == "desc")
        return found[:limit] if limit else found

    def insert(self, table: str, row: dict) -> dict:
        self._next_id += 1
        stored = {"id": self._next_id, "created_at": self.clock().isoformat(timespec="seconds"),
                  **self.DEFAULTS.get(table, {}), **row}
        self.rows(table).append(stored)
        return dict(stored)

    def upsert(self, table: str, row: dict, on_conflict: str) -> dict:
        for existing in self.rows(table):
            if existing.get(on_conflict) == row[on_conflict]:
                existing.update(row)
                return dict(existing)
        return self.insert(table, row)

    def update(self, table: str, match: dict, values: dict) -> None:
        for row in self.rows(table):
            if _matches(row, match):
                row.update(values)

    def delete(self, table: str, match: dict) -> None:
        self.tables[table] = [r for r in self.rows(table) if not _matches(r, match)]

    def cp_key(self, name: str, method: str) -> str:
        norm = re.sub(r"\s+", "", name).lower()
        if method == "transfer":
            return "p:" + hashlib.sha256(norm.encode()).hexdigest()[:16]
        return "m:" + norm

    def get_settings(self) -> dict:
        return dict(self.settings)

    def load_rules(self) -> dict:
        return dict(self.rules)

    def load_cache(self) -> dict:
        return {r["name"]: r for r in self.rows("merchant_cache")}
