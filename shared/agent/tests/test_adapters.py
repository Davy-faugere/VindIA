"""Tests des adaptateurs STT/LLM/TTS — 100 % offline, 0 dépendance.

On injecte un `transport` fake dans chaque adaptateur : aucun appel réseau,
aucune lib tierce. Le test end-to-end prouve que les adaptateurs respectent
bien les Protocol attendus par `ConversationRuntime`.
"""

import asyncio
import unittest

from shared.agent.adapters import CallableTTS, MistralLLM, VoxtralSTT
from shared.agent.runtime import ConversationRuntime
from shared.agent.session import SessionDescriptor


class MistralLLMTest(unittest.TestCase):
    def test_uses_transport_and_prepends_system_prompt(self):
        captured = {}

        async def fake(messages):
            captured["messages"] = list(messages)
            return "réponse-mock"

        llm = MistralLLM(transport=fake, system_prompt="Tu es VindIA.")
        out = asyncio.run(llm.reply("bonjour", session_id="s1"))

        self.assertEqual(out, "réponse-mock")
        self.assertEqual(
            captured["messages"],
            [
                {"role": "system", "content": "Tu es VindIA."},
                {"role": "user", "content": "bonjour"},
            ],
        )

    def test_without_system_prompt_sends_only_user_turn(self):
        captured = {}

        async def fake(messages):
            captured["messages"] = list(messages)
            return "ok"

        # system_prompt=None explicite pour désactiver le prompt par défaut.
        asyncio.run(MistralLLM(transport=fake, system_prompt=None).reply("salut", session_id="s1"))
        self.assertEqual(captured["messages"], [{"role": "user", "content": "salut"}])

    def test_default_system_prompt_is_vindia(self):
        from shared.agent.adapters import VINDIA_SYSTEM_PROMPT
        captured = {}

        async def fake(messages):
            captured["messages"] = list(messages)
            return "ok"

        asyncio.run(MistralLLM(transport=fake).reply("bonjour", session_id="s1"))
        self.assertEqual(captured["messages"][0]["role"], "system")
        self.assertEqual(captured["messages"][0]["content"], VINDIA_SYSTEM_PROMPT)
        self.assertEqual(captured["messages"][-1], {"role": "user", "content": "bonjour"})

    def test_history_accumulates_across_turns(self):
        calls = []

        async def fake(messages):
            calls.append([m.copy() for m in messages])
            return f"r{len(calls)}"

        llm = MistralLLM(transport=fake, system_prompt=None)
        asyncio.run(llm.reply("tour1", session_id="s1"))
        asyncio.run(llm.reply("tour2", session_id="s1"))

        # 2e appel : [user:tour1, assistant:r1, user:tour2]
        second = calls[1]
        self.assertEqual(second[0], {"role": "user", "content": "tour1"})
        self.assertEqual(second[1], {"role": "assistant", "content": "r1"})
        self.assertEqual(second[2], {"role": "user", "content": "tour2"})

    def test_history_bounded_by_max_history(self):
        async def fake(messages):
            return "x"

        llm = MistralLLM(transport=fake, system_prompt=None, max_history=2)
        for i in range(10):
            asyncio.run(llm.reply(f"t{i}", session_id="s1"))

        # max_history=2 → au plus 4 messages d'historique (2 tours × 2)
        history = llm._history["s1"]
        self.assertLessEqual(len(history), 4)

    def test_without_transport_fails_fast(self):
        # Pas de transport injecté + ni lib ni clé en CI → erreur claire, pas un crash obscur.
        with self.assertRaises(RuntimeError):
            asyncio.run(MistralLLM().reply("x", session_id="s1"))


class VoxtralSTTTest(unittest.TestCase):
    def test_uses_transport_with_audio_and_locale(self):
        seen = {}

        async def fake(audio, locale):
            seen["audio"] = audio
            seen["locale"] = locale
            return "transcription-mock"

        stt = VoxtralSTT(transport=fake)
        out = asyncio.run(stt.transcribe(b"PCM", "fr-FR"))

        self.assertEqual(out, "transcription-mock")
        self.assertEqual(seen, {"audio": b"PCM", "locale": "fr-FR"})

    def test_without_transport_fails_fast(self):
        with self.assertRaises(RuntimeError):
            asyncio.run(VoxtralSTT().transcribe(b"PCM", "fr-FR"))


class CallableTTSTest(unittest.TestCase):
    def test_delegates_to_transport(self):
        async def fake(text, locale):
            return b"AUDIO:" + text.encode() + b":" + locale.encode()

        out = asyncio.run(CallableTTS(fake).synthesize("salut", "fr-FR"))
        self.assertEqual(out, b"AUDIO:salut:fr-FR")


class AdaptersIntoRuntimeTest(unittest.TestCase):
    """Le vrai test d'intégration : les 3 adaptateurs branchés dans le runtime."""

    def test_full_pipeline_with_real_adapters(self):
        async def fake_stt(audio, locale):
            return f"dit[{locale}]"

        async def fake_llm(messages):
            return "réponse(" + messages[-1]["content"] + ")"

        async def fake_tts(text, locale):
            return b"SPEECH:" + text.encode()

        played = []

        class RoomOut:
            async def play(self, audio):
                played.append(audio)

        events = []
        rt = ConversationRuntime(
            VoxtralSTT(transport=fake_stt),
            MistralLLM(transport=fake_llm),
            CallableTTS(fake_tts),
            audit=lambda sid, ev, payload: events.append((sid, ev)),
        )

        async def scenario():
            desc = SessionDescriptor(
                "s1", "t1", "room-a", member_id="m1", consent_granted=True
            )
            await rt.open(desc, RoomOut())
            await rt.handle("s1", b"PCM")

        asyncio.run(scenario())

        self.assertEqual(len(played), 1)
        expected = b"SPEECH:" + "réponse(dit[fr-FR])".encode()
        self.assertEqual(played[0], expected)
        self.assertIn(("s1", "transcript"), events)
        self.assertIn(("s1", "reply"), events)


if __name__ == "__main__":
    unittest.main()
