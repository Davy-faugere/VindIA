import asyncio
import unittest

from shared.agent.runtime import ConversationRuntime, _clean_for_tts
from shared.agent.session import SessionDescriptor


class FakeSTT:
    async def transcribe(self, audio, locale):
        return f"texte[{locale}]:{audio!r}"


class FakeLLM:
    async def reply(self, text, *, session_id):
        return f"réponse({text})"


class FakeTTS:
    async def synthesize(self, text, locale):
        return ("AUDIO", text, locale)


class FakeRoomOut:
    def __init__(self):
        self.played = []

    async def play(self, audio):
        self.played.append(audio)


def runtime_with_audit():
    events = []
    rt = ConversationRuntime(
        FakeSTT(), FakeLLM(), FakeTTS(),
        audit=lambda sid, ev, payload: events.append((sid, ev)),
    )
    return rt, events


class ConversationRuntimeTest(unittest.TestCase):
    def _consenting_session(self):
        return SessionDescriptor(
            "s1", "t1", "room-a", member_id="m1", consent_granted=True
        )

    def test_full_pipeline_plays_synthesized_reply(self):
        rt, events = runtime_with_audit()
        out = FakeRoomOut()

        async def scenario():
            await rt.open(self._consenting_session(), out)
            await rt.handle("s1", b"PCM")

        asyncio.run(scenario())
        self.assertEqual(len(out.played), 1)
        audio, text, locale = out.played[0]
        self.assertEqual(audio, "AUDIO")
        self.assertIn("réponse(", text)
        self.assertEqual(locale, "fr-FR")
        self.assertIn(("s1", "transcript"), events)
        self.assertIn(("s1", "reply"), events)

    def test_no_consent_skips_pipeline(self):
        rt, events = runtime_with_audit()
        out = FakeRoomOut()
        desc = SessionDescriptor("s2", "t1", "room-b", member_id="m1", consent_granted=False)

        async def scenario():
            await rt.open(desc, out)
            await rt.handle("s2", b"PCM")

        asyncio.run(scenario())
        self.assertEqual(out.played, [])
        self.assertIn(("s2", "utterance_skipped_no_consent"), events)

    def test_unknown_session_is_noop(self):
        rt, _ = runtime_with_audit()
        asyncio.run(rt.handle("ghost", b"PCM"))  # ne lève pas

    def test_close_emits_and_unregisters(self):
        rt, events = runtime_with_audit()
        out = FakeRoomOut()

        async def scenario():
            await rt.open(self._consenting_session(), out)
            rt.close("s1")
            await rt.handle("s1", b"PCM")  # session fermée → no-op

        asyncio.run(scenario())
        self.assertEqual(out.played, [])
        self.assertIn(("s1", "session_closed"), events)


class CleanForTTSTest(unittest.TestCase):
    def test_strips_bold(self):
        self.assertEqual(_clean_for_tts("Voici **important** ici."), "Voici important ici.")

    def test_strips_italic(self):
        self.assertEqual(_clean_for_tts("mot *accentué* là."), "mot accentué là.")

    def test_strips_heading(self):
        self.assertEqual(_clean_for_tts("## Titre principal"), "Titre principal")

    def test_strips_list_dash(self):
        self.assertEqual(_clean_for_tts("- item un\n- item deux"), "item un\nitem deux")

    def test_strips_numbered_list(self):
        self.assertEqual(_clean_for_tts("1. premier\n2. deuxième"), "premier\ndeuxième")

    def test_strips_inline_code(self):
        self.assertEqual(_clean_for_tts("utilise `print()` ici"), "utilise print() ici")

    def test_strips_link(self):
        self.assertEqual(_clean_for_tts("voir [le site](https://example.com)"), "voir le site")

    def test_plain_text_unchanged(self):
        text = "Bonjour, comment puis-je vous aider ?"
        self.assertEqual(_clean_for_tts(text), text)

    def test_tts_text_reaches_synth(self):
        """Le texte nettoyé (pas le brut LLM) arrive au TTS."""
        synthesized = []

        class FakeLLMMarkdown:
            async def reply(self, text, *, session_id):
                return "## Résultat\n- **point un**\n- point deux"

        class FakeSTT:
            async def transcribe(self, audio, locale):
                return "question"

        class FakeTTS:
            async def synthesize(self, text, locale):
                synthesized.append(text)
                return b""

        class FakeRoomOut:
            async def play(self, audio): pass

        async def scenario():
            rt = ConversationRuntime(FakeSTT(), FakeLLMMarkdown(), FakeTTS())
            desc = SessionDescriptor("s1", "t1", "r", member_id="m1", consent_granted=True)
            await rt.open(desc, FakeRoomOut())
            await rt.handle("s1", b"PCM")

        asyncio.run(scenario())
        self.assertEqual(len(synthesized), 1)
        self.assertNotIn("**", synthesized[0])
        self.assertNotIn("##", synthesized[0])
        self.assertIn("Résultat", synthesized[0])


if __name__ == "__main__":
    unittest.main()
