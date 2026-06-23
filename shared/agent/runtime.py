"""Runtime conversationnel : STT → LLM → TTS, modèles substituables.

Les briques (STT/LLM/TTS) sont des `Protocol` : on branche Voxtral/Mistral en prod,
des fakes en test. Le runtime applique le garde-fou consentement et émet l'audit.
"""

from __future__ import annotations

import re
from typing import Awaitable, Callable, Dict, Optional, Protocol, Tuple

from .session import SessionDescriptor

# Séquence de substitutions pour rendre un texte LLM sûr pour la synthèse vocale.
# Appliquées dans l'ordre : du plus spécifique au plus général.
_TTS_CLEANERS = [
    (re.compile(r'\[([^\]]+)\]\([^\)]*\)'), r'\1'),  # [texte](url) → texte
    (re.compile(r'```.*?```', re.S), ''),             # blocs de code
    (re.compile(r'`([^`]+)`'), r'\1'),               # inline code
    (re.compile(r'\*\*(.+?)\*\*', re.S), r'\1'),     # **gras**
    (re.compile(r'\*(.+?)\*', re.S), r'\1'),         # *italique*
    (re.compile(r'_(.+?)_', re.S), r'\1'),           # _italique_
    (re.compile(r'^#{1,6}\s+', re.M), ''),           # ## titres
    (re.compile(r'^\s*[-*+]\s+', re.M), ''),         # - listes
    (re.compile(r'^\s*\d+\.\s+', re.M), ''),         # 1. listes numérotées
    (re.compile(r'^\s*>\s*', re.M), ''),             # > citations
    (re.compile(r'\n{3,}'), '\n\n'),                  # sauts de ligne excessifs
]


def _clean_for_tts(text: str) -> str:
    """Retire le markdown d'un texte LLM avant synthèse vocale."""
    for pattern, repl in _TTS_CLEANERS:
        text = pattern.sub(repl, text)
    return text.strip()


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
        # Nettoyage markdown avant synthèse : les **, #, - sont lus à voix haute
        # par le TTS sans ce filtre.
        tts_text = _clean_for_tts(reply)
        speech = await self._tts.synthesize(tts_text, desc.locale)
        await room_out.play(speech)
        self._emit(session_id, "reply", {"text": tts_text})

    def _emit(self, session_id: str, event_type: str, payload: dict) -> None:
        if self._audit is not None:
            self._audit(session_id, event_type, payload)
