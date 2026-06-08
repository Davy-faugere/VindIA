"""Pont audio LiveKit ⇄ agent.

Ce module contient :
- `RoomSessionRegistry` : mapping room → session_id + résolution speaker_id →
  member_id. Logique PURE, sans dépendance LiveKit, entièrement testable.
- `HalfDuplexGate` : verrou anti-larsen (on coupe la capture entrante pendant que
  l'agent parle). Logique PURE, testable.
- `LiveKitRoomOut` / `LiveKitAudioBridge` : adaptateurs qui touchent le SDK LiveKit.
  Les méthodes réseau sont des SQUELETTES balisés TODO (à implémenter quand le SDK
  `livekit`/`livekit-rtc` est ajouté aux dépendances) ; leur structure et leurs
  contrats sont posés ici pour câbler `main.run()`.

Garde-fous : 1 personne = 1 device = 1 identité ; le `speaker_id` de diarisation
n'est JAMAIS utilisé comme identité — il est résolu vers un `member_id`.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Dict, Optional

# Résolveur injecté : (tenant_id, speaker_id) -> member_id (ou None si inconnu).
MemberResolver = Callable[[str, str], Optional[str]]

# Callback d'énoncé finalisé : (session_id, audio) -> Awaitable.
UtteranceCallback = Callable[[str, object], Awaitable[None]]


class RoomSessionRegistry:
    """Associe rooms et sessions, et résout les labels de diarisation.

    Pur, synchrone, testable. Aucune dépendance LiveKit.
    """

    def __init__(self, member_resolver: Optional[MemberResolver] = None) -> None:
        self._room_to_session: Dict[str, str] = {}
        self._session_to_room: Dict[str, str] = {}
        self._member_resolver = member_resolver

    def bind(self, room: str, session_id: str) -> None:
        """Lie une room à une session (1 room ↔ 1 session)."""
        if room in self._room_to_session and self._room_to_session[room] != session_id:
            raise ValueError(f"room {room!r} déjà liée à une autre session")
        self._room_to_session[room] = session_id
        self._session_to_room[session_id] = room

    def session_for(self, room: str) -> Optional[str]:
        return self._room_to_session.get(room)

    def room_for(self, session_id: str) -> Optional[str]:
        return self._session_to_room.get(session_id)

    def unbind(self, room: str) -> None:
        session_id = self._room_to_session.pop(room, None)
        if session_id is not None:
            self._session_to_room.pop(session_id, None)

    def resolve_member(self, tenant_id: str, speaker_id: str) -> Optional[str]:
        """Résout un label de diarisation vers une identité membre.

        Retourne None si aucun résolveur n'est fourni ou si le speaker est inconnu :
        l'appelant ne doit PAS retomber sur le speaker_id comme identité.
        """
        if self._member_resolver is None:
            return None
        return self._member_resolver(tenant_id, speaker_id)


class HalfDuplexGate:
    """Anti-larsen : suspend la capture entrante quand l'agent parle.

    Pur et testable. `agent_started()/agent_stopped()` encadrent la lecture TTS ;
    `should_capture()` indique si l'audio entrant doit être traité.
    """

    def __init__(self) -> None:
        self._agent_speaking = False

    def agent_started(self) -> None:
        self._agent_speaking = True

    def agent_stopped(self) -> None:
        self._agent_speaking = False

    @property
    def agent_speaking(self) -> bool:
        return self._agent_speaking

    def should_capture(self) -> bool:
        return not self._agent_speaking


class LiveKitRoomOut:
    """Piste de sortie : publie les frames audio TTS dans la room.

    Adaptateur SDK LiveKit. La publication réseau est un squelette TODO.
    """

    def __init__(self, room: object) -> None:
        self._room = room
        self._gate = HalfDuplexGate()
        self._track = None  # piste audio locale (créée à l'ouverture)

    @property
    def gate(self) -> HalfDuplexGate:
        return self._gate

    async def play(self, audio: object) -> None:
        """Publie les frames audio TTS sur la piste de sortie de la room.

        Encadre la lecture par le half-duplex (anti-larsen) : on marque l'agent
        comme parlant pendant l'émission, ce qui suspend la capture entrante.
        """
        self._gate.agent_started()
        try:
            # TODO(livekit): créer la piste locale si besoin, encoder `audio` en
            # frames Opus/PCM et les pousser via livekit-rtc (AudioSource.capture_frame).
            raise NotImplementedError("LiveKitRoomOut.play — câblage SDK LiveKit à faire")
        finally:
            self._gate.agent_stopped()


class LiveKitAudioBridge:
    """S'abonne aux pistes entrantes, alimente la VAD, émet les énoncés finalisés.

    Adaptateur SDK LiveKit. L'abonnement réseau est un squelette TODO ; le mapping
    room → session et la résolution membre passent par `RoomSessionRegistry`.
    """

    def __init__(self, registry: RoomSessionRegistry) -> None:
        self._registry = registry
        self.on_utterance: Optional[UtteranceCallback] = None

    async def start(self, room: object) -> None:
        """S'abonne aux pistes audio entrantes de la room.

        TODO(livekit): brancher room.on('track_subscribed'), lire les frames,
        les pousser dans un VoiceSegmenter, et appeler `_emit` à chaque énoncé.
        """
        raise NotImplementedError(
            "LiveKitAudioBridge.start — abonnement pistes LiveKit à faire"
        )

    async def _emit(self, room_name: str, audio: object) -> None:
        """Route un énoncé finalisé vers le callback, via la session de la room."""
        session_id = self._registry.session_for(room_name)
        if session_id is None or self.on_utterance is None:
            return
        await self.on_utterance(session_id, audio)
