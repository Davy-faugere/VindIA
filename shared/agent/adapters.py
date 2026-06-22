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
from typing import Awaitable, Callable, Optional, Sequence

# --- Frontières réseau injectables (le "joint" testable de chaque adaptateur) ---
# LLM : liste de messages {role, content} -> texte de réponse.
LlmTransport = Callable[[Sequence[dict]], Awaitable[str]]
# STT : (audio brut, locale BCP-47) -> transcription.
SttTransport = Callable[[object, str], Awaitable[str]]
# TTS : (texte, locale BCP-47) -> audio synthétisé (bytes).
TtsTransport = Callable[[str, str], Awaitable[bytes]]

DEFAULT_LLM_MODEL = "mistral-large-latest"
DEFAULT_STT_MODEL = "voxtral-mini-latest"


def _require_mistral_key() -> str:
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise RuntimeError(
            "MISTRAL_API_KEY manquante dans l'environnement (cf. server/.env)."
        )
    return key


class MistralLLM:
    """LLM via Mistral La Plateforme (souveraineté UE). Implémente `LLM`.

    Exemple (live) :  llm = MistralLLM(system_prompt="Tu es l'assistant VindIA.")
    Exemple (test) :  llm = MistralLLM(transport=fake_async_returning_text)
    """

    def __init__(
        self,
        transport: Optional[LlmTransport] = None,
        *,
        model: str = DEFAULT_LLM_MODEL,
        system_prompt: Optional[str] = None,
    ) -> None:
        self._transport = transport
        self._model = model
        self._system_prompt = system_prompt
        self._client = None  # mémoïsé au 1er appel live

    async def reply(self, text: str, *, session_id: str) -> str:
        messages: list[dict] = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
        messages.append({"role": "user", "content": text})
        transport = self._transport or self._live_transport()
        return await transport(messages)

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
