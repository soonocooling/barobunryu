"""회귀 테스트: 실제 HTTP 요청은 항상 차단한다."""
import copy
import os
import unittest
from unittest.mock import Mock, patch

import watch


class WatchRegressions(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("requests.sessions.Session.request",
                                side_effect=AssertionError("network forbidden")))
        self.enterContext(patch.dict(os.environ, {"CP_SALT": "offline-salt"}))

    def test_original_self_transfer_before_insert(self):
        fake = Mock()
        fake.cp_key = watch.db.cp_key
        fake.select.return_value = []
        fake.upsert.side_effect = lambda table, row, **kw: row
        fake.insert.side_effect = lambda table, row: {"id": 1, **row}
        fake.load_rules.return_value = {}
        fake.load_cache.return_value = {}
        fake.get_settings.return_value = {}
        with patch.object(watch, "db", fake):
            row = watch.create_txn({"counterparty": "내 통장", "method": "transfer",
                                    "direction": "out", "amount": 5000,
                                    "ts": "2026-11-03T12:00:00+09:00"})
        self.assertEqual(row["category"], "self")
        self.assertTrue(row["cp_key"].startswith("p:"))
        self.assertNotIn("내 통장", str(fake.insert.call_args))
        self.assertNotIn("counterparty", row)

    def test_repeat_answer_preserves_partial_and_completed_splits(self):
        for remaining in (15000, 0):
            with self.subTest(remaining=remaining):
                txn = {"id": 1, "amount": 40000, "direction": "out", "cp_key": "m:test",
                       "category": "food", "status": "confirmed"}
                split = {"id": 2, "n": 4, "remaining": remaining,
                         "receivable": 30000, "status": "done" if not remaining else "open"}
                fake = Mock()
                fake.select.side_effect = lambda table, **kw: [txn] if table == "transactions" else [split]
                with patch.object(watch, "db", fake), patch.object(watch.classify, "learn") as learn:
                    watch.apply_answer(copy.deepcopy(txn), {"split_n": 4})
                    watch.apply_answer(copy.deepcopy(txn), {"split_n": 5})
                fake.upsert.assert_not_called()
                fake.update.assert_not_called()
                learn.assert_not_called()

    def test_explicit_new_unsettled_split(self):
        fake = Mock()
        txn = {"id": 1, "amount": 40000, "direction": "out", "category": "food", "status": "confirmed"}
        split = {"id": 2, "n": 4, "receivable": 30000, "remaining": 30000}
        fake.select.side_effect = lambda table, **kw: {"transactions": [txn], "splits": [split], "settlements": []}[table]
        fake.upsert.side_effect = lambda table, row, conflict: row
        with patch.object(watch, "db", fake):
            watch.apply_answer(txn, {"split_n": 2, "new_split": True})
        self.assertEqual(fake.upsert.call_args.args[1]["remaining"], 20000)

    def test_failure_is_retryable_and_next_row_runs(self):
        fake = Mock()
        fake.cp_key = watch.db.cp_key
        rows = [{"id": i, "cp_key": key, "method": "card", "direction": "out", "amount": 1000,
                 "category": None, "cp_label": "사용자 별칭"}
                for i, key in [(1, "m:bad"), (2, "m:good")]]
        fake.select.return_value = rows
        fake.load_rules.return_value = {}
        fake.load_cache.return_value = {}
        with patch.object(watch, "db", fake), patch.object(watch.classify, "classify",
                side_effect=[RuntimeError("fail"), ("food", 0.8, None),
                             ("food", 0.8, None), ("food", 0.8, None)]) as classify:
            watch.classify_new({})
            self.assertEqual(fake.update.call_count, 1)
            self.assertEqual(fake.update.call_args.args[1], {"id": 2})
            self.assertEqual(classify.call_args.args[0]["counterparty"], "good")
            self.assertIsNone(rows[0]["category"])
            watch.classify_new({})
            self.assertEqual(fake.update.call_count, 3)

    def test_hashed_transfer_without_original_is_not_guessed(self):
        fake = Mock()
        fake.load_rules.return_value = {}
        fake.load_cache.return_value = {}
        fake.select.return_value = [{"id": 1, "cp_key": "p:unknown", "method": "transfer",
                                     "cp_label": "상대 #1", "category": None}]
        with patch.object(watch, "db", fake), patch.object(watch.classify, "classify") as classify:
            watch.classify_new({})
        fake.update.assert_not_called()
        classify.assert_not_called()

    def test_new_split_cannot_reset_settled_balance(self):
        fake = Mock()
        txn = {"id": 1, "direction": "out", "category": "food"}
        fake.select.side_effect = [[txn], [{"id": 2, "remaining": 10000, "receivable": 30000}]]
        with patch.object(watch, "db", fake), self.assertRaises(ValueError):
            watch.apply_answer(txn, {"split_n": 2, "new_split": True})
        fake.upsert.assert_not_called()
        fake.update.assert_not_called()

    def test_cache_failure_does_not_mark_transaction_successful(self):
        fake = Mock()
        fake.cp_key = watch.db.cp_key
        fake.load_rules.return_value = {}
        fake.load_cache.return_value = {}
        fake.select.return_value = [{"id": i, "cp_key": "m:test", "method": "card",
                                     "direction": "out", "amount": 1000} for i in (1, 2)]
        fake.upsert.side_effect = RuntimeError("cache write failed")
        with patch.object(watch, "db", fake), patch.object(watch.classify, "classify",
                side_effect=[("food", 0.8, {"name": "test"}), ("food", 0.8, None)]):
            watch.classify_new({})
        fake.update.assert_called_once()
        self.assertEqual(fake.update.call_args.args[1], {"id": 2})
