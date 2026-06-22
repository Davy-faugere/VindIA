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

import array
import asyncio
import io
import wave
from typing import Awaitable, Callable, Dict, List, Optional, Sequence

from .vad import VoiceSegmenter

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

    Adaptateur SDK LiveKit. `play(audio)` reçoit du PCM 16 bits mono au
    `sample_rate` configuré (sortie du TTS), le découpe en frames de 10 ms et
    les pousse sur une `AudioSource` publiée dans la room.

    Testabilité : la `source` et la fabrique de frames (`frame_factory`) sont
    injectables. En test, on injecte des fakes → 0 dépendance LiveKit. En live,
    elles sont créées paresseusement via `livekit.rtc` au 1er `play`.
    """

    FRAME_MS = 10  # durée d'une frame poussée à l'AudioSource

    def __init__(
        self,
        room: object,
        *,
        sample_rate: int = 48000,
        num_channels: int = 1,
        source: object = None,
        frame_factory: Optional[Callable[[bytes, int, int, int], object]] = None,
        track_name: str = "vindia-tts",
    ) -> None:
        self._room = room
        self._gate = HalfDuplexGate()
        self._sample_rate = sample_rate
        self._num_channels = num_channels
        self._source = source
        self._frame_factory = frame_factory
        self._track_name = track_name
        self._published = source is not None

    @property
    def gate(self) -> HalfDuplexGate:
        return self._gate

    def _chunks(self, audio: bytes):
        """Découpe le PCM en tranches (data, samples_per_channel) de FRAME_MS.

        Logique pure (pas de SDK) → testable hors-ligne.
        """
        bytes_per_sample = 2 * self._num_channels  # int16
        spf = int(self._sample_rate * self.FRAME_MS / 1000)  # samples/frame/canal
        step = spf * bytes_per_sample
        if step <= 0:
            return
        for i in range(0, len(audio), step):
            chunk = audio[i : i + step]
            n = len(chunk) // bytes_per_sample
            if n > 0:
                yield chunk, n

    async def _ensure_source(self) -> object:
        """Crée et publie l'AudioSource au 1er usage (lazy, live uniquement)."""
        if self._source is None:
            import livekit.rtc as rtc  # lazy : hors CI

            self._source = rtc.AudioSource(self._sample_rate, self._num_channels)
            track = rtc.LocalAudioTrack.create_audio_track(self._track_name, self._source)
            await self._room.local_participant.publish_track(
                track, rtc.TrackPublishOptions()
            )
            self._published = True
        return self._source

    def _make_frame(self, data: bytes, samples_per_channel: int) -> object:
        if self._frame_factory is not None:
            return self._frame_factory(
                data, self._sample_rate, self._num_channels, samples_per_channel
            )
        import livekit.rtc as rtc  # lazy : hors CI

        return rtc.AudioFrame(
            data, self._sample_rate, self._num_channels, samples_per_channel
        )

    async def play(self, audio: object) -> None:
        """Publie les frames audio TTS sur la piste de sortie de la room.

        Encadre la lecture par le half-duplex (anti-larsen) : on marque l'agent
        comme parlant pendant l'émission, ce qui suspend la capture entrante.
        """
        source = await self._ensure_source()
        self._gate.agent_started()
        try:
            for data, n in self._chunks(bytes(audio)):
                await source.capture_frame(self._make_frame(data, n))
        finally:
            self._gate.agent_stopped()


def _frame_to_samples(frame: object) -> Sequence[int]:
    """AudioFrame (ou objet `.data`) PCM int16 -> séquence d'échantillons int.

    Accepte un `livekit.rtc.AudioFrame` (attribut `.data`) ou un objet exposant
    `.data`, ou des bytes bruts. Décodage int16 little-endian via `array` (stdlib).
    """
    data = getattr(frame, "data", frame)
    return array.array("h", bytes(data))


