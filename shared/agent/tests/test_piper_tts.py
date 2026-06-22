"""Tests du transport TTS Piper — offline, 0 dépendance.

On injecte un `synth` fake (texte -> PCM bytes) : aucun modèle ni lib Piper requis.
"""

import asyncio
import unittest

from shared.agent.piper_tts import piper_tts_transport


class PiperTtsTransportTest(unittest.TestCase):
    def test_transport_returns_synth_pcm(self):
        calls = []

        def fake_synth(text):
            calls.append(text)
            return b"PCM:" + text.encode()

        tts = piper_tts_transport(fake_synth)
        out = asyncio.run(tts("Bonjour", "fr-FR"))

        self.assertEqual(out, b"PCM:Bonjour")
        self.assertEqual(calls, ["Bonjour"])

    def test_locale_is_ignored(self):
        tts = piper_tts_transport(lambda text: b"x")
        self.assertEqual(asyncio.run(tts("a", "en-US")), b"x")
        self.assertEqual(asyncio.run(tts("a", "fr-FR")), b"x")


if __name__ == "__main__":
    unittest.main()
