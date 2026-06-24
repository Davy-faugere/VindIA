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


class MemoryIntegrationTest(unittest.TestCase):
    def test_memory_context_loaded_at_open(self):
        """À l'ouverture, la mémoire du membre est injectée dans le LLM."""
        injected = {}

        class TrackingLLM:
            def load_memory(self, session_id, ctx):
                injected["session_id"] = session_id
                injected["ctx"] = ctx

            async def reply(self, text, *, session_id):
                return "ok"

        class FakeMemory:
            def load_context(self, member_id):
                return f"[Mémoire de {member_id}]"

        async def scenario():
            rt = ConversationRuntime(FakeSTT(), TrackingLLM(), FakeTTS(), memory=FakeMemory())
            desc = SessionDescriptor("s1", "t1", "r", member_id="m1", consent_granted=True)
            await rt.open(desc, FakeRoomOut())

        asyncio.run(scenario())
        self.assertEqual(injected.get("session_id"), "s1")
        self.assertIn("m1", injected.get("ctx", ""))

    def test_memory_not_loaded_when_no_member(self):
        """Pas de membre résolu → pas d'injection mémoire."""
        injected = {}

        class TrackingLLM:
            def load_memory(self, session_id, ctx):
                injected["called"] = True

            async def reply(self, text, *, session_id):
                return "ok"

        class FakeMemory:
            def load_context(self, member_id):
                return "context"

        async def scenario():
            rt = ConversationRuntime(FakeSTT(), TrackingLLM(), FakeTTS(), memory=FakeMemory())
            # member_id=None → pas d'injection
            desc = SessionDescriptor("s1", "t1", "r", member_id=None, consent_granted=True)
            await rt.open(desc, FakeRoomOut())

        asyncio.run(scenario())
        self.assertNotIn("called", injected)

    def test_memory_extracted_at_close(self):
        """À la fermeture, l'historique est extrait (fire-and-forget)."""
        extracted = []

        class TrackingLLM:
            def get_history(self, session_id):
                return [{"role": "user", "content": "test"}]

            def unload_memory(self, session_id):
                pass

            async def reply(self, text, *, session_id):
                return "ok"

        class FakeMemory:
            def load_context(self, member_id):
                return ""

            async def extract_and_save(self, member_id, tenant_id, session_id, history):
                extracted.append({"mid": member_id, "n": len(history)})
                return len(history)

        async def scenario():
            rt = ConversationRuntime(FakeSTT(), TrackingLLM(), FakeTTS(), memory=FakeMemory())
            desc = SessionDescriptor("s1", "t1", "r", member_id="m1", consent_granted=True)
            await rt.open(desc, FakeRoomOut())
            rt.close("s1")
            await asyncio.sleep(0)  # donne un tick à la tâche fire-and-forget

        asyncio.run(scenario())
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0]["mid"], "m1")


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
