"""Tests de la transcription — offline, ffmpeg et Voxtral mockés."""

import asyncio
import tempfile
import unittest
from pathlib import Path

from shared.agent.transcribe_tools import TranscribeTool


def _tool(tmp, *, segments=None, transcribe=None):
    async def fake_transcribe(audio, locale):
        return transcribe if transcribe is not None else "Bonjour, ceci est la transcription."
    def fake_extract(path):
        return segments if segments is not None else [b"AUDIO"]
    return TranscribeTool(tmp, fake_transcribe, extract_segments=fake_extract)


class TranscribeTest(unittest.TestCase):
    def _media(self, tmp, name="reunion.mp4"):
        (Path(tmp) / name).write_bytes(b"fake video bytes")
        return name

    def test_transcribes_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._media(tmp)
            out = asyncio.run(_tool(tmp).run({"filename": "reunion.mp4"}))
            self.assertIn("transcription", out)

    def test_rejects_non_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "doc.txt").write_text("x")
            out = asyncio.run(_tool(tmp).run({"filename": "doc.txt"}))
            self.assertIn("pas un média", out)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = asyncio.run(_tool(tmp).run({"filename": "absent.mp3"}))
            self.assertIn("introuvable", out)

    def test_traversal_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = asyncio.run(_tool(tmp).run({"filename": "../../x.mp4"}))
            self.assertIn("refusé", out)

    def test_empty_transcription(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._media(tmp, "vide.wav")
            out = asyncio.run(_tool(tmp, transcribe="").run({"filename": "vide.wav"}))
            self.assertIn("vide", out)

    def test_multiple_segments_concatenated(self):
        # Découpage : 3 tranches → 3 transcriptions recollées dans l'ordre.
        with tempfile.TemporaryDirectory() as tmp:
            self._media(tmp, "longue.mp4")
            calls = {"n": 0}
            async def tr(audio, locale):
                calls["n"] += 1
                return f"partie{calls['n']}"
            def segs(path):
                return [b"s1", b"s2", b"s3"]
            tool = TranscribeTool(tmp, tr, extract_segments=segs)
            out = asyncio.run(tool.run({"filename": "longue.mp4"}))
            self.assertEqual(calls["n"], 3)
            self.assertIn("partie1", out)
            self.assertIn("partie3", out)

    def test_extraction_failure_handled(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._media(tmp, "ko.mov")
            async def tr(a, l): return "x"
            def boom(p): raise RuntimeError("ffmpeg cassé")
            tool = TranscribeTool(tmp, tr, extract_segments=boom)
            out = asyncio.run(tool.run({"filename": "ko.mov"}))
            self.assertIn("Extraction audio impossible", out)


if __name__ == "__main__":
    unittest.main()
