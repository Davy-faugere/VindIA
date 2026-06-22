"""Runtime conversationnel : STT → LLM → TTS, modèles substituables.

Les briques (STT/LLM/TTS) sont des `Protocol` : on branche Voxtral/Mistral en prod,
des fakes en test. Le runtime applique le garde-fou consentement et émet l'audit.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Dict, Optional, Protocol, Tuple

from .session import SessionDescriptor


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
        self, stt: STT, llm: LLM, tts: TTS, audit: Optional[AuditSink] = None
    ) -> None:
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._audit = audit
        self._sessions: Dict[str, Tuple[SessionDescriptor, RoomOut]] = {}

    async def open(self, desc: SessionDescriptor, room_out: RoomOut) -> None:
        self._sessions[desc.session_id] = (desc, room_out)
        self._emit(desc.session_id, "session_opened", {"tenant": desc.tenant_id})

    def close(self, session_id: str) -> None:
        if self._sessions.pop(session_id, None) is not None:
            self._emit(session_id, "session_closed", {})

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
        speech = await self._tts.synthesize(reply, desc.locale)
        await room_out.play(speech)
        self._emit(session_id, "reply", {"text": reply})

    def _emit(self, session_id: str, event_type: str, payload: dict) -> None:
        if self._audit is not None:
            self._audit(session_id, event_type, payload)
