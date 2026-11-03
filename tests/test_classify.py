"""네트워크를 차단한 분류·학습·카카오 테스트. unittest와 pytest 모두 지원."""
import importlib
import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

import requests

import classify
import db
import kakao


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.network = self.enterContext(patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("실제 네트워크 요청 금지")))
        self.enterContext(patch.dict(os.environ, {}, clear=True))

    def test_import_without_keys_or_network(self):
        importlib.reload(kakao)
        importlib.reload(classify)
        self.network.assert_not_called()

    def test_missing_keys(self):
        with self.assertRaisesRegex(RuntimeError, "KAKAO_REST_KEY"):
            kakao.kakao_lookup("테스트")
        with self.assertRaisesRegex(RuntimeError, "CP_SALT"):
            classify.classify(self.txn("상대", method="transfer"), {}, {})
        with self.assertRaisesRegex(RuntimeError, "SUPABASE_URL"):
            classify.learn("m:test", "food")
        self.network.assert_not_called()

    @staticmethod
    def txn(name, method="card", direction="out"):
        return {"counterparty": name, "method": method, "direction": direction}

    def test_local_classification_and_priority(self):
        self.enterContext(patch.dict(os.environ, {"CP_SALT": "unit-test-salt"}))
        lookup = self.enterContext(patch.object(kakao, "kakao_lookup"))
        cases = [
            (self.txn("스벅"), {"m:스벅": "gift"}, {}, ("gift", 0.95)),
            (self.txn("내 통장", "transfer", "in"), {}, {}, ("self", 0.9)),
            (self.txn("상대", "transfer", "in"), {}, {}, ("income", 0.5)),
            (self.txn("치킨", "transfer"), {}, {}, ("transfer", 0.3)),
            (self.txn("스벅"), {}, {}, ("cafe", 0.8)),
            (self.txn("교촌치킨 신촌점"), {}, {}, ("food", 0.8)),
            (self.txn("쿠팡이츠"), {}, {}, ("food", 0.8)),
            (self.txn("B H C"), {}, {}, ("food", 0.8)),
            (self.txn("식비"), {}, {}, ("food", 0.8)),
            (self.txn("스벅"), {}, {"스벅": {"category": "gift", "confidence": 0.9}}, ("gift", 0.9)),
        ]
        for txn, rules, cache, expected in cases:
            with self.subTest(name=txn["counterparty"], expected=expected):
                result = classify.classify(txn, rules, cache)
                self.assertEqual(result[:2], expected)
        lookup.assert_not_called()
        row = classify.classify(self.txn("스 벅"), {}, {})[2]
        self.assertEqual(row, {"name": "스벅", "kakao_code": None,
                              "kakao_name": None, "category": "cafe", "confidence": 0.8})

    def test_kakao_classification(self):
        for place, expected in [({"code": "FD6", "name": "음식점"}, ("food", 0.85)),
                                ({"code": "CE7", "name": "카페"}, ("cafe", 0.85)),
                                ({"code": None, "name": "미상"}, ("etc", 0.5)),
                                (None, ("etc", 0.2))]:
            with self.subTest(place=place), patch.object(kakao, "kakao_lookup", return_value=place) as lookup:
                result = classify.classify(self.txn("미등록장소"), {}, {})
                self.assertEqual(result[:2], expected)
                lookup.assert_called_once_with("미등록장소")
                if place is None:
                    self.assertIsNone(result[2])
                else:
                    self.assertEqual(result[2]["kakao_code"], place["code"])

    def test_learning(self):
        select = self.enterContext(patch.object(db, "select", return_value=[]))
        insert = self.enterContext(patch.object(db, "insert"))
        update = self.enterContext(patch.object(db, "update"))
        classify.learn("m:test", "food")
        select.assert_called_once_with("rules", cp_key="m:test")
        insert.assert_called_once_with("rules", {"cp_key": "m:test", "category": "food", "hits": 1, "active": False})
        for previous, hits, expected_hits, active in [("food", 1, 2, True), ("food", 2, 3, True), ("cafe", 3, 1, False)]:
            select.return_value = [{"category": previous, "hits": hits}]
            classify.learn("m:test", "food")
            update.assert_called_with("rules", {"cp_key": "m:test"}, {"category": "food", "hits": expected_hits, "active": active})
        select.reset_mock()
        for category in ("etc", "transfer", "income", "settlement"):
            classify.learn("m:test", category)
        with self.assertRaises(ValueError):
            classify.learn("m:test", "invalid")
        select.assert_not_called()

    def test_kakao_request_and_empty_result(self):
        self.enterContext(patch.dict(os.environ, {"KAKAO_REST_KEY": "unit-test-key"}))
        response = Mock()
        response.json.return_value = {"documents": [{"category_group_code": "FD6", "category_name": "음식점"}]}
        with patch.object(kakao.requests, "get", return_value=response) as get:
            self.assertEqual(kakao.kakao_lookup("테스트"), {"code": "FD6", "name": "음식점"})
            get.assert_called_once_with(kakao.URL, params={"query": "테스트", "size": 1},
                                        headers={"Authorization": "KakaoAK unit-test-key"}, timeout=5)
            response.json.return_value = {"documents": []}
            self.assertIsNone(kakao.kakao_lookup("테스트"))
            response.json.return_value = {"documents": [{}]}
            self.assertEqual(kakao.kakao_lookup("테스트"), {"code": None, "name": ""})

    def test_kakao_failures_hide_details(self):
        self.enterContext(patch.dict(os.environ, {"KAKAO_REST_KEY": "unit-test-key"}))
        for error in (requests.Timeout("unit-test-key"), requests.HTTPError("unit-test-key"), ValueError("unit-test-key")):
            with patch.object(kakao.requests, "get", side_effect=error), redirect_stdout(io.StringIO()) as output:
                self.assertIsNone(kakao.kakao_lookup("테스트"))
                self.assertNotIn("unit-test-key", output.getvalue())
        for data in ({}, [], {"documents": [None]}, {"documents": [{"category_group_code": [] , "category_name": 1}]}):
            response = Mock()
            response.json.return_value = data
            with patch.object(kakao.requests, "get", return_value=response), redirect_stdout(io.StringIO()):
                self.assertIsNone(kakao.kakao_lookup("테스트"))


if __name__ == "__main__":
    unittest.main()
