"""Tests OAuth Google — partie PURE (URL, scopes, extraction) + échanges mockés.

Aucun appel réseau : les transports http sont injectés. On prouve l'URL
d'autorisation (offline access, consent, scopes, state) et le mapping token→coffre.
"""

import asyncio
import unittest
from urllib.parse import parse_qs, urlparse

from shared.agent.oauth_google import (
    DEFAULT_SCOPES,
    GoogleOAuth,
    secrets_from_token_response,
)


def _oauth():
    return GoogleOAuth("cid.apps.googleusercontent.com", "secret", "https://vindia.example/oauth/google/callback")


class AuthUrlTest(unittest.TestCase):
    def test_build_auth_url_has_required_params(self):
        url = _oauth().build_auth_url("st4te-xyz")
        q = parse_qs(urlparse(url).query)
        self.assertEqual(q["client_id"][0], "cid.apps.googleusercontent.com")
        self.assertEqual(q["redirect_uri"][0], "https://vindia.example/oauth/google/callback")
        self.assertEqual(q["response_type"][0], "code")
        self.assertEqual(q["access_type"][0], "offline")   # → refresh_token
        self.assertEqual(q["prompt"][0], "consent")
        self.assertEqual(q["state"][0], "st4te-xyz")
        # scopes lecture seule présents
        self.assertIn("gmail.readonly", q["scope"][0])
        self.assertIn("calendar.readonly", q["scope"][0])
        self.assertIn("drive.readonly", q["scope"][0])

    def test_configured_flag(self):
        self.assertTrue(_oauth().configured)
        self.assertFalse(GoogleOAuth("", "", "").configured)


class ExchangeTest(unittest.TestCase):
    def test_exchange_code_posts_expected_payload(self):
        captured = {}

        async def fake_post(url, data):
            captured["url"] = url
            captured["data"] = data
            return {"access_token": "at", "refresh_token": "rt", "expires_in": 3599, "scope": "openid email"}

        token = asyncio.run(_oauth().exchange_code("auth-code-123", http=fake_post))
        self.assertEqual(captured["url"], "https://oauth2.googleapis.com/token")
        self.assertEqual(captured["data"]["code"], "auth-code-123")
        self.assertEqual(captured["data"]["grant_type"], "authorization_code")
        self.assertEqual(captured["data"]["client_secret"], "secret")
        self.assertEqual(token["refresh_token"], "rt")

    def test_fetch_userinfo_uses_bearer(self):
        captured = {}

        async def fake_get(url, access_token):
            captured["url"] = url
            captured["token"] = access_token
            return {"email": "user@gmail.com", "name": "User"}

        info = asyncio.run(_oauth().fetch_userinfo("the-access-token", http=fake_get))
        self.assertEqual(captured["url"], "https://www.googleapis.com/oauth2/v3/userinfo")
        self.assertEqual(captured["token"], "the-access-token")
        self.assertEqual(info["email"], "user@gmail.com")

    def test_refresh_posts_refresh_grant(self):
        captured = {}

        async def fake_post(url, data):
            captured["data"] = data
            return {"access_token": "new-at", "expires_in": 3599}

        out = asyncio.run(_oauth().refresh("rt", http=fake_post))
        self.assertEqual(captured["data"]["grant_type"], "refresh_token")
        self.assertEqual(captured["data"]["refresh_token"], "rt")
        self.assertEqual(out["access_token"], "new-at")


class SecretsMappingTest(unittest.TestCase):
    def test_secrets_from_token_response(self):
        s = secrets_from_token_response(
            {"access_token": "at", "refresh_token": "rt", "expires_in": 3599, "scope": "x"}
        )
        self.assertEqual(s["access_token"], "at")
        self.assertEqual(s["refresh_token"], "rt")
        self.assertEqual(s["expires_in"], 3599)
        self.assertEqual(s["token_type"], "Bearer")  # défaut

    def test_default_scopes_readonly(self):
        joined = " ".join(DEFAULT_SCOPES)
        self.assertNotIn(".modify", joined)
        self.assertNotIn(".send", joined)  # pas d'envoi de mail


if __name__ == "__main__":
    unittest.main()
