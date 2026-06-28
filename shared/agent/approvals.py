"""Validation humaine des comptes : un utilisateur inscrit attend l'aval de l'admin.

Flux : un membre se connecte (auth Supabase OK) → s'il n'est pas encore connu, il
passe en « pending » et l'admin est notifié. Tant qu'il n'est pas « approved », les
fonctions de VindIA lui sont refusées. L'admin (Davy) approuve ou refuse.

Stockage sur DISQUE (comme projets/coffre) → aucun changement du schéma MariaDB.
Un fichier JSON par membre : `<base>/<member_id>.json`. member_id assaini (les ids
Supabase sont des UUID) pour éviter toute traversée de chemin.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, List, Optional, Tuple

PENDING, APPROVED, REFUSED = "pending", "approved", "refused"

_MEMBER_RE = re.compile(r"^[0-9a-fA-F-]{1,36}$")


def _safe_member(member_id: str) -> str:
    if not member_id or not _MEMBER_RE.match(member_id):
        raise ValueError("member_id invalide")
    return member_id


def _default_clock() -> str:  # pragma: no cover - dépend de l'heure réelle
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


class ApprovalStore:
    """Statut d'approbation par membre, persistant sur disque."""

    def __init__(self, base_dir: str, *, clock: Optional[Callable[[], str]] = None) -> None:
        self._base = Path(base_dir)
        self._clock = clock or _default_clock

    def _path(self, member_id: str) -> Path:
        return self._base / f"{_safe_member(member_id)}.json"

    def get(self, member_id: str) -> Optional[dict]:
        p = self._path(member_id)
        if not p.is_file():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def status(self, member_id: str) -> str:
        rec = self.get(member_id)
        return rec["status"] if rec else "unknown"

    def request(self, member_id: str, email: str) -> Tuple[str, bool]:
        """Enregistre la demande au 1er passage. Retourne (statut, est_nouveau).

        Idempotent : un membre déjà connu garde son statut (et est_nouveau=False),
        ce qui évite de re-notifier l'admin à chaque connexion.
        """
        existing = self.get(member_id)
        if existing is not None:
            return existing["status"], False
        self._base.mkdir(parents=True, exist_ok=True)
        ts = self._clock()
        rec = {
            "member_id": member_id,
            "email": email or "",
            "status": PENDING,
            "requested_at": ts,
            "decided_at": None,
        }
        self._path(member_id).write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        return PENDING, True

    def decide(self, member_id: str, approved: bool) -> bool:
        """Approuve ou refuse un membre. Retourne True si le membre existait."""
        rec = self.get(member_id)
        if rec is None:
            return False
        rec["status"] = APPROVED if approved else REFUSED
        rec["decided_at"] = self._clock()
        self._path(member_id).write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        return True

    def list_by_status(self, status: str) -> List[dict]:
        if not self._base.exists():
            return []
        out = []
        for f in sorted(self._base.glob("*.json")):
            rec = json.loads(f.read_text(encoding="utf-8"))
            if rec.get("status") == status:
                out.append(rec)
        return out
