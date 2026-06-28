"""Tests du notificateur Telegram — offline, send mocké."""

import asyncio
import unittest

from shared.agent.telegram_notify import TelegramNotifier


class TelegramTest(unittest.TestCase):
    def test_notify_sends_to_admin_chat(self):
        captured = {}

        async def send(token, chat, text):
            captured.update(token=token, chat=chat, text=text)

        n = TelegramNotifier("tok", "12345", send=send)
        self.assertTrue(n.configured)
        ok = asyncio.run(n.notify("nouvel utilisateur"))
        self.assertTrue(ok)
        self.assertEqual(captured, {"token": "tok", "chat": "12345", "text": "nouvel utilisateur"})

    def test_not_configured_is_silent(self):
        async def send(*a):  # pragma: no cover - ne doit pas être appelé
            raise AssertionError("pas d'envoi si non configuré")

        n = TelegramNotifier("", "", send=send)
        self.assertFalse(n.configured)
        self.assertFalse(asyncio.run(n.notify("x")))

    def test_send_error_swallowed(self):
        async def send(token, chat, text):
            raise RuntimeError("Telegram down")

        n = TelegramNotifier("tok", "chat", send=send)
        self.assertFalse(asyncio.run(n.notify("x")))  # pas d'exception propagée


if __name__ == "__main__":
    unittest.main()
