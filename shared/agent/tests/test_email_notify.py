"""Tests de l'alerte e-mail — hors ligne, envoi mocké, aucun serveur SMTP requis."""

import asyncio
import unittest

from shared.agent.email_notify import EmailNotifier, signup_message


def _notifier(send, **kw):
    return EmailNotifier("smtp.test", 587, "user@test", "secret",
                         "vindia@test", ["admin@test"], send=send, **kw)


class EmailNotifierTest(unittest.TestCase):
    def test_sends_to_configured_recipients(self):
        seen = {}

        async def send(to, subject, body):
            seen.update(to=to, subject=subject, body=body)

        ok = asyncio.run(_notifier(send).notify("Sujet", "Corps"))
        self.assertTrue(ok)
        self.assertEqual(seen["to"], ["admin@test"])
        self.assertEqual(seen["subject"], "Sujet")

    def test_not_configured_is_silent(self):
        async def send(*a):  # pragma: no cover - ne doit pas être appelé
            raise AssertionError("aucun envoi si non configuré")

        n = EmailNotifier("", 587, "", "", "", [], send=send)
        self.assertFalse(n.configured)
        self.assertFalse(asyncio.run(n.notify("s", "b")))

    def test_send_failure_never_raises(self):
        async def send(to, subject, body):
            raise RuntimeError("SMTP injoignable")

        # Une alerte ratée ne doit jamais casser l'authentification.
        self.assertFalse(asyncio.run(_notifier(send).notify("s", "b")))

    def test_missing_password_is_not_configured(self):
        n = EmailNotifier("smtp.test", 587, "user", "", "from@test", ["a@test"])
        self.assertFalse(n.configured)


class SignupMessageTest(unittest.TestCase):
    def test_contains_email_and_next_step(self):
        subject, body = signup_message("cyril@example.com", "uuid-1")
        self.assertIn("cyril@example.com", subject)
        self.assertIn("cyril@example.com", body)
        self.assertIn("Administration", body)      # dit où aller valider
        self.assertIn("en attente", body)          # rassure : aucun accès entre-temps

    def test_handles_missing_email(self):
        _, body = signup_message("", "uuid-2")
        self.assertIn("uuid-2", body)
        self.assertIn("non renseignée", body)

    def test_includes_url_when_given(self):
        _, body = signup_message("a@b.c", "id", "https://vindia.example")
        self.assertIn("https://vindia.example", body)


if __name__ == "__main__":
    unittest.main()


class DecisionTest(unittest.TestCase):
    """Message envoyé À LA PERSONNE après validation ou refus."""

    def test_validation_dit_quoi_faire(self):
        from shared.agent.email_notify import decision_message
        sujet, corps = decision_message(True, "https://vindia.example")
        self.assertIn("validé", corps)
        self.assertIn("connecter", corps)          # l'action à faire maintenant
        self.assertIn("https://vindia.example", corps)

    def test_refus_est_sobre_et_rassurant(self):
        from shared.agent.email_notify import decision_message
        sujet, corps = decision_message(False)
        self.assertIn("pas été retenue", corps)
        self.assertNotIn("validé", corps)
        self.assertIn("Aucune donnée", corps)      # ce qu'on fait de ses données

    def test_envoi_a_un_destinataire_precis(self):
        seen = {}

        async def send(to, subject, body):
            seen.update(to=to)

        # Sans ce chemin, le message de validation partirait à l'ADMIN, pas à la
        # personne concernée.
        asyncio.run(_notifier(send).notify("s", "b", to=["nouveau@exemple.fr"]))
        self.assertEqual(seen["to"], ["nouveau@exemple.fr"])

    def test_destinataire_vide_n_envoie_rien(self):
        async def send(*a):  # pragma: no cover
            raise AssertionError("aucun envoi sans destinataire")

        self.assertFalse(asyncio.run(_notifier(send).notify("s", "b", to=[])))
