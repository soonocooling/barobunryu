"""카카오 로컬 키워드 검색. 담당: 박세훈. 절차: tasks/classify.md."""
from __future__ import annotations

import requests

from config import env

URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
TIMEOUT = 5


def kakao_lookup(name: str) -> dict | None:
    """가맹점명 → {code, name}. 검색 실패/0건은 None, 키 누락은 RuntimeError.

    환경변수는 이 함수를 호출할 때만 읽고 요청한다. 응답 본문과 키는 출력하지 않는다.
    """
    key = env("KAKAO_REST_KEY")
    try:
        response = requests.get(URL, params={"query": name, "size": 1},
                                headers={"Authorization": f"KakaoAK {key}"},
                                timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("documents"), list):
            raise ValueError("Invalid documents")
        documents = data["documents"]
        if not documents:
            return None
        doc = documents[0]
        if not isinstance(doc, dict):
            raise ValueError("Invalid document")
        code = doc.get("category_group_code") or None
        category_name = doc.get("category_name", "")
        if (code is not None and not isinstance(code, str)) or not isinstance(category_name, str):
            raise ValueError("Invalid category")
        return {"code": code, "name": category_name}
    except (requests.RequestException, ValueError):
        print("카카오 장소 검색 실패. 연결 상태와 API 설정을 확인하세요.")
        return None
