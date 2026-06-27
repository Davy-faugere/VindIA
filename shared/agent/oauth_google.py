"""Connecteur OAuth2 Google (Authorization Code flow) — identité + Gmail/Agenda/Drive.

Le flow donne, en un consentement, l'identité de l'utilisateur ET un
`refresh_token` pour appeler ses APIs Google. Les jetons obtenus sont chiffrés
dans le coffre par membre (cf. `vault.py`) — ils ne transitent jamais en clair
sur disque.

Découpage testable : la construction de l'URL d'autorisation est PURE (testée
offline) ; les échanges réseau (token, userinfo) passent par un `http` injectable
(aiohttp en prod, fake en test) — le module n'importe rien de tiers au chargement.

Sécurité : `access_type=offline` + `prompt=consent` pour obtenir un refresh_token ;
le `state` anti-CSRF est géré par l'appelant (server.py) et lie le flow au membre.
Scopes en LECTURE SEULE par défaut (gmail.readonly, calendar.readonly, drive.readonly).
"""

from __future__ import annotations

from typing import Awaitable, Callable, List, Optional, Sequence
from urllib.parse import urlencode

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

# Lecture seule par défaut : VindIA consulte, ne modifie pas les comptes.
DEFAULT_SCOPES = (
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
)

# Transports réseau injectables : (url, données) -> JSON.
#   POST form-urlencoded (échange de code) ; GET avec Bearer (userinfo).
HttpPost = Callable[[str, dict], Awaitable[dict]]
HttpGetAuth = Callable[[str, str], Awaitable[dict]]


class GoogleOAuth:
    """Configuration d'une app OAuth Google + opérations du flow."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        *,
        scopes: Sequence[str] = DEFAULT_SCOPES,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = list(scopes)

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)

    def build_auth_url(self, state: str) -> str:
        """URL d'autorisation Google vers laquelle rediriger l'utilisateur (pur)."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",      # → refresh_token
            "prompt": "consent",           # force le refresh_token même si déjà consenti
            "include_granted_scopes": "true",
            "state": state,
        }
        return f"{AUTH_ENDPOINT}?{urlencode(params)}"

    async def exchange_code(self, code: str, http: Optional[HttpPost] = None) -> dict:
        """Échange le code d'autorisation contre les jetons (token endpoint)."""
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        post = http or _live_post()
        return await post(TOKEN_ENDPOINT, data)

    async def fetch_userinfo(self, access_token: str, http: Optional[HttpGetAuth] = None) -> dict:
        """Récupère le profil (email, nom) avec l'access_token."""
        get = http or _live_get_auth()
        return await get(USERINFO_ENDPOINT, access_token)

    async def refresh(self, refresh_token: str, http: Optional[HttpPost] = None) -> dict:
        """Renouvelle l'access_token à partir du refresh_token (token endpoint)."""
        data = {
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
        }
        post = http or _live_post()
        return await post(TOKEN_ENDPOINT, data)


def _live_post() -> HttpPost:  # pragma: no cover - live
    async def _post(url: str, data: dict) -> dict:
        import aiohttp

        async with aiohttp.ClientSession() as sess:
            async with sess.post(url, data=data, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                resp.raise_for_status()
                return await resp.json()

    return _post


def _live_get_auth() -> HttpGetAuth:  # pragma: no cover - live
    async def _get(url: str, access_token: str) -> dict:
        import aiohttp

        headers = {"Authorization": f"Bearer {access_token}"}
        async with aiohttp.ClientSession(headers=headers) as sess:
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                resp.raise_for_status()
                return await resp.json()

    return _get


def secrets_from_token_response(token: dict) -> dict:
    """Extrait du retour token les secrets à chiffrer dans le coffre."""
    return {
        "access_token": token.get("access_token", ""),
        "refresh_token": token.get("refresh_token", ""),
        "expires_in": token.get("expires_in", 0),
        "token_type": token.get("token_type", "Bearer"),
        "scope": token.get("scope", ""),
    }
