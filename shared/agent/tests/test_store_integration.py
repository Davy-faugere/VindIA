"""Test d'intégration round-trip DB réel (MariaDB) — OPT-IN.

Garde-fou CI : ce test ne s'exécute QUE si VINDIA_DB_IT=1 ET un DSN est fourni
(DB_DSN, chargé depuis server/.env). Sinon il est SKIPPÉ → la CI stdlib
0-dépendance n'est jamais cassée (ni pymysql ni MariaDB requis là-bas).

Lancement local (sur le VPS, MariaDB up) :
    set -a; . server/.env; set +a
    VINDIA_DB_IT=1 python3 -m unittest shared.agent.tests.test_store_integration -v

Il prouve que la couche Store (SQL portable, paramstyle 'format') fonctionne
réellement contre MariaDB, pas seulement contre le sqlite3 des tests unitaires.
Le test est auto-nettoyant : il supprime en fin de course tout ce qu'il a créé.
"""

import os
import unittest

_RUN_IT = os.environ.get("VINDIA_DB_IT") == "1" and bool(os.environ.get("DB_DSN"))


@unittest.skipUnless(_RUN_IT, "round-trip DB réel : poser VINDIA_DB_IT=1 + DB_DSN")
class StoreMariaDBIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from server.db import open_store  # import paresseux (pymysql hors CI)

        cls.store = open_store()  # lit DB_DSN
        cls._tenant_ids: list[str] = []

    @classmethod
    def tearDownClass(cls):
        # Nettoyage : on retire tout ce qui est rattaché aux tenants créés.
        conn = cls.store._conn
        cur = conn.cursor()
        for tid in cls._tenant_ids:
            cur.execute("DELETE FROM audit_log WHERE tenant_id = %s", (tid,))
            cur.execute("DELETE FROM speaker_bindings WHERE tenant_id = %s", (tid,))
            cur.execute("DELETE FROM members WHERE tenant_id = %s", (tid,))
            cur.execute("DELETE FROM tenants WHERE id = %s", (tid,))
        conn.commit()
        conn.close()

    def test_round_trip_tenant_member_binding_audit(self):
        store = self.store

        # tenant + member
        tid = store.create_tenant("IT-vindia")
        self._tenant_ids.append(tid)
        mid = store.create_member(tid, display_name="Membre IT")

        member = store.get_member(mid)
        self.assertIsNotNone(member)
        self.assertEqual(member["id"], mid)
        self.assertEqual(member["tenant_id"], tid)
        self.assertEqual(member["display_name"], "Membre IT")

        # ID en CHAR(36) : longueur attendue
        self.assertEqual(len(mid), 36)

        # résolution diarisation -> identité (par session, jamais l'inverse)
        session_id = "it-session-1"
        store.bind_speaker(tid, session_id, "speaker-A", mid)
        self.assertEqual(store.resolve_member(session_id, "speaker-A"), mid)
        self.assertIsNone(store.resolve_member(session_id, "speaker-inconnu"))

        # audit append-only
        store.record_audit(tid, session_id, "transcript", {"text": "bonjour"})
        store.record_audit(tid, session_id, "reply", {"text": "salut"})
        self.assertEqual(store.audit_count(session_id), 2)


if __name__ == "__main__":
    unittest.main()
