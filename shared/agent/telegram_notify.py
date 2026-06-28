"""Notification Telegram à l'admin (ex. nouvelle inscription en attente).

Activé si TELEGRAM_BOT_TOKEN + TELEGRAM_ADMIN_CHAT_ID sont fournis. Transport HTTP
injectable → testable offline. Best-effort : une notif qui échoue ne casse jamais
le flux d'authentification (on avale l'erreur).
"""

from __future__ import annotations

import os
from typing import Awaitable, Callable, Optional

# Transport : (bot_token, chat_id, texte) -> None.
SendFn = Callable[[str, str, str], Awaitable[None]]


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, *, send: Optional[SendFn] = None) -> None:
        self._token = bot_token or ""
        self._chat = chat_id or ""
        self._send = send

    @property
    def configured(self) -> bool:
        return bool(self._token and self._chat)

    async def notify(self, text: str) -> bool:
        """Envoie un message à l'admin. Retourne True si envoyé, False sinon (silencieux)."""
        if not self.configured:
            return False
        send = self._send or _live_send()
        try:
            await send(self._token, self._chat, text)
            return True
        except Exception:
            return False


def _live_send() -> SendFn:  # pragma: no cover - live
    async def _send(token: str, chat_id: str, text: str) -> None:
        import aiohttp

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        async with aiohttp.ClientSession() as sess:
            async with sess.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()

    return _send


def build_telegram_notifier() -> Optional[TelegramNotifier]:
    """Construit le notificateur depuis l'environnement, ou None si non configuré."""
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.environ.get("TELEGRAM_ADMIN_CHAT_ID") or "").strip()
    if not token or not chat:
        return None
    return TelegramNotifier(token, chat)
