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
# LLM tool-aware : (messages, specs d'outils) -> {content, tool_calls, assistant}.
# Contrat détaillé dans MistralLLM._reply_with_tools.
LlmToolTransport = Callable[[Sequence[dict], Sequence[dict]], Awaitable[dict]]
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
    "Pas de formules de politesse excessives, pas de récapitulatif.\n"
    "5. DOCUMENTS À TÉLÉCHARGER : quand on te demande de créer un document, un "
    "fichier ou un livrable (Word, Excel, PowerPoint, PDF, note, tableau…), écris-le "
    "ENTRE les marqueurs [[FICHIER:nom.ext]] et [[/FICHIER]]. Conventions de contenu : "
    ".docx et .pdf = texte avec titres « # » et puces « - » ; .xlsx = lignes au format "
    "CSV ; .pptx = diapositives séparées par une ligne « --- ». Le contenu entre les "
    "marqueurs PEUT être long et structuré — la règle de brièveté ne s'y applique PAS. "
    "En dehors des marqueurs, garde une phrase courte : annonce simplement que le "
    "document est prêt."
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
        tools: Optional[object] = None,
        tool_transport: Optional["LlmToolTransport"] = None,
        max_tool_hops: int = 4,
    ) -> None:
        self._transport = transport
        self._model = model
        self._system_prompt = system_prompt
        self._max_history = max_history
        # Outils (ToolRegistry duck-typé : `.specs()` + `.dispatch()`). Optionnel :
        # absent → comportement texte pur historique inchangé. Présent → boucle
        # function-calling activée (le LLM peut chercher sur le web, etc.).
        self._tools = tools
        self._tool_transport = tool_transport
        # Garde-fou anti-boucle : nb max d'allers-retours d'outils par énoncé.
        self._max_tool_hops = max_tool_hops
        # Historique par session : deque bornée à max_history tours (user+assistant).
        self._history: Dict[str, Deque[dict]] = {}
        # Contexte mémorisé long-terme injecté par MemoryStore à l'ouverture de session.
        self._memory_context: Dict[str, str] = {}
        # Contexte du PROJET actif (documents de l'utilisateur), injecté par ProjectStore.
        self._project_context: Dict[str, str] = {}
        self._client = None  # mémoïsé au 1er appel live

    async def reply(self, text: str, *, session_id: str, extra_tools: Optional[object] = None) -> str:
        history = self._history.get(session_id, deque(maxlen=self._max_history * 2))
        messages: list[dict] = []
        # System = prompt de base + mémoire long-terme + projet actif (si présents).
        parts = [
            p
            for p in (
                self._system_prompt,
                self._memory_context.get(session_id),
                self._project_context.get(session_id),
            )
            if p
        ]
        if parts:
            messages.append({"role": "system", "content": "\n\n".join(parts)})
        messages.extend(history)
        messages.append({"role": "user", "content": text})

        # Outils actifs pour CET énoncé : globaux (web) + éventuels outils de
        # session (projet de l'utilisateur), combinés sans muter le registre global.
        if extra_tools is not None and self._tools is not None:
            active_tools = self._tools.merged_with(extra_tools)
        else:
            active_tools = extra_tools if extra_tools is not None else self._tools

        if active_tools:
            response = await self._reply_with_tools(messages, active_tools)
        else:
            transport = self._transport or self._live_transport()
            response = await transport(messages)

        # Mise à jour de l'historique après réponse réussie. NB : seuls le tour
        # user et la réponse finale entrent dans l'historique long-terme — les
        # allers-retours d'outils restent internes à l'énoncé (pas de pollution).
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": response})
        self._history[session_id] = history
        return response

    async def _reply_with_tools(self, base: Sequence[dict], tools: object) -> str:
        """Boucle function-calling : LLM ↔ outils jusqu'à une réponse en clair.

        `tools` = le registre actif pour cet énoncé (globaux + session). Contrat du
        `tool_transport` — `(messages, specs) -> dict` avec :
          - "content"    : texte de réponse (présent quand pas de tool_calls) ;
          - "tool_calls" : liste normalisée [{id, name, arguments}] à exécuter ;
          - "assistant"  : message assistant à réinjecter tel quel au tour suivant.
        """
        transport = self._tool_transport or self._live_tool_transport()
        specs = tools.specs()
        work = list(base)
        for _ in range(self._max_tool_hops):
            out = await transport(work, specs)
            calls = out.get("tool_calls") or []
            if not calls:
                return out.get("content") or ""
            work.append(out["assistant"])  # assistant + ses tool_calls
            for call in calls:
                result = await tools.dispatch(call["name"], call.get("arguments"))
                work.append(
                    {
                        "role": "tool",
                        "name": call["name"],
                        "tool_call_id": call.get("id", ""),
                        "content": result,
                    }
                )
        # Hops épuisés : dernier appel SANS outils pour forcer une réponse parlée.
        final = await transport(work, [])
        return final.get("content") or "Désolée, je n'ai pas réussi à aboutir."

    def load_memory(self, session_id: str, context: str) -> None:
        """Injecte la mémoire long-terme d'un membre (appelé par le runtime à open())."""
        self._memory_context[session_id] = context

    def load_project(self, session_id: str, context: str) -> None:
        """Active un projet : injecte ses documents dans le contexte de la session.

        Canal distinct de la mémoire long-terme → activer/changer de projet ne
        touche pas aux souvenirs du membre. `context` vide désactive le projet.
        """
        if context:
            self._project_context[session_id] = context
        else:
            self._project_context.pop(session_id, None)

    def unload_memory(self, session_id: str) -> None:
        """Libère la mémoire, le projet actif et l'historique d'une session fermée."""
        self._memory_context.pop(session_id, None)
        self._project_context.pop(session_id, None)
        self._history.pop(session_id, None)

    def get_history(self, session_id: str) -> list:
        """Retourne l'historique de la session (pour extraction en fin de session)."""
        h = self._history.get(session_id)
        return list(h) if h else []

    def _live_transport(self) -> LlmTransport:
        async def _call(messages: Sequence[dict]) -> str:  # pragma: no cover - live
            client = self._lazy_client()
            resp = await client.chat.complete_async(
                model=self._model, messages=list(messages)
            )
            return resp.choices[0].message.content

        self._transport = _call  # n'enferme pas la lazy-init côté CI
        return _call

    def _live_tool_transport(self) -> "LlmToolTransport":  # pragma: no cover - live
        """Transport Mistral tool-aware : mappe l'API vers le contrat de la boucle."""

        async def _call(messages: Sequence[dict], specs: Sequence[dict]) -> dict:
            client = self._lazy_client()
            kwargs: dict = {"model": self._model, "messages": list(messages)}
            if specs:
                kwargs["tools"] = list(specs)
                kwargs["tool_choice"] = "auto"
            resp = await client.chat.complete_async(**kwargs)
            msg = resp.choices[0].message
            tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,  # str JSON côté API
                }
                for tc in (getattr(msg, "tool_calls", None) or [])
            ]
            # Message assistant réinjectable tel quel au tour suivant (format API).
            assistant: dict = {"role": "assistant", "content": msg.content or ""}
            if tool_calls:
                assistant["tool_calls"] = [
                    {
                        "id": c["id"],
                        "type": "function",
                        "function": {"name": c["name"], "arguments": c["arguments"]},
                    }
                    for c in tool_calls
                ]
            return {"content": msg.content, "tool_calls": tool_calls, "assistant": assistant}

        self._tool_transport = _call
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
