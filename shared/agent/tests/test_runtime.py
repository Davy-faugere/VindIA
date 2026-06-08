import asyncio
import unittest

from shared.agent.runtime import ConversationRuntime
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


if __name__ == "__main__":
    unittest.main()
