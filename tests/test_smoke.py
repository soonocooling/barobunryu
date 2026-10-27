"""뼈대가 import되는지만 본다. 각 파트가 자기 테스트 파일을 추가한다."""
import importlib

import config


def test_modules_import():
    for name in ["config", "parse", "kakao", "classify", "db", "bot", "watch"]:
        importlib.import_module(name)


def test_categories_have_labels():
    cats = config.categories()
    for code in ["food", "cafe", "transfer", "etc", "self", "income", "settlement"]:
        assert cats[code]["label"]
