"""Tests MemoryStore : extraction LLM → faits → DB → injection prompt."""
import asyncio
import sqlite3
import unittest

from shared.agent.memory import MemoryStore
from shared.agent.store import Store

_SCHEMA = """
CREATE TABLE tenants (id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE members (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, display_name TEXT);
CREATE TABLE member_memories (
    id TEXT PRIMARY KEY, member_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
    source_session_id TEXT, content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_HISTORY = [
    {"role": "user", "content": "Je vends des compléments alimentaires depuis 6 mois."},
    {"role": "assistant", "content": "D'accord, comment se passe ton équipe ?"},
    {"role": "user", "content": "J'ai 5 filleuls mais j'ai du mal à les motiver."},
]


def fresh_store():
    conn = sqlite3.connect(":memory:")
    conn.executescript(_SCHEMA)
    return Store(conn, paramstyle="qmark")


class LoadContextTest(unittest.TestCase):
    def test_empty_when_no_memories(self):
        ms = MemoryStore(fresh_store(), None)
        self.assertEqual(ms.load_context("unknown"), "")

    def test_formats_block_with_header(self):
        s = fresh_store()
        tid = s.create_tenant("T")
        mid = s.create_member(tid, "Davy")
        s.save_memory(mid, tid, "sess-1", "Distributeur MLM depuis 6 mois")
        s.save_memory(mid, tid, "sess-1", "Équipe de 5 filleuls")
        ctx = MemoryStore(s, None).load_context(mid)
        self.assertTrue(ctx.startswith("[Mémoire long-terme"))
        self.assertIn("Distributeur MLM", ctx)
        self.assertIn("Équipe de 5 filleuls", ctx)


class ExtractAndSaveTest(unittest.TestCase):
    def test_extracts_and_persists_facts(self):
        s = fresh_store()
        tid = s.create_tenant("T")
        mid = s.create_member(tid, "Davy")

        async def transport(messages):
            # Vérifie que la transcription est bien passée
            self.assertIn("USER:", messages[-1]["content"])
            return '{"facts": ["Distributeur MLM depuis 6 mois", "5 filleuls difficiles à motiver"]}'

        saved = asyncio.run(MemoryStore(s, transport).extract_and_save(mid, tid, "s1", _HISTORY))
        self.assertEqual(saved, 2)
        rows = s.get_memories(mid)
        self.assertIn("Distributeur MLM depuis 6 mois", rows)

    def test_bad_json_returns_zero(self):
        s = fresh_store()
        tid = s.create_tenant("T")
        mid = s.create_member(tid, "X")

        async def transport(messages):
            return "pas du json"

        saved = asyncio.run(MemoryStore(s, transport).extract_and_save(mid, tid, "s1", _HISTORY))
        self.assertEqual(saved, 0)
        self.assertEqual(s.get_memories(mid), [])

    def test_empty_history_skips_llm_call(self):
        called = []

        async def transport(messages):
            called.append(True)
            return '{"facts": ["fait"]}'

        saved = asyncio.run(MemoryStore(fresh_store(), transport).extract_and_save("m", "t", "s", []))
        self.assertEqual(saved, 0)
        self.assertEqual(called, [])

    def test_caps_at_10_facts(self):
        s = fresh_store()
        tid = s.create_tenant("T")
        mid = s.create_member(tid, "X")

        async def transport(messages):
            return '{"facts": [' + ",".join(f'"fait {i}"' for i in range(15)) + "]}"

        saved = asyncio.run(MemoryStore(s, transport).extract_and_save(mid, tid, "s1", _HISTORY))
        self.assertEqual(saved, 10)
        self.assertEqual(len(s.get_memories(mid)), 10)

    def test_llm_error_returns_zero(self):
        s = fresh_store()
        tid = s.create_tenant("T")
        mid = s.create_member(tid, "X")

        async def failing_transport(messages):
            raise RuntimeError("réseau coupé")

        saved = asyncio.run(MemoryStore(s, failing_transport).extract_and_save(mid, tid, "s1", _HISTORY))
        self.assertEqual(saved, 0)


if __name__ == "__main__":
    unittest.main()
