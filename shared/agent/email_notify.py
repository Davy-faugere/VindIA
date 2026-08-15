"""Notification par e-mail à l'administrateur (nouvelle inscription à valider).

Sans alerte, une inscription passe inaperçue et l'utilisateur attend indéfiniment son
autorisation. Ce module envoie un e-mail dès qu'un compte demande l'accès.

Repose sur `smtplib` (bibliothèque standard) : aucune dépendance ajoutée. L'envoi
réel est isolé derrière un `sender` injectable → testable hors ligne, comme le reste.

Activé si SMTP_HOST, SMTP_USER, SMTP_PASSWORD et VINDIA_ADMIN_EMAILS sont fournis.
Best-effort : un échec d'envoi ne bloque jamais l'authentification.
"""

from __future__ import annotations

import os
from email.message import EmailMessage
from typing import Awaitable, Callable, List, Optional

# Envoi : (destinataires, sujet, corps) -> None. Injectable pour les tests.
SendMail = Callable[[List[str], str, str], Awaitable[None]]


class EmailNotifier:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        sender_addr: str,
        recipients,
        *,
        use_tls: bool = True,
        send: Optional[SendMail] = None,
    ) -> None:
        self._host, self._port = host or "", int(port or 587)
        self._user, self._password = user or "", password or ""
        self._from = sender_addr or user or ""
        self._to = [r.strip() for r in (recipients or []) if r and r.strip()]
        self._use_tls = use_tls
        self._send = send

    @property
    def configured(self) -> bool:
        return bool(self._host and self._user and self._password and self._to)

    async def notify(self, subject: str, body: str) -> bool:
        """Envoie un e-mail. Retourne False sans lever si l'envoi échoue."""
        if not self.configured:
            return False
        send = self._send or self._live_send()
        try:
            await send(self._to, subject, body)
            return True
        except Exception as exc:  # noqa: BLE001 - une alerte ratée ne casse pas le login
            print(f"[VindIA] e-mail non envoyé : {exc}")
            return False

    def _live_send(self) -> SendMail:  # pragma: no cover - dépend du serveur SMTP
        host, port, user, pwd, sender, tls = (
            self._host, self._port, self._user, self._password, self._from, self._use_tls
        )

        async def _send(to: List[str], subject: str, body: str) -> None:
            import asyncio
            import smtplib

            def _blocking() -> None:
                msg = EmailMessage()
                msg["From"] = sender
                msg["To"] = ", ".join(to)
                msg["Subject"] = subject
                msg.set_content(body)
                # Port 465 = SSL implicite ; sinon STARTTLS (587, le cas courant).
                if port == 465:
                    with smtplib.SMTP_SSL(host, port, timeout=20) as s:
                        s.login(user, pwd)
                        s.send_message(msg)
                else:
                    with smtplib.SMTP(host, port, timeout=20) as s:
                        if tls:
                            s.starttls()
                        s.login(user, pwd)
                        s.send_message(msg)

            # smtplib est bloquant : on l'exécute hors de la boucle asyncio.
            await asyncio.get_running_loop().run_in_executor(None, _blocking)

        return _send


def build_email_notifier() -> Optional[EmailNotifier]:
    """Construit le notificateur depuis l'environnement, ou None si non configuré."""
    host = (os.environ.get("SMTP_HOST") or "").strip()
    user = (os.environ.get("SMTP_USER") or "").strip()
    pwd = (os.environ.get("SMTP_PASSWORD") or "").strip()
    recipients = [e.strip() for e in (os.environ.get("VINDIA_ADMIN_EMAILS") or "").split(",") if e.strip()]
    if not (host and user and pwd and recipients):
        return None
    return EmailNotifier(
        host,
        int(os.environ.get("SMTP_PORT") or 587),
        user,
        pwd,
        (os.environ.get("SMTP_FROM") or user).strip(),
        recipients,
        use_tls=(os.environ.get("SMTP_TLS", "1").strip() not in ("0", "false", "no")),
    )


def signup_message(email: str, member_id: str, public_url: str = "") -> tuple:
    """Sujet et corps de l'alerte « nouvelle inscription »."""
    subject = f"VindIA — nouvelle inscription à valider : {email or member_id}"
    lines = [
        "Une nouvelle personne vient de créer un compte sur VindIA.",
        "",
        f"  Adresse e-mail : {email or '(non renseignée)'}",
        f"  Identifiant    : {member_id}",
        "",
        "Ce compte est en attente : il n'a accès à rien tant que tu ne l'as pas validé.",
        "",
        "Pour l'autoriser ou le refuser : connecte-toi à VindIA avec ton compte "
        "administrateur, puis ouvre « Administration ».",
    ]
    if public_url:
        lines += ["", public_url]
    return subject, "\n".join(lines)
