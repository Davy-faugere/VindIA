"""Tests du transport TTS Voxtral — offline, 0 dépendance.

On injecte `http_post` (la frontière réseau) → aucun appel réel. On vérifie le
payload envoyé et le décodage base64 → bytes.
"""

import asyncio
import base64
import json
import unittest

from shared.agent.mistral_tts import mistral_tts_transport


class MistralTtsTransportTest(unittest.TestCase):
    def test_builds_payload_and_decodes_audio(self):
        seen = {}

        def fake_post(endpoint, payload):
            seen["endpoint"] = endpoint
            seen["payload"] = payload
            audio = b"\xff\xfb\x90fake-mp3-bytes"
            return json.dumps({"audio_data": base64.b64encode(audio).decode()})

        tts = mistral_tts_transport("en_paul_neutral", http_post=fake_post)
        out = asyncio.run(tts("Bonjour le monde", "fr-FR"))

        self.assertEqual(out, b"\xff\xfb\x90fake-mp3-bytes")
        self.assertEqual(seen["payload"]["voice"], "en_paul_neutral")
        self.assertEqual(seen["payload"]["input"], "Bonjour le monde")
        self.assertEqual(seen["payload"]["model"], "voxtral-mini-tts-latest")
        self.assertIn("/v1/audio/speech", seen["endpoint"])

    def test_missing_audio_data_raises(self):
        def fake_post(endpoint, payload):
            return json.dumps({"object": "error", "message": "boom"})

        tts = mistral_tts_transport("en_paul_neutral", http_post=fake_post)
        with self.assertRaises(RuntimeError):
            asyncio.run(tts("x", "fr-FR"))

    def test_custom_model_passed_through(self):
        seen = {}

        def fake_post(endpoint, payload):
            seen.update(payload)
            return json.dumps({"audio_data": base64.b64encode(b"a").decode()})

        tts = mistral_tts_transport("en_paul_neutral", model="voxtral-mini-tts-2603", http_post=fake_post)
        asyncio.run(tts("x", "fr-FR"))
        self.assertEqual(seen["model"], "voxtral-mini-tts-2603")


if __name__ == "__main__":
    unittest.main()
