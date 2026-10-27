"""Supabase PostgREST 래퍼. 담당: 박세훈. 절차: tasks/classify.md (현재 스텁)"""
from __future__ import annotations


def select(table: str, **filters) -> list[dict]:
    raise NotImplementedError("tasks/classify.md")


def insert(table: str, row: dict) -> dict:
    raise NotImplementedError("tasks/classify.md")


def upsert(table: str, row: dict, on_conflict: str) -> dict:
    raise NotImplementedError("tasks/classify.md")


def update(table: str, match: dict, values: dict) -> None:
    raise NotImplementedError("tasks/classify.md")


def cp_key(name: str, method: str) -> str:
    raise NotImplementedError("tasks/classify.md")


def get_settings() -> dict:
    raise NotImplementedError("tasks/classify.md")
