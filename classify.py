"""분류 파이프라인. 담당: 박세훈. 절차: tasks/classify.md."""
from __future__ import annotations

import re

import config
import db
import kakao


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _match_length(name: str, category: dict) -> int:
    """라벨과 키워드 중 포함된 가장 긴 문자열의 길이. 없으면 0."""
    words = [category["label"], *category.get("keywords", [])]
    return max((len(word) for value in words
                if (word := _normalize(value)) and word in name), default=0)


def _cache_row(name: str, category: str, confidence: float, place: dict | None = None) -> dict:
    place = place or {}
    return {"name": name, "kakao_code": place.get("code"),
            "kakao_name": place.get("name"), "category": category,
            "confidence": confidence}


def classify(txn: dict, rules: dict, cache: dict) -> tuple[str, float, dict | None]:
    """Txn(counterparty/method/direction), 규칙, 캐시 → (분류, 신뢰도, 새 캐시 행).

    규칙 → 계좌 이동/입금/이체 → 캐시 → 키워드 → 카카오 → 기타 순서.
    DB 저장은 하지 않는다. 새 캐시 행은 호출자가 merchant_cache에 upsert한다.
    이체 해시에 CP_SALT가 필요하고, 카카오까지 진행할 때만 API 키가 필요하다.
    """
    name = txn["counterparty"]
    key = db.cp_key(name, txn["method"])
    norm = _normalize(name)
    if key in rules:
        return rules[key], 0.95, None

    categories = config.categories()
    if _match_length(norm, categories["self"]):
        return "self", 0.9, None
    if txn["direction"] == "in":
        return "income", 0.5, None
    if txn["method"] == "transfer":
        return "transfer", 0.3, None
    if norm in cache:
        row = cache[norm]
        return row["category"], row["confidence"], None

    best_category = None
    best_length = 0
    for code, category in categories.items():
        if category.get("ask", True) is False:
            continue
        length = _match_length(norm, category)
        if length > best_length:
            best_category, best_length = code, length
    if best_category is not None:
        return best_category, 0.8, _cache_row(norm, best_category, 0.8)

    place = kakao.kakao_lookup(name)
    if place is not None:
        mapping = {kakao_code: code for code, category in categories.items()
                   for kakao_code in category.get("kakao_codes", [])}
        category = mapping.get(place["code"], "etc")
        confidence = 0.85 if place["code"] in mapping else 0.5
        return category, confidence, _cache_row(norm, category, confidence, place)
    return "etc", 0.2, None


def learn(cp_key: str, category: str) -> None:
    """확정 분류를 rules에 학습한다. 같은 분류 2회부터 active=True.

    cp_key는 counterparties에 이미 존재해야 한다(FK). 호출 시에만 DB에 접근한다.
    분류가 바뀌면 hits=1로 초기화한다. 기타/이체/수입/정산은 학습하지 않는다.
    """
    if category in ("etc", "transfer", "income", "settlement"):
        return
    if category not in config.categories():
        raise ValueError("알 수 없는 카테고리입니다. keywords.json의 코드를 사용하세요.")
    rows = db.select("rules", cp_key=cp_key)
    if not rows:
        db.insert("rules", {"cp_key": cp_key, "category": category,
                            "hits": 1, "active": False})
        return
    row = rows[0]
    hits = row["hits"] + 1 if row["category"] == category else 1
    db.update("rules", {"cp_key": cp_key},
              {"category": category, "hits": hits, "active": hits >= 2})
