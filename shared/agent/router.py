"""Routage des énoncés finalisés vers le runtime conversationnel.

Squelette : `Router.dispatch(session_id, audio)` est le point d'entrée branché sur
`LiveKitAudioBridge.on_utterance`. Le câblage STT→LLM→TTS sera ajouté avec le runtime.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Optional

RuntimeDispatch = Callable[[str, object], Awaitable[None]]


class Router:
    def __init__(self, runtime_dispatch: Optional[RuntimeDispatch] = None) -> None:
        self._runtime_dispatch = runtime_dispatch

    async def dispatch(self, session_id: str, audio: object) -> None:
        if self._runtime_dispatch is None:
            # TODO(runtime): brancher STT (Voxtral) → LLM (Mistral) → TTS → RoomOut.play
            return
        await self._runtime_dispatch(session_id, audio)
