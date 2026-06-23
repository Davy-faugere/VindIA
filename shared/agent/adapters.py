"""Adaptateurs concrets STT / LLM / TTS pour le runtime conversationnel.

Ces classes implémentent les `Protocol` de `runtime.py` (STT / LLM / TTS) avec
des fournisseurs souverains EU : STT = Voxtral, LLM = Mistral (La Plateforme,
hébergement UE). Le TTS reste agnostique (fournisseur souverain à trancher).

Contrainte CI : ce module n'importe AUCUNE dépendance tierce au chargement.
Les libs réelles (`mistralai`) sont importées PARESSEUSEMENT, au premier appel
réseau seulement. En test, on injecte un `transport` mocké → 100 % offline,
0 dépendance, exécutable par la CI stdlib.

Chaque adaptateur accepte un `transport` injectable :
  - fourni (tests / wiring custom) → utilisé tel quel ;
  - absent → construit paresseusement depuis l'environnement au 1er appel
    (clé lue dans `MISTRAL_API_KEY` ; erreur claire si lib absente / clé absente).

NB câblage live : les signatures exactes du SDK `mistralai` (méthodes async,
noms de modèles) sont à confirmer contre la version installée le jour du
branchement — d'où l'isolation derrière `transport` (le runtime, lui, est figé).
"""

from __future__ import annotations

import os
from collections import deque
from typing import Awaitable, Callable, Deque, Dict, Optional, Sequence

# --- Frontières réseau injectables (le "joint" testable de chaque adaptateur) ---
# LLM : liste de messages {role, content} -> texte de réponse.
LlmTransport = Callable[[Sequence[dict]], Awaitable[str]]
# STT : (audio brut, locale BCP-47) -> transcription.
SttTransport = Callable[[object, str], Awaitable[str]]
# TTS : (texte, locale BCP-47) -> audio synthétisé (bytes).
TtsTransport = Callable[[str, str], Awaitable[bytes]]

DEFAULT_LLM_MODEL = "mistral-large-latest"
DEFAULT_STT_MODEL = "voxtral-mini-latest"

# Prompt injecté par défaut dans toutes les sessions VindIA.
# Priorités : français strict, oral, sans markdown, bref.
VINDIA_SYSTEM_PROMPT = (
    "Tu es VindIA, une assistante vocale française bienveillante et directe.\n"
    "RÈGLES ABSOLUES — ne jamais déroger :\n"
    "1. Réponds TOUJOURS et UNIQUEMENT en français, même si on te parle dans une autre langue.\n"
    "2. N'utilise JAMAIS de markdown : pas d'astérisques, pas de tirets de liste, "
    "pas de titres (#), pas de gras, pas de code. Ta réponse sera lue à voix haute.\n"
    "3. Sois BREF : 1 à 2 phrases maximum. Va à l'essentiel, sans introduction.\n"
    "4. Parle naturellement, comme dans une vraie conversation. "
    "Pas de formules de politesse excessives, pas de récapitulatif."
)


def _require_mistral_key() -> str:
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise RuntimeError(
            "MISTRAL_API_KEY manquante dans l'environnement (cf. server/.env)."
        )
    return key


class MistralLLM:
    """LLM via Mistral La Plateforme (souveraineté UE). Implémente `LLM`.

    Exemple (live) :  llm = MistralLLM()  # VINDIA_SYSTEM_PROMPT par défaut
    Exemple (test) :  llm = MistralLLM(transport=fake_async_returning_text)

    `max_history` : nombre de tours (user+assistant) conservés par session. Borné
    pour éviter une croissance illimitée du contexte en sessions longues.
    """

    def __init__(
        self,
        transport: Optional[LlmTransport] = None,
        *,
        model: str = DEFAULT_LLM_MODEL,
        system_prompt: Optional[str] = VINDIA_SYSTEM_PROMPT,
        max_history: int = 5,
    ) -> None:
        self._transport = transport
        self._model = model
        self._system_prompt = system_prompt
        self._max_history = max_history
        # Historique par session : deque de (role, content) bornée à max_history tours.
        self._history: Dict[str, Deque[dict]] = {}
        self._client = None  # mémoïsé au 1er appel live

    async def reply(self, text: str, *, session_id: str) -> str:
        history = self._history.get(session_id, deque(maxlen=self._max_history * 2))
        messages: list[dict] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": text})
        transport = self._transport or self._live_transport()
        response = await transport(messages)
        # Mise à jour de l'historique après réponse réussie.
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": response})
        self._history[session_id] = history
        return response

    def _live_transport(self) -> LlmTransport:
        async def _call(messages: Sequence[dict]) -> str:  # pragma: no cover - live
            client = self._lazy_client()
            resp = await client.chat.complete_async(
                model=self._model, messages=list(messages)
            )
            return resp.choices[0].message.content

        self._transport = _call  # n'enferme pas la lazy-init côté CI
        return _call

    def _lazy_client(self):  # pragma: no cover - dépend de l'install live
        if self._client is None:
            try:
                from mistralai import Mistral
            except ImportError as exc:
                raise RuntimeError(
                    "mistralai non installé : `pip install mistralai` pour le live."
                ) from exc
            self._client = Mistral(api_key=_require_mistral_key())
        return self._client


class VoxtralSTT:
    """STT via Voxtral (Mistral audio, souveraineté UE). Implémente `STT`.

    Exemple (test) :  stt = VoxtralSTT(transport=fake_async_returning_text)
    """

    def __init__(
        self,
        transport: Optional[SttTransport] = None,
        *,
        model: str = DEFAULT_STT_MODEL,
    ) -> None:
        self._transport = transport
        self._model = model
        self._client = None

    async def transcribe(self, audio: object, locale: str) -> str:
        transport = self._transport or self._live_transport()
        return await transport(audio, locale)

    def _live_transport(self) -> SttTransport:
        async def _call(audio: object, locale: str) -> str:  # pragma: no cover - live
            client = self._lazy_client()
            # L'API attend un objet File {file_name, content}, pas des bytes bruts.
            resp = await client.audio.transcriptions.complete_async(
                model=self._model,
                file={"file_name": "utterance.wav", "content": bytes(audio)},
                language=locale.split("-")[0],
            )
            return resp.text

        self._transport = _call
        return _call

    def _lazy_client(self):  # pragma: no cover - dépend de l'install live
        if self._client is None:
            try:
                from mistralai import Mistral
            except ImportError as exc:
                raise RuntimeError(
                    "mistralai non installé : `pip install mistralai` pour le live."
                ) from exc
            self._client = Mistral(api_key=_require_mistral_key())
        return self._client


class CallableTTS:
    """TTS agnostique : délègue à un `transport` (texte, locale) -> bytes.

    Le fournisseur TTS souverain n'est pas encore tranché (décision Davy) :
    cet adaptateur EST le joint d'injection — on branchera le vrai backend
    (self-host Piper/Coqui, ou provider EU) derrière le même `transport`,
    sans toucher le runtime. Implémente `TTS`.
    """

    def __init__(self, transport: TtsTransport) -> None:
        self._transport = transport

    async def synthesize(self, text: str, locale: str) -> bytes:
        return await self._transport(text, locale)
