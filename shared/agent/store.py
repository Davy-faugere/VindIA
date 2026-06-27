"""Couche d'accès données, agnostique du moteur (MariaDB en prod, SQLite en test).

Le store reçoit une connexion DB-API ; on écrit le SQL avec des placeholders `?`
et on les traduit selon le `paramstyle` (`qmark` pour sqlite3, `format` pour PyMySQL).
ID en CHAR(36) (cf. `ids.new_id`). Aucune dépendance externe ici.
"""

from __future__ import annotations

import json
from typing import Optional

from .ids import new_id


class Store:
    def __init__(self, conn: object, paramstyle: str = "qmark") -> None:
        self._conn = conn
        self._ph = "?" if paramstyle == "qmark" else "%s"

    def _q(self, sql: str) -> str:
        return sql.replace("?", self._ph)

    def _exec(self, sql: str, params: tuple = ()):  # type: ignore[no-untyped-def]
        cur = self._conn.cursor()
        cur.execute(self._q(sql), params)
        return cur

    # --- tenants / members ---
    def create_tenant(self, name: str) -> str:
        tid = new_id()
        self._exec("INSERT INTO tenants (id, name) VALUES (?, ?)", (tid, name))
        self._conn.commit()
        return tid

    def create_member(self, tenant_id: str, display_name: Optional[str] = None) -> str:
        mid = new_id()
        self._exec(
            "INSERT INTO members (id, tenant_id, display_name) VALUES (?, ?, ?)",
            (mid, tenant_id, display_name),
        )
        self._conn.commit()
        return mid

    def get_member(self, member_id: str) -> Optional[dict]:
        cur = self._exec(
            "SELECT id, tenant_id, display_name FROM members WHERE id = ?", (member_id,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {"id": row[0], "tenant_id": row[1], "display_name": row[2]}

    # --- résolution diarisation -> identité (par session, jamais l'inverse) ---
    def bind_speaker(
        self, tenant_id: str, session_id: str, speaker_id: str, member_id: str
    ) -> str:
        bid = new_id()
        self._exec(
            "INSERT INTO speaker_bindings "
            "(id, tenant_id, session_id, speaker_id, member_id) VALUES (?, ?, ?, ?, ?)",
            (bid, tenant_id, session_id, speaker_id, member_id),
        )
        self._conn.commit()
        return bid

    def resolve_member(self, session_id: str, speaker_id: str) -> Optional[str]:
        cur = self._exec(
            "SELECT member_id FROM speaker_bindings "
            "WHERE session_id = ? AND speaker_id = ?",
            (session_id, speaker_id),
        )
        row = cur.fetchone()
        return row[0] if row else None

    # --- audit append-only ---
    def record_audit(
        self, tenant_id: str, session_id: Optional[str], event_type: str, payload: dict
    ) -> str:
        aid = new_id()
        self._exec(
            "INSERT INTO audit_log (id, tenant_id, session_id, event_type, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            (aid, tenant_id, session_id, event_type, json.dumps(payload)),
        )
        self._conn.commit()
        return aid

    def audit_count(self, session_id: str) -> int:
        cur = self._exec(
            "SELECT COUNT(*) FROM audit_log WHERE session_id = ?", (session_id,)
        )
        return int(cur.fetchone()[0])

    # --- bootstrap idempotent ---
    def ensure_tenant(self, tenant_id: str, name: str) -> None:
        """INSERT ignore si le tenant existe déjà."""
        try:
            self._exec("INSERT INTO tenants (id, name) VALUES (?, ?)", (tenant_id, name))
            self._conn.commit()
        except Exception:
            pass

    def ensure_member(self, member_id: str, tenant_id: str, display_name: str) -> None:
        """INSERT ignore si le membre existe déjà."""
        try:
            self._exec(
                "INSERT INTO members (id, tenant_id, display_name) VALUES (?, ?, ?)",
                (member_id, tenant_id, display_name),
            )
            self._conn.commit()
        except Exception:
            pass

    # --- mémoire long-terme par membre ---
    def get_memories(self, member_id: str) -> list:
        cur = self._exec(
            "SELECT content FROM member_memories WHERE member_id = ? ORDER BY created_at ASC",
            (member_id,),
        )
        return [row[0] for row in cur.fetchall()]

    def list_memories(self, member_id: str) -> list:
        """Souvenirs du membre avec leur id (pour l'écran « Ma mémoire »).

        Plus récent d'abord. L'id permet à l'utilisateur d'effacer un souvenir précis.
        """
        cur = self._exec(
            "SELECT id, content, created_at FROM member_memories "
            "WHERE member_id = ? ORDER BY created_at DESC",
            (member_id,),
        )
        return [{"id": r[0], "content": r[1], "created_at": str(r[2])} for r in cur.fetchall()]

    def delete_memory(self, member_id: str, memory_id: str) -> bool:
        """Supprime UN souvenir. Le filtre member_id garantit l'isolation : un
        membre ne peut effacer que SES souvenirs, jamais ceux d'un autre."""
        cur = self._exec(
            "DELETE FROM member_memories WHERE id = ? AND member_id = ?",
            (memory_id, member_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def save_memory(
        self, member_id: str, tenant_id: str, session_id: Optional[str], content: str
    ) -> str:
        mid = new_id()
        self._exec(
            "INSERT INTO member_memories "
            "(id, member_id, tenant_id, source_session_id, content) VALUES (?, ?, ?, ?, ?)",
            (mid, member_id, tenant_id, session_id, content),
        )
        self._conn.commit()
        return mid

    def trim_memories(self, member_id: str, max_count: int) -> int:
        """Supprime les faits les plus anciens si le total dépasse max_count.

        Retourne le nombre de faits supprimés (0 si déjà sous la limite).
        Compatible SQLite et MariaDB.
        """
        cur = self._exec(
            "SELECT COUNT(*) FROM member_memories WHERE member_id = ?", (member_id,)
        )
        count = int(cur.fetchone()[0])
        to_delete = count - max_count
        if to_delete <= 0:
            return 0
        cur = self._exec(
            "SELECT id FROM member_memories WHERE member_id = ? ORDER BY created_at ASC LIMIT ?",
            (member_id, to_delete),
        )
        ids = [row[0] for row in cur.fetchall()]
        if not ids:
            return 0
        ph = ",".join(["?"] * len(ids))
        self._exec(f"DELETE FROM member_memories WHERE id IN ({ph})", tuple(ids))
        self._conn.commit()
        return len(ids)


def make_member_resolver(store: Store, session_id: str):
    """Adapte le store en résolveur (tenant_id, speaker_id) -> member_id pour la session."""

    def _resolver(_tenant_id: str, speaker_id: str) -> Optional[str]:
        return store.resolve_member(session_id, speaker_id)

    return _resolver


def make_audit_sink(store: Store, tenant_id: str):
    """Adapte le store en AuditSink (session_id, event_type, payload) -> None."""

    def _sink(session_id: str, event_type: str, payload: dict) -> None:
        store.record_audit(tenant_id, session_id, event_type, payload)

    return _sink
