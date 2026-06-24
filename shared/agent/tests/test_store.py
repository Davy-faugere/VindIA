import sqlite3
import unittest

from shared.agent.ids import is_valid_id
from shared.agent.store import Store, make_audit_sink, make_member_resolver

# Schéma SQLite minimal, miroir de db/01-schema.sql + db/02-memories.sql.
_SQLITE_SCHEMA = """
CREATE TABLE tenants (id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE members (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, display_name TEXT);
CREATE TABLE speaker_bindings (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, session_id TEXT NOT NULL,
  speaker_id TEXT NOT NULL, member_id TEXT NOT NULL,
  UNIQUE(session_id, speaker_id)
);
CREATE TABLE audit_log (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, session_id TEXT,
  event_type TEXT NOT NULL, payload TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE member_memories (
  id TEXT PRIMARY KEY, member_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
  source_session_id TEXT, content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def fresh_store():
    conn = sqlite3.connect(":memory:")
    conn.executescript(_SQLITE_SCHEMA)
    return Store(conn, paramstyle="qmark")


class StoreTest(unittest.TestCase):
    def test_create_tenant_and_member_returns_char36(self):
        s = fresh_store()
        tid = s.create_tenant("ACME")
        mid = s.create_member(tid, "Alice")
        self.assertTrue(is_valid_id(tid))
        self.assertTrue(is_valid_id(mid))
        self.assertEqual(s.get_member(mid)["display_name"], "Alice")

    def test_get_member_unknown_is_none(self):
        self.assertIsNone(fresh_store().get_member("nope"))

    def test_speaker_binding_resolves_to_member(self):
        s = fresh_store()
        tid = s.create_tenant("ACME")
        mid = s.create_member(tid, "Alice")
        s.bind_speaker(tid, "sess-1", "speaker-0", mid)
        self.assertEqual(s.resolve_member("sess-1", "speaker-0"), mid)
        # Pas de fuite inter-session ni speaker inconnu.
        self.assertIsNone(s.resolve_member("sess-2", "speaker-0"))
        self.assertIsNone(s.resolve_member("sess-1", "speaker-9"))

    def test_member_resolver_adapter(self):
        s = fresh_store()
        tid = s.create_tenant("ACME")
        mid = s.create_member(tid)
        s.bind_speaker(tid, "sess-1", "speaker-0", mid)
        resolver = make_member_resolver(s, "sess-1")
        self.assertEqual(resolver(tid, "speaker-0"), mid)

    def test_audit_sink_appends_rows(self):
        s = fresh_store()
        tid = s.create_tenant("ACME")
        sink = make_audit_sink(s, tid)
        sink("sess-1", "transcript", {"text": "bonjour"})
        sink("sess-1", "reply", {"text": "salut"})
        self.assertEqual(s.audit_count("sess-1"), 2)
        self.assertEqual(s.audit_count("sess-x"), 0)

    def test_save_and_get_memories(self):
        s = fresh_store()
        tid = s.create_tenant("ACME")
        mid = s.create_member(tid, "Davy")
        s.save_memory(mid, tid, "sess-1", "Distributeur MLM depuis 6 mois")
        s.save_memory(mid, tid, "sess-1", "Équipe de 5 filleuls")
        rows = s.get_memories(mid)
        self.assertEqual(len(rows), 2)
        self.assertIn("Distributeur MLM depuis 6 mois", rows)

    def test_get_memories_empty_for_unknown_member(self):
        self.assertEqual(fresh_store().get_memories("inconnu"), [])


if __name__ == "__main__":
    unittest.main()
