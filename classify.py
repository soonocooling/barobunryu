"""분류 파이프라인. 담당: 박세훈. 절차: tasks/classify.md (현재 스텁)"""
from __future__ import annotations


def classify(txn: dict, rules: dict, cache: dict) -> tuple[str, float, dict | None]:
    """(category, confidence, 캐시에 새로 넣을 행 또는 None). 순서: rules → cache → kakao → keywords → etc"""
    return ("etc", 0.2, None)  # TODO(tasks/classify.md)


def learn(cp_key: str, category: str) -> None:
    """사용자가 확정한 분류로 rules를 갱신한다 (F-07)."""
    return None  # TODO(tasks/classify.md)
