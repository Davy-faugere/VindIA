"""Tests du coffre à credentials — 100 % offline, tmpdir, 0 dépendance.

Priorités sécurité : (1) le secret n'apparaît JAMAIS en clair sur le disque ;
(2) isolation stricte par membre ; (3) list_connections n'expose pas les secrets.
On injecte un chiffreur factice RÉVERSIBLE mais NON trivial (XOR+hex) → on peut
vérifier que le plaintext n'est pas présent dans le fichier écrit.
"""

import json
import tempfile
import unittest
from pathlib import Path

from shared.agent.vault import CredentialVault

ALICE = "00000001-0001-0001-0002-000000000001"
BOB = "00000001-0001-0001-0003-000000000001"


class _XorCrypto:
    """Chiffreur factice : XOR avec une clé fixe + hex. Réversible, non identité."""

    _KEY = 0x5A

    def encrypt(self, plaintext: str) -> str:
        return bytes(b ^ self._KEY for b in plaintext.encode("utf-8")).hex()

    def decrypt(self, token: str) -> str:
        return bytes(b ^ self._KEY for b in bytes.fromhex(token)).decode("utf-8")


def _vault(tmp):
    return CredentialVault(tmp, _XorCrypto(), clock=lambda: "2026-06-27T00:00:00+00:00")


class CryptoRoundtripTest(unittest.TestCase):
    def test_xor_crypto_is_reversible(self):
        c = _XorCrypto()
        self.assertEqual(c.decrypt(c.encrypt("ya29.secret-token")), "ya29.secret-token")


class VaultSecurityTest(unittest.TestCase):
    def test_secret_never_on_disk_in_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = _vault(tmp)
            v.store(ALICE, "google", {"refresh_token": "ya29.SUPER-SECRET"}, meta={"email": "a@b.com"})
            # Lecture brute du fichier : le secret ne doit PAS y être en clair.
            raw = list(Path(tmp).rglob("*.json"))[0].read_text()
            self.assertNotIn("SUPER-SECRET", raw)
            self.assertNotIn("ya29.SUPER-SECRET", raw)
            # …mais la meta non sensible, oui (affichable).
            self.assertIn("a@b.com", raw)

    def test_get_secrets_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = _vault(tmp)
            v.store(ALICE, "google", {"refresh_token": "tok", "scope": "gmail"})
            self.assertEqual(v.get_secrets(ALICE, "google"), {"refresh_token": "tok", "scope": "gmail"})

    def test_list_does_not_expose_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = _vault(tmp)
            v.store(ALICE, "google", {"refresh_token": "tok"}, meta={"email": "a@b.com"})
            conns = v.list_connections(ALICE)
            self.assertEqual(len(conns), 1)
            d = conns[0].as_dict()
            self.assertEqual(d["service"], "google")
            self.assertTrue(d["connected"])
            self.assertEqual(d["meta"], {"email": "a@b.com"})
            self.assertNotIn("secret", d)
            self.assertNotIn("refresh_token", json.dumps(d))


class VaultIsolationTest(unittest.TestCase):
    def test_members_partitioned(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = _vault(tmp)
            v.store(ALICE, "google", {"refresh_token": "alice-token"})
            self.assertEqual(v.list_connections(BOB), [])
            self.assertIsNone(v.get_secrets(BOB, "google"))
            self.assertFalse(v.is_connected(BOB, "google"))
            self.assertTrue(v.is_connected(ALICE, "google"))

    def test_invalid_member_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = _vault(tmp)
            for bad in ("../evil", "a/b", "..", "x" * 40):
                with self.subTest(bad=bad):
                    with self.assertRaises(ValueError):
                        v.store(bad, "google", {"t": "1"})

    def test_service_name_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = _vault(tmp)
            v.store(ALICE, "../../Gmail Account!", {"t": "1"})
            files = list((Path(tmp) / ALICE / "connections").glob("*.json"))
            self.assertEqual(len(files), 1)
            # Nom de fichier assaini, confiné sous le membre.
            self.assertTrue(str(files[0]).startswith(str(Path(tmp) / ALICE)))
            self.assertNotIn("..", files[0].name)


class VaultCrudTest(unittest.TestCase):
    def test_overwrite_reconnect(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = _vault(tmp)
            v.store(ALICE, "google", {"refresh_token": "old"})
            v.store(ALICE, "google", {"refresh_token": "new"})
            self.assertEqual(v.get_secrets(ALICE, "google"), {"refresh_token": "new"})
            self.assertEqual(len(v.list_connections(ALICE)), 1)

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            v = _vault(tmp)
            v.store(ALICE, "google", {"t": "1"})
            self.assertTrue(v.delete(ALICE, "google"))
            self.assertFalse(v.is_connected(ALICE, "google"))
            self.assertFalse(v.delete(ALICE, "google"))  # idempotent

    def test_get_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(_vault(tmp).get_secrets(ALICE, "nope"))
            self.assertIsNone(_vault(tmp).get_meta(ALICE, "nope"))


if __name__ == "__main__":
    unittest.main()
