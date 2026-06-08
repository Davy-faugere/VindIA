"""Connexion MariaDB de production (PyMySQL en import paresseux).

NON importé par les tests unitaires (qui utilisent sqlite3). PyMySQL n'est requis
qu'au runtime sur le VPS (cf. requirements.txt).
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse

from shared.agent.store import Store


def _dsn() -> str:
    dsn = os.environ.get("DB_DSN")
    if not dsn:
        raise RuntimeError("DB_DSN absent (cf. server/.env)")
    return dsn


def connect(dsn: Optional[str] = None):  # type: ignore[no-untyped-def]
    """Ouvre une connexion PyMySQL à partir d'un DSN mysql://user:pass@host:port/db."""
    import pymysql  # import paresseux : hors CI

    u = urlparse(dsn or _dsn())
    return pymysql.connect(
        host=u.hostname or "127.0.0.1",
        port=u.port or 3306,
        user=u.username or "vindia",
        password=u.password or "",
        database=(u.path or "/vindia").lstrip("/"),
        charset="utf8mb4",
        autocommit=False,
    )


def open_store(dsn: Optional[str] = None) -> Store:
    """Store branché sur MariaDB (paramstyle 'format' pour PyMySQL)."""
    return Store(connect(dsn), paramstyle="format")
