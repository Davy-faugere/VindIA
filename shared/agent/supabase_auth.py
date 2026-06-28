"""Authentification VindIA via Supabase Auth (vrai login par utilisateur).

Remplace le code d'accès partagé : la page se connecte avec email + mot de passe
(SDK Supabase) et envoie le jeton d'accès ; le serveur le VALIDE ici. L'identité
(member_id = id Supabase, email, admin) en découle → projets/mémoire/coffre restent
isolés, mais derrière une vraie authentification (impossible de deviner un « code »).

Validation = appel à `GET /auth/v1/user` de Supabase (le seul à pouvoir confirmer/
révoquer un jeton). Mémoïsé brièvement (cache TTL) pour ne pas appeler le réseau à
chaque requête. Le transport HTTP est injectable → testable 100 % offline, 0 dépendance.

admin : un email présent dans la liste blanche (env VINDIA_ADMIN_EMAILS) reçoit les
outils sensibles (état du VPS). Les autres comptes ne les ont jamais.
"""

from __future__ import annotations

import time
from typing import Awaitable, Callable, Dict, Optional, Tuple

# Transport : (url, headers) -> (status_http, json_dict). Injectable (aiohttp en prod).
HttpGet = Callable[[str, dict], Awaitable[Tuple[int, dict]]]


class SupabaseAuth:
    """Valide un jeton Supabase et en déduit l'identité VindIA."""

    def __init__(
        self,
        url: str,
        anon_key: str,
        admin_emails,
        *,
        http: Optional[HttpGet] = None,
        cache_ttl: float = 300.0,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._url = (url or "").rstrip("/")
        self._anon = anon_key or ""
        self._admins = {e.strip().lower() for e in (admin_emails or []) if e and e.strip()}
        self._http = http
        self._ttl = cache_ttl
        self._clock = clock or time.monotonic
        # token -> (identity, expiration monotonic)
        self._cache: Dict[str, Tuple[dict, float]] = {}

    @property
    def configured(self) -> bool:
        return bool(self._url and self._anon)

    async def verify(self, token: str) -> Optional[dict]:
        """Retourne {member_id, email, admin} si le jeton est valide, sinon None."""
        if not token:
            return None
        now = self._clock()
        cached = self._cache.get(token)
        if cached and cached[1] > now:
            return cached[0]
        http = self._http or self._live_http()
        try:
            status, data = await http(
                f"{self._url}/auth/v1/user",
                {"Authorization": f"Bearer {token}", "apikey": self._anon},
            )
        except Exception:
            return None
        if status != 200 or not isinstance(data, dict) or not data.get("id"):
            return None
        email = (data.get("email") or "").strip().lower()
        identity = {
            "member_id": str(data["id"]),
            "email": email,
            "admin": email in self._admins,
        }
        self._cache[token] = (identity, now + self._ttl)
        return identity

    def _live_http(self) -> HttpGet:  # pragma: no cover - live
        async def _get(url: str, headers: dict) -> Tuple[int, dict]:
            import aiohttp

            async with aiohttp.ClientSession(headers=headers) as sess:
                async with sess.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    try:
                        data = await resp.json()
                    except Exception:
                        data = {}
                    return resp.status, data

        return _get


def bearer_token(authorization_header: str) -> str:
    """Extrait le jeton d'un en-tête « Authorization: Bearer <token> »."""
    h = (authorization_header or "").strip()
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return ""
