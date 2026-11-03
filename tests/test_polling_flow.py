import os
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import bot
import watch
from config import KST


class PollingFlow(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("requests.sessions.Session.request", side_effect=AssertionError("network forbidden")))

    def test_get_updates_request_is_mocked(self):
        response = Mock()
        response.json.return_value = {"ok": True, "result": [{"update_id": 4}]}
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake-test-token"}), patch.object(bot.requests, "get", return_value=response) as get:
            self.assertEqual(bot.get_updates(3), [{"update_id": 4}])
        self.assertEqual(get.call_args.kwargs["params"]["offset"], 3)
        self.assertEqual(get.call_args.kwargs["params"]["timeout"], 0)
        self.assertEqual(get.call_args.kwargs["timeout"], 10)

    def test_missing_test_credentials_blocks_all_calls(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(watch, "load_env"), patch.object(watch.db, "get_settings") as settings, patch.object(watch.bot, "get_updates") as updates:
            with self.assertRaisesRegex(RuntimeError, "TEST_TELEGRAM_BOT_TOKEN"):
                watch.main()
        settings.assert_not_called()
        updates.assert_not_called()

    def test_main_continues_and_saves_offset(self):
        state = {"tg_offset": 0, "asked_today": {"date": None, "count": 0}, "last_digest_date": None}
        self.enterContext(patch.dict(os.environ, {"TEST_TELEGRAM_BOT_TOKEN": "fake", "TEST_TELEGRAM_CHAT_ID": "123"}))
        self.enterContext(patch.object(watch, "STATE_FILE"))
        self.enterContext(patch.object(watch, "load_env"))
        self.enterContext(patch.object(watch, "load_state", return_value=state))
        save = self.enterContext(patch.object(watch, "save_state"))
        self.enterContext(patch.object(watch.db, "get_settings", return_value={}))
        self.enterContext(patch.object(watch.bot, "get_updates", return_value=[{"update_id": 1}, {"update_id": 2}]))
        handle = self.enterContext(patch.object(watch, "handle_update", side_effect=[ValueError("hidden"), None]))
        for name in ("process_inbox", "classify_new", "ask_pending", "digest"):
            self.enterContext(patch.object(watch, name))
        watch.main()
        self.assertEqual(handle.call_count, 2)
        self.assertEqual(state["tg_offset"], 3)
        save.assert_called_once_with(state)

    def test_question_saved_and_not_repeated(self):
        txn = {"id": 1, "method": "card", "direction": "out", "category": "food",
               "cp_label": "가게", "amount": 46000, "ts": "2026-11-03T12:00:00+09:00"}
        fake = Mock()
        fake.select.side_effect = [[txn], []]
        state = {"asked_today": {"count": 0}}
        t = datetime(2026, 11, 3, 12, tzinfo=KST)
        with patch.object(watch, "db", fake), patch.object(watch.bot, "send", return_value=99) as send:
            watch.ask_pending({}, state, t)
            watch.ask_pending({}, state, t)
        send.assert_called_once()
        buttons = send.call_args.args[1]
        self.assertIn(("식비", "c:1:food"), buttons[0])
        self.assertEqual(fake.update.call_args.args[2]["tg_message_id"], 99)
        self.assertEqual(state["asked_today"]["count"], 1)

    def test_unknown_push_is_preserved(self):
        fake = Mock()
        fake.select.return_value = [{"id": 1, "raw_text": "unknown sample"}]
        with patch.object(watch, "db", fake), patch.object(watch, "create_txn") as create:
            watch.process_inbox()
        create.assert_not_called()
        fake.update.assert_not_called()
