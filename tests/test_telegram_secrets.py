"""실제 자격 증명이나 네트워크 없이 설정과 오류 출력 경계를 검증한다."""
import traceback
import unittest
from unittest.mock import Mock, patch

import requests

import bot
import config


class TelegramSecretsTests(unittest.TestCase):
    def test_send_reads_environment(self):
        response = Mock()
        response.json.return_value = {"ok": True, "result": {"message_id": 1}}
        with patch.dict("os.environ", {
            "TELEGRAM_BOT_TOKEN": "test-token-placeholder",
            "TELEGRAM_CHAT_ID": "test-chat-placeholder",
        }, clear=True), patch.object(bot.requests, "post", return_value=response) as post:
            self.assertEqual(bot.send("test"), 1)
            args, kwargs = post.call_args
            self.assertIn("test-token-placeholder", args[0])
            self.assertEqual(kwargs["json"]["chat_id"], "test-chat-placeholder")

    def test_errors_do_not_expose_request_details(self):
        for error in (requests.ConnectionError, requests.HTTPError, ValueError):
            with self.subTest(error=error), patch.dict("os.environ", {
                "TELEGRAM_BOT_TOKEN": "test-token-placeholder",
                "TELEGRAM_CHAT_ID": "test-chat-placeholder",
            }), patch.object(bot.requests, "post", side_effect=error(
                "test-token-placeholder test-chat-placeholder"
            )):
                try:
                    bot.send("test")
                except RuntimeError:
                    output = traceback.format_exc()
                else:
                    self.fail("Expected a sanitized error")
                self.assertNotIn("test-token-placeholder", output)
                self.assertNotIn("test-chat-placeholder", output)

    def test_missing_secret_only_reports_name(self):
        for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            with self.subTest(name=name), patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(RuntimeError, name):
                    config.env(name)

    def test_local_file_optional_and_environment_wins(self):
        with patch.object(config, "ROOT") as root:
            (root / ".env.local").exists.return_value = False
            config.load_env()
        with patch.dict("os.environ", {"TELEGRAM_CHAT_ID": "test-chat-placeholder"}):
            self.assertEqual(config.env("TELEGRAM_CHAT_ID"), "test-chat-placeholder")
