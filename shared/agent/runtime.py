"""Runtime conversationnel : STT → LLM → TTS, modèles substituables.

Les briques (STT/LLM/TTS) sont des `Protocol` : on branche Voxtral/Mistral en prod,
des fakes en test. Le runtime applique le garde-fou consentement et émet l'audit.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Dict, Optional, Protocol, Tuple

from .session import SessionDescriptor
from .speech_normalize import normalize_for_speech


class STT(Protocol):
    async def transcribe(self, audio: object, locale: str) -> str: ...


class LLM(Protocol):
    async def reply(self, text: str, *, session_id: str) -> str: ...


class TTS(Protocol):
    async def synthesize(self, text: str, locale: str) -> object: ...


class RoomOut(Protocol):
    async def play(self, audio: object) -> None: ...


# (session_id, event_type, payload) -> None  (audit append-only)
AuditSink = Callable[[str, str, dict], None]


class ConversationRuntime:
    """Orchestre le traitement d'un énoncé pour une session ouverte."""

    # En-deçà, une transcription est considérée comme du bruit (pas de LLM/TTS).
    MIN_UTTERANCE_CHARS = 3

    def __init__(
        self,
        stt: STT,
        llm: LLM,
        tts: TTS,
        audit: Optional[AuditSink] = None,
        memory: Optional[object] = None,
    ) -> None:
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._audit = audit
        self._memory = memory  # MemoryStore optionnel (duck-typed)
        self._sessions: Dict[str, Tuple[SessionDescriptor, RoomOut]] = {}

    async def open(self, desc: SessionDescriptor, room_out: RoomOut) -> None:
        self._sessions[desc.session_id] = (desc, room_out)
        self._emit(desc.session_id, "session_opened", {"tenant": desc.tenant_id})
        # Injection mémoire long-terme : charge les souvenirs du membre dans le LLM.
        if self._memory and desc.member_id and hasattr(self._llm, "load_memory"):
            ctx = self._memory.load_context(desc.member_id)
            if ctx:
                self._llm.load_memory(desc.session_id, ctx)

    def close(self, session_id: str) -> None:
        entry = self._sessions.pop(session_id, None)
        if entry is None:
            return
        desc, _ = entry
        self._emit(session_id, "session_closed", {})
        # Extraction mémoire fire-and-forget : ne bloque pas la fermeture.
        if self._memory and desc.member_id and hasattr(self._llm, "get_history"):
            history = self._llm.get_history(session_id)
            if history:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(
                        self._memory.extract_and_save(
                            desc.member_id, desc.tenant_id, session_id, history
                        )
                    )
                except RuntimeError:
                    pass  # pas de boucle active — extraction ignorée
        # Libère RAM (historique + contexte mémorisé).
        if hasattr(self._llm, "unload_memory"):
            self._llm.unload_memory(session_id)

    async def handle(self, session_id: str, audio: object) -> None:
        """Pipeline d'un énoncé finalisé. No-op si session inconnue."""
        entry = self._sessions.get(session_id)
        if entry is None:
            return
        desc, room_out = entry

        # Garde-fou : pas de traitement sans consentement + identité résolue.
        if not desc.can_process():
            self._emit(session_id, "utterance_skipped_no_consent", {})
            return

        text = (await self._stt.transcribe(audio, desc.locale) or "").strip()
        self._emit(session_id, "transcript", {"text": text})

        # Anti-bruit : un énoncé sans parole exploitable (silence, souffle) ne
        # déclenche NI le LLM NI le TTS — sinon l'agent « répond » au vide et
        # gaspille le quota API.
        if len(text) < self.MIN_UTTERANCE_CHARS:
            self._emit(session_id, "utterance_empty", {"text": text})
            return

        reply = await self._llm.reply(text, session_id=session_id)

        # Couche déterministe : on ne laisse JAMAIS le markdown / les URLs / les
        # symboles bruts du LLM atteindre la voix. Garantie par le code, pas par
        # une consigne au modèle (qui fuit). Les mots anglais sont préservés.
        spoken = normalize_for_speech(reply, desc.locale)

        speech = await self._tts.synthesize(spoken, desc.locale)
        await room_out.play(speech)
        self._emit(session_id, "reply", {"text": reply, "spoken": spoken})

    def _emit(self, session_id: str, event_type: str, payload: dict) -> None:
        if self._audit is not None:
            self._audit(session_id, event_type, payload)
