"""Tests de l'auth Supabase — offline, transport HTTP mocké, 0 réseau."""

import asyncio
import unittest

from shared.agent.supabase_auth import SupabaseAuth, bearer_token

URL = "https://proj.supabase.co"
ANON = "anon-key"
ADMINS = ["faugredavy@gmail.com"]


def _auth(http, **kw):
    # Horloge contrôlable pour tester le cache.
    return SupabaseAuth(URL, ANON, ADMINS, http=http, **kw)


class BearerTest(unittest.TestCase):
    def test_extracts_token(self):
        self.assertEqual(bearer_token("Bearer abc.def.ghi"), "abc.def.ghi")
        self.assertEqual(bearer_token("bearer xyz"), "xyz")  # tolérant à la casse

    def test_rejects_non_bearer(self):
        self.assertEqual(bearer_token(""), "")
        self.assertEqual(bearer_token("Basic abc"), "")
        self.assertEqual(bearer_token("abc"), "")


class VerifyTest(unittest.TestCase):
    def test_valid_token_returns_identity(self):
        async def http(url, headers):
            self.assertTrue(url.endswith("/auth/v1/user"))
            self.assertEqual(headers["Authorization"], "Bearer good")
            self.assertEqual(headers["apikey"], ANON)
            return 200, {"id": "uuid-123", "email": "Someone@Example.com"}

        ident = asyncio.run(_auth(http).verify("good"))
        self.assertEqual(ident["member_id"], "uuid-123")
        self.assertEqual(ident["email"], "someone@example.com")  # normalisé minuscule
        self.assertFalse(ident["admin"])

    def test_admin_email_flagged(self):
        async def http(url, headers):
            return 200, {"id": "uuid-davy", "email": "faugredavy@gmail.com"}

        ident = asyncio.run(_auth(http).verify("tok"))
        self.assertTrue(ident["admin"])

    def test_invalid_token_returns_none(self):
        async def http(url, headers):
            return 401, {"error": "invalid"}

        self.assertIsNone(asyncio.run(_auth(http).verify("bad")))

    def test_empty_token_short_circuits(self):
        async def http(url, headers):  # pragma: no cover - ne doit pas être appelé
            raise AssertionError("pas d'appel réseau pour un jeton vide")

        self.assertIsNone(asyncio.run(_auth(http).verify("")))

    def test_network_error_returns_none(self):
        async def http(url, headers):
            raise RuntimeError("réseau coupé")

        self.assertIsNone(asyncio.run(_auth(http).verify("tok")))

    def test_cache_avoids_second_network_call(self):
        calls = {"n": 0}
        t = {"now": 1000.0}

        async def http(url, headers):
            calls["n"] += 1
            return 200, {"id": "u", "email": "a@b.com"}

        auth = _auth(http, cache_ttl=300, clock=lambda: t["now"])
        asyncio.run(auth.verify("tok"))
        asyncio.run(auth.verify("tok"))  # dans le TTL → pas de 2e appel
        self.assertEqual(calls["n"], 1)
        # Au-delà du TTL → re-validation
        t["now"] = 1000.0 + 301
        asyncio.run(auth.verify("tok"))
        self.assertEqual(calls["n"], 2)

    def test_configured_flag(self):
        self.assertTrue(_auth(None).configured)
        self.assertFalse(SupabaseAuth("", "", []).configured)


if __name__ == "__main__":
    unittest.main()
