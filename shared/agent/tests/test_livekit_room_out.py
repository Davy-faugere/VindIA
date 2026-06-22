"""Tests de LiveKitRoomOut.play — offline, 0 dépendance LiveKit.

On injecte une `source` fake et une `frame_factory` fake : aucune lib SDK n'est
importée. On vérifie le découpage en frames, le nombre de captures et le
garde-fou half-duplex (agent marqué parlant pendant l'émission, relâché après,
y compris en cas d'erreur).
"""

import asyncio
import unittest

from shared.agent.audio.livekit_io import LiveKitRoomOut


class FakeSource:
    def __init__(self):
        self.frames = []

    async def capture_frame(self, frame):
        self.frames.append(frame)


def _out(source, **kw):
    # frame_factory renvoie un simple tuple → pas d'AudioFrame réel
    return LiveKitRoomOut(
        room=object(),
        source=source,
        frame_factory=lambda data, sr, ch, n: (data, n),
        **kw,
    )


class ChunkingTest(unittest.TestCase):
    def test_chunks_split_into_10ms_frames(self):
        out = _out(FakeSource())  # 48 kHz mono → 480 samples = 960 bytes / frame
        audio = bytes(2400)  # 2.5 frames → 960 + 960 + 480
        chunks = list(out._chunks(audio))
        self.assertEqual([n for _, n in chunks], [480, 480, 240])
        self.assertEqual([len(d) for d, _ in chunks], [960, 960, 480])

    def test_empty_audio_yields_nothing(self):
        self.assertEqual(list(_out(FakeSource())._chunks(b"")), [])


class PlayTest(unittest.TestCase):
    def test_play_captures_all_frames(self):
        src = FakeSource()
        out = _out(src)
        asyncio.run(out.play(bytes(2400)))
        self.assertEqual(len(src.frames), 3)
        self.assertEqual(src.frames[0], (bytes(960), 480))

    def test_play_marks_agent_speaking_during_capture_then_releases(self):
        src = FakeSource()
        seen_states = []
        out = LiveKitRoomOut(
            room=object(),
            source=src,
            frame_factory=lambda d, sr, ch, n: seen_states.append(out.gate.agent_speaking) or (d, n),
        )
        asyncio.run(out.play(bytes(960)))
        self.assertTrue(all(seen_states), "agent doit être 'speaking' pendant la capture")
        self.assertFalse(out.gate.agent_speaking, "gate relâché après play")
        self.assertTrue(out.gate.should_capture())

    def test_gate_released_even_on_capture_error(self):
        class Boom(FakeSource):
            async def capture_frame(self, frame):
                raise RuntimeError("capture KO")

        out = _out(Boom())
        with self.assertRaises(RuntimeError):
            asyncio.run(out.play(bytes(960)))
        self.assertFalse(out.gate.agent_speaking, "gate relâché malgré l'erreur (finally)")


if __name__ == "__main__":
    unittest.main()
