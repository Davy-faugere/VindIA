import asyncio
import unittest

from shared.agent.audio.livekit_io import (
    HalfDuplexGate,
    LiveKitAudioBridge,
    RoomSessionRegistry,
)


class RoomSessionRegistryTest(unittest.TestCase):
    def test_bind_and_lookup_both_directions(self):
        reg = RoomSessionRegistry()
        reg.bind("room-a", "sess-1")
        self.assertEqual(reg.session_for("room-a"), "sess-1")
        self.assertEqual(reg.room_for("sess-1"), "room-a")

    def test_rebind_same_session_is_ok(self):
        reg = RoomSessionRegistry()
        reg.bind("room-a", "sess-1")
        reg.bind("room-a", "sess-1")  # idempotent
        self.assertEqual(reg.session_for("room-a"), "sess-1")

    def test_rebind_conflicting_session_raises(self):
        reg = RoomSessionRegistry()
        reg.bind("room-a", "sess-1")
        with self.assertRaises(ValueError):
            reg.bind("room-a", "sess-2")

    def test_unbind_clears_both_directions(self):
        reg = RoomSessionRegistry()
        reg.bind("room-a", "sess-1")
        reg.unbind("room-a")
        self.assertIsNone(reg.session_for("room-a"))
        self.assertIsNone(reg.room_for("sess-1"))

    def test_speaker_id_never_falls_back_to_identity(self):
        # Sans résolveur, un speaker inconnu ne devient PAS une identité.
        reg = RoomSessionRegistry()
        self.assertIsNone(reg.resolve_member("tenant-x", "speaker-0"))

    def test_member_resolver_maps_speaker_to_member(self):
        table = {("tenant-x", "speaker-0"): "member-42"}
        reg = RoomSessionRegistry(member_resolver=lambda t, s: table.get((t, s)))
        self.assertEqual(reg.resolve_member("tenant-x", "speaker-0"), "member-42")
        self.assertIsNone(reg.resolve_member("tenant-x", "speaker-9"))


class HalfDuplexGateTest(unittest.TestCase):
    def test_capture_suspended_while_agent_speaks(self):
        gate = HalfDuplexGate()
        self.assertTrue(gate.should_capture())
        gate.agent_started()
        self.assertFalse(gate.should_capture())
        gate.agent_stopped()
        self.assertTrue(gate.should_capture())


class BridgeEmitTest(unittest.TestCase):
    def test_emit_routes_to_callback_with_session_id(self):
        reg = RoomSessionRegistry()
        reg.bind("room-a", "sess-1")
        bridge = LiveKitAudioBridge(reg)
        seen = []

        async def cb(session_id, audio):
            seen.append((session_id, audio))

        bridge.on_utterance = cb
        asyncio.run(bridge._emit("room-a", b"AUDIO"))
        self.assertEqual(seen, [("sess-1", b"AUDIO")])

    def test_emit_noop_when_room_unknown(self):
        bridge = LiveKitAudioBridge(RoomSessionRegistry())
        seen = []
        bridge.on_utterance = lambda s, a: seen.append((s, a))  # type: ignore
        asyncio.run(bridge._emit("ghost-room", b"AUDIO"))
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()