def _utterance_to_wav(
    utterance: List[Sequence[int]], sample_rate: int, num_channels: int = 1
) -> bytes:
    """Liste de frames int16 -> WAV en mémoire (header = sample_rate, pas de
    resampling : l'API STT lit le débit dans l'en-tête)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(num_channels)
        w.setsampwidth(2)  # int16
        w.setframerate(sample_rate)
        for frame in utterance:
            w.writeframes(array.array("h", frame).tobytes())
    return buf.getvalue()


class LiveKitAudioBridge:
    """S'abonne aux pistes entrantes, alimente la VAD, émet les énoncés finalisés.

    Adaptateur SDK LiveKit. `start` branche l'abonnement réseau (lazy SDK) ;
    `_consume_stream` porte la logique (VAD + segmentation), testable hors-ligne
    avec un flux fake. Le mapping room → session passe par `RoomSessionRegistry`.
    """

    def __init__(
        self,
        registry: RoomSessionRegistry,
        *,
        sample_rate: int = 48000,
        num_channels: int = 1,
        gate: Optional["HalfDuplexGate"] = None,
        vad_threshold: Optional[float] = None,
    ) -> None:
        self._registry = registry
        self._sample_rate = sample_rate
        self._num_channels = num_channels
        self._gate = gate                  # anti-larsen : ignore l'entrée quand l'agent parle
        self._vad_threshold = vad_threshold
        self.on_utterance: Optional[UtteranceCallback] = None

    async def start(self, room: object, *, stream_factory=None) -> None:
        """S'abonne aux pistes audio entrantes : VAD → énoncés → `_emit`.

        `stream_factory(track)` renvoie un flux async de frames (injectable en
        test). En live, il est créé via `livekit.rtc.AudioStream`.
        """
        make_stream = stream_factory or self._default_stream_factory

        def _on_track(track, *_) -> None:  # signature SDK : (track, publication, participant)
            import livekit.rtc as rtc  # lazy : hors CI

            if getattr(track, "kind", None) != rtc.TrackKind.KIND_AUDIO:
                return
            stream = make_stream(track)
            asyncio.create_task(self._consume_stream(room.name, stream))

        room.on("track_subscribed", _on_track)

    @staticmethod
    def _default_stream_factory(track: object):  # pragma: no cover - SDK live
        import livekit.rtc as rtc

        return rtc.AudioStream(track)

    async def _consume_stream(
        self, room_name: str, stream, *, segmenter: Optional[VoiceSegmenter] = None
    ) -> None:
        """Consomme un flux de frames : segmente en énoncés, émet chaque énoncé.

        Logique pure côté traitement (VAD) → testable avec un flux fake.
        """
        if segmenter is not None:
            seg = segmenter
        elif self._vad_threshold is not None:
            seg = VoiceSegmenter(threshold=self._vad_threshold)
        else:
            seg = VoiceSegmenter()
        async for event in stream:
            # Half-duplex : pendant que l'agent parle, on n'écoute pas (anti-larsen).
            # On vide tout énoncé partiel pour ne pas mélanger avec l'écho.
            if self._gate is not None and self._gate.agent_speaking:
                seg.flush()
                continue
            frame = getattr(event, "frame", event)  # AudioFrameEvent.frame ou frame direct
            utterance = seg.push(_frame_to_samples(frame))
            if utterance is not None:
                await self._emit(room_name, self._wav(utterance))
        tail = seg.flush()
        if tail is not None:
            await self._emit(room_name, self._wav(tail))

    def _wav(self, utterance: List[Sequence[int]]) -> bytes:
        return _utterance_to_wav(utterance, self._sample_rate, self._num_channels)

    async def _emit(self, room_name: str, audio: object) -> None:
        """Route un énoncé finalisé vers le callback, via la session de la room."""
        session_id = self._registry.session_for(room_name)
        if session_id is None or self.on_utterance is None:
            return
        await self.on_utterance(session_id, audio)
