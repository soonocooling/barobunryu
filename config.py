"""공용 설정. 담당: 권순오(setup). 모든 모듈이 여기서 시간대·카테고리·환경변수를 가져온다."""
from __future__ import annotations

import json
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
KST = ZoneInfo("Asia/Seoul")


def load_env() -> None:
    """로컬 실행 시 .env.local을 읽는다. Actions에서는 Secrets가 이미 환경변수라 아무 일도 안 한다."""
    path = ROOT / ".env.local"
    if not path.exists():
        return
    try:
        from dotenv import load_dotenv  # 개발 의존성
        load_dotenv(path, override=False)
    except ImportError:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"환경변수 {name}가 비어 있다. .env.local 또는 GitHub Secrets를 확인할 것")
    return value


def now() -> datetime:
    return datetime.now(KST)


@lru_cache(maxsize=1)
def keywords() -> dict:
    return json.loads((ROOT / "keywords.json").read_text(encoding="utf-8"))


def categories() -> dict:
    """{code: {"label", "kakao_codes", "keywords", "ask"?}}"""
    return keywords()["categories"]


def label(code: str | None) -> str:
    if not code:
        return "미분류"
    return categories().get(code, {}).get("label", code)
