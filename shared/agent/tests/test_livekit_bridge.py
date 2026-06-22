"""Tests de l'entrée LiveKitAudioBridge — offline, 0 dépendance LiveKit.

On injecte un flux de frames fake et une fake room : aucune lib SDK importée.
Couvre la conversion frame→samples, le packaging WAV, la segmentation VAD →
émission d'énoncé, et l'enregistrement du handler par `start`.
"""

import array
import asyncio
import io
import types
import unittest
import wave

from shared.agent.audio.livekit_io import (
    LiveKitAudioBridge,
    RoomSessionRegistry,
    _frame_to_samples,
    _utterance_to_wav,
)


def _frame(level: int, n: int = 480):
    """Frame fake exposant `.data` (PCM int16) comme un AudioFrame LiveKit."""
    return types.SimpleNamespace(data=array.array("h", [level] * n).tobytes())


class FakeStream:
    def __init__(self, frames):
        self._frames = frames

    def __aiter__(self):
        self._i = 0
        return self

    async def __anext__(self):
        if self._i >= len(self._frames):
            raise StopAsyncIteration
        f = self._frames[self._i]
        self._i += 1
        return f


class HelpersTest(unittest.TestCase):
    def test_frame_to_samples_decodes_int16(self):
        data = types.SimpleNamespace(data=array.array("h", [1, -2, 3]).tobytes())
        self.assertEqual(list(_frame_to_samples(data)), [1, -2, 3])

    def test_utterance_to_wav_is_valid_wav(self):
        utt = [array.array("h", [1000] * 480), array.array("h", [0] * 480)]
        raw = _utterance_to_wav(utt, sample_rate=16000, num_channels=1)
        w = wave.open(io.BytesIO(raw))
        self.assertEqual(w.getframerate(), 16000)
        self.assertEqual(w.getnchannels(), 1)
        self.assertEqual(w.getsampwidth(), 2)
        self.assertEqual(w.getnframes(), 960)


class ConsumeStreamTest(unittest.TestCase):
    def _bridge(self):
        reg = RoomSessionRegistry()
        reg.bind("room-a", "s1")
        b = LiveKitAudioBridge(reg, sample_rate=16000)
        got = []

        async def cb(sid, audio):
            got.append((sid, audio))

        b.on_utterance = cb
        return b, got

    def test_voice_then_silence_emits_one_utterance(self):
        bridge, got = self._bridge()
        # 5 frames "voix" (RMS élevé) puis 12 frames "silence" → 1 énoncé finalisé
        frames = [_frame(10000) for _ in range(5)] + [_frame(0) for _ in range(12)]
        asyncio.run(bridge._consume_stream("room-a", FakeStream(frames)))

        self.assertEqual(len(got), 1)
        sid, wav = got[0]
        self.assertEqual(sid, "s1")
        w = wave.open(io.BytesIO(wav))
        self.assertEqual(w.getframerate(), 16000)
        self.assertGreater(w.getnframes(), 0)

    def test_pure_silence_emits_nothing(self):
        bridge, got = self._bridge()
        asyncio.run(bridge._consume_stream("room-a", FakeStream([_frame(0) for _ in range(20)])))
        self.assertEqual(got, [])

    def test_unbound_room_does_not_emit(self):
        reg = RoomSessionRegistry()  # aucune session liée
        bridge = LiveKitAudioBridge(reg)
        got = []
        bridge.on_utterance = lambda sid, audio: got.append(sid)
        frames = [_frame(10000) for _ in range(5)] + [_frame(0) for _ in range(12)]
        asyncio.run(bridge._consume_stream("room-x", FakeStream(frames)))
        self.assertEqual(got, [])


class StartTest(unittest.TestCase):
    def test_start_registers_track_subscribed_handler(self):
        class FakeRoom:
            name = "room-a"

            def __init__(self):
                self.handlers = {}

            def on(self, event, cb):
                self.handlers[event] = cb

        reg = RoomSessionRegistry()
        bridge = LiveKitAudioBridge(reg)
        room = FakeRoom()
        asyncio.run(bridge.start(room))
        self.assertIn("track_subscribed", room.handlers)
        self.assertTrue(callable(room.handlers["track_subscribed"]))


if __name__ == "__main__":
    unittest.main()
