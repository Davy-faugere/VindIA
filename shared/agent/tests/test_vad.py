import unittest

from shared.agent.audio.vad import VoiceSegmenter, frame_rms, segment_stream


def voiced(n, level=2000):
    return [level if i % 2 == 0 else -level for i in range(n)]


def silent(n):
    return [0] * n


class FrameRmsTest(unittest.TestCase):
    def test_empty_frame_is_zero(self):
        self.assertEqual(frame_rms([]), 0.0)

    def test_constant_amplitude(self):
        self.assertAlmostEqual(frame_rms([1000, -1000, 1000, -1000]), 1000.0)

    def test_silence_below_voice(self):
        self.assertLess(frame_rms(silent(160)), frame_rms(voiced(160)))


class VoiceSegmenterTest(unittest.TestCase):
    def test_single_utterance_finalized_after_hangover(self):
        seg = VoiceSegmenter(threshold=500, start_frames=3, hangover_frames=5)
        frames = [voiced(160)] * 10 + [silent(160)] * 6
        utterances = []
        for f in frames:
            u = seg.push(f)
            if u is not None:
                utterances.append(u)
        self.assertEqual(len(utterances), 1)
        # L'énoncé contient la voix + le hangover de silence qui le clôt.
        self.assertGreaterEqual(len(utterances[0]), 10)

    def test_short_blip_below_start_frames_ignored(self):
        seg = VoiceSegmenter(threshold=500, start_frames=3, hangover_frames=5)
        frames = [voiced(160)] * 2 + [silent(160)] * 6
        self.assertEqual([f for f in (seg.push(x) for x in frames) if f], [])

    def test_two_utterances_separated_by_silence(self):
        frames = (
            [voiced(160)] * 6
            + [silent(160)] * 8
            + [voiced(160)] * 6
            + [silent(160)] * 8
        )
        out = segment_stream(frames, threshold=500, start_frames=3, hangover_frames=5)
        self.assertEqual(len(out), 2)

    def test_flush_finalizes_open_utterance(self):
        seg = VoiceSegmenter(threshold=500, start_frames=2, hangover_frames=10)
        for f in [voiced(160)] * 5:
            seg.push(f)
        tail = seg.flush()
        self.assertIsNotNone(tail)
        self.assertEqual(seg.flush(), None)  # idempotent après reset


if __name__ == "__main__":
    unittest.main()
