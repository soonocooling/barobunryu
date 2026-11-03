import unittest
from unittest.mock import Mock, patch

import parse
import watch


class MessageFlow(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("requests.sessions.Session.request", side_effect=AssertionError("network")))
        self.enterContext(patch.dict("os.environ", {"TELEGRAM_CHAT_ID": "123"}))
        self.bot = self.enterContext(patch.object(watch, "bot"))

    def message(self, text, reply=None):
        msg = {"chat": {"id": 123}, "message_id": 20, "text": text}
        if reply:
            msg["reply_to_message"] = {"message_id": reply}
        return {"message": msg}

    def test_new_message_keeps_original(self):
        with patch.object(watch, "create_txn") as create:
            watch.handle_update(self.message("50000 내 통장 이체"))
        txn = create.call_args.args[0]
        self.assertEqual(txn["counterparty"], "내 통장")
        self.assertEqual(txn["method"], "transfer")

    def test_reply_reaches_confirmation(self):
        txn = {"id": 1, "cp_key": "p:existing", "category": "transfer",
               "direction": "out", "status": "pending", "tg_message_id": 9}
        fake = Mock()
        fake.select.return_value = [txn]
        with patch.object(watch, "db", fake), patch.object(watch, "confirm_category") as confirm:
            watch.handle_update(self.message("월세", reply=9))
        confirm.assert_called_once_with(txn, "living")

    def test_callback_reaches_confirmation(self):
        txn = {"id": 1, "cp_key": "m:test", "category": "etc", "direction": "out"}
        fake = Mock()
        fake.select.return_value = [txn]
        with patch.object(watch, "db", fake), patch.object(watch, "confirm_category") as confirm:
            watch.handle_update({"callback_query": {"id": "cb", "data": "c:1:food",
                               "message": {"chat": {"id": 123}, "message_id": 9}}})
        confirm.assert_called_once_with(txn, "food")
        self.bot.answer_callback.assert_called_once_with("cb")

    def test_other_chat_ignored(self):
        update = self.message("스벅 6500")
        update["message"]["chat"]["id"] = 999
        with patch.object(watch, "create_txn") as create:
            watch.handle_update(update)
        create.assert_not_called()

    def test_no_undocumented_restart_command(self):
        with patch.object(watch.db, "select", return_value=[{"id": 1}]), patch.object(watch, "apply_answer") as apply:
            watch.handle_update(self.message("/split new 4", reply=9))
        apply.assert_not_called()

    def test_documented_parser_examples(self):
        for text, amount in [("스벅 6500", 6500), ("6,500원 스벅", 6500),
                             ("3만 고기집", 30000), ("1만2천 고기집", 12000)]:
            self.assertEqual(parse.parse_manual(text)["amount"], amount)
        self.assertIsNone(parse.parse_manual("100 200 가게"))
        self.assertEqual(parse.parse_answer("치킨 4명")["split_n"], 4)
        self.assertEqual(parse.parse_answer("월세")["category"], "living")
        self.assertEqual(parse.parse_answer("내 몫 15,000")["my_share"], 15000)
        self.assertTrue(parse.parse_answer("몰라")["skip"])
