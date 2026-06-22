"""Transport TTS Voxtral via l'API REST Mistral (`POST /v1/audio/speech`).

Le SDK `mistralai` 1.x n'expose pas le TTS → appel REST direct. Retourne l'audio
synthétisé en bytes (MP3 ; la réponse est un JSON `{"audio_data": <base64>}`).

0 dépendance tierce : `urllib` + `base64` stdlib → le module reste importable en
CI. L'appel HTTP est isolé derrière `http_post`, injectable → testable offline.
La clé est lue dans `MISTRAL_API_KEY`. Construit un `TtsTransport` (texte, locale)
-> bytes, branchable dans `CallableTTS`.

NB voix : le catalogue Mistral TTS n'expose pour l'instant que des voix EN
(`GET /v1/audio/voices`). Le modèle Voxtral est multilingue (le texte FR est
prononcé), la `voice` ne fixe que le timbre — choix de voix à arbitrer.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import urllib.request
from typing import Awaitable, Callable, Optional

TTS_ENDPOINT = "https://api.mistral.ai/v1/audio/speech"
DEFAULT_TTS_MODEL = "voxtral-mini-tts-latest"

# (endpoint, payload_dict) -> corps de réponse brut (str JSON)
HttpPost = Callable[[str, dict], str]
TtsTransport = Callable[[str, str], Awaitable[bytes]]


def _default_post(endpoint: str, payload: dict) -> str:  # pragma: no cover - réseau live
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise RuntimeError("MISTRAL_API_KEY manquante dans l'environnement.")
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def mistral_tts_transport(
    voice: str,
    *,
    model: str = DEFAULT_TTS_MODEL,
    endpoint: str = TTS_ENDPOINT,
    http_post: Optional[HttpPost] = None,
) -> TtsTransport:
    """Construit un transport TTS (texte, locale) -> bytes audio (MP3).

    `voice` : slug d'une voix Mistral (cf. GET /v1/audio/voices).
    `http_post` : injecté en test (offline) ; sinon appel REST réel.
    """
    post = http_post or _default_post

    async def _transport(text: str, locale: str) -> bytes:
        # locale non transmise : le modèle Voxtral infère la langue du texte.
        payload = {"model": model, "input": text, "voice": voice}
        raw = await asyncio.to_thread(post, endpoint, payload)
        data = json.loads(raw)
        b64 = data.get("audio_data")
        if not b64:
            raise RuntimeError(f"Réponse TTS sans audio_data : {str(data)[:200]}")
        return base64.b64decode(b64)

    return _transport
