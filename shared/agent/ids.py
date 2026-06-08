"""Génération/validation d'identifiants CHAR(36) (UUID v4 avec tirets).

Encodage validé : CHAR(36) — portable MariaDB <-> SQLite, lisible, aligné avec
les ID générés côté Python. (Alternative BINARY(16) écartée.)
"""

from __future__ import annotations

import re
import uuid

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def new_id() -> str:
    """Nouvel identifiant CHAR(36)."""
    return str(uuid.uuid4())


def is_valid_id(value: object) -> bool:
    """True si `value` est un UUID canonique de 36 caractères."""
    return isinstance(value, str) and len(value) == 36 and bool(_UUID_RE.match(value))
