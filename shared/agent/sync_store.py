"""Espace de travail synchronisé avec le poste de l'utilisateur.

L'application de bureau envoie ici les fichiers des dossiers que l'utilisateur a
désignés, et récupère ce que VindIA y crée. C'est ce qui remplace un outil de
synchronisation externe : l'échange est intégré à l'application.

Principes repris du reste du projet :
  - ISOLATION par membre : tout vit sous `<base>/<member_id>/`. Le member_id, le nom
    de dossier et le chemin relatif sont assainis — impossible de sortir de son espace.
  - Comparaison par EMPREINTE (SHA-256) : on ne retransfère que ce qui a changé,
    et la taille seule ne suffit pas à décider (deux versions peuvent peser pareil).
  - Aucune dépendance tierce.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional

_MEMBER_RE = re.compile(r"^[0-9a-fA-F-]{1,36}$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Sous-dossier où VindIA dépose ses créations (redescend chez l'utilisateur).
CREATIONS = "Créations VindIA"


def _safe_member(member_id: str) -> str:
    if not member_id or not _MEMBER_RE.match(member_id):
        raise ValueError("member_id invalide")
    return member_id


def slug_workspace(name: str) -> str:
    """Nom d'espace de travail sûr, dérivé du nom de dossier choisi sur le poste."""
    s = _SLUG_RE.sub("-", (name or "").strip().lower()).strip("-")
    return (s or "espace")[:48]


def safe_rel(rel: str) -> Optional[str]:
    """Chemin relatif accepté (sous-dossiers autorisés), ou None s'il est douteux.

    Un chemin ABSOLU est refusé, pas « rendu relatif » : une entrée suspecte doit
    être rejetée plutôt que réinterprétée silencieusement.
    """
    raw = (rel or "").strip()
    if not raw:
        return None
    if raw.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", raw):
        return None                      # chemin absolu (Unix ou Windows) : refusé
    rel = raw.replace("\\", "/")
    if rel.startswith(".") or ".." in rel.split("/"):
        return None
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    if not parts or any(p.startswith(".") for p in parts):
        return None
    return "/".join(parts)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SyncStore:
    """Espaces de travail synchronisés, isolés par membre."""

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir)

    # -- chemins ------------------------------------------------------------- #
    def _member_dir(self, member_id: str) -> Path:
        return self._base / _safe_member(member_id)

    def workspace_dir(self, member_id: str, workspace: str) -> Path:
        d = (self._member_dir(member_id) / slug_workspace(workspace)).resolve()
        root = self._member_dir(member_id).resolve()
        if root not in d.parents and d != root:
            raise ValueError("espace hors du périmètre du membre")
        return d

    def _file_path(self, member_id: str, workspace: str, rel: str) -> Optional[Path]:
        safe = safe_rel(rel)
        if safe is None:
            return None
        ws = self.workspace_dir(member_id, workspace)
        p = (ws / safe).resolve()
        if ws not in p.parents and p != ws:
            return None
        return p

    # -- opérations ---------------------------------------------------------- #
    def list_workspaces(self, member_id: str) -> List[dict]:
        root = self._member_dir(member_id)
        if not root.exists():
            return []
        out = []
        for d in sorted(root.iterdir()):
            if d.is_dir():
                meta = d / ".vindia-workspace.json"
                label = d.name
                if meta.is_file():
                    try:
                        label = json.loads(meta.read_text(encoding="utf-8")).get("label", d.name)
                    except Exception:
                        pass
                out.append({"workspace": d.name, "label": label, "files": self._count(d)})
        return out

    @staticmethod
    def _count(d: Path) -> int:
        return sum(1 for p in d.rglob("*") if p.is_file() and not p.name.startswith("."))

    def register_workspace(self, member_id: str, workspace: str, label: str) -> str:
        ws = self.workspace_dir(member_id, workspace)
        ws.mkdir(parents=True, exist_ok=True)
        (ws / ".vindia-workspace.json").write_text(
            json.dumps({"label": label or workspace}, ensure_ascii=False), encoding="utf-8"
        )
        return ws.name

    def index(self, member_id: str, workspace: str) -> Dict[str, dict]:
        """Empreinte de chaque fichier de l'espace : {chemin: {hash, size}}."""
        ws = self.workspace_dir(member_id, workspace)
        out: Dict[str, dict] = {}
        if not ws.exists():
            return out
        for p in ws.rglob("*"):
            if not p.is_file() or p.name.startswith("."):
                continue
            try:
                data = p.read_bytes()
            except Exception:
                continue
            out[str(p.relative_to(ws)).replace("\\", "/")] = {
                "hash": sha256(data), "size": len(data)
            }
        return out

    def put(self, member_id: str, workspace: str, rel: str, data: bytes) -> bool:
        p = self._file_path(member_id, workspace, rel)
        if p is None:
            return False
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return True

    def get(self, member_id: str, workspace: str, rel: str) -> Optional[bytes]:
        p = self._file_path(member_id, workspace, rel)
        if p is None or not p.is_file():
            return None
        try:
            return p.read_bytes()
        except Exception:
            return None

    def delete_workspace(self, member_id: str, workspace: str) -> bool:
        ws = self.workspace_dir(member_id, workspace)
        if not ws.exists():
            return False
        shutil.rmtree(ws, ignore_errors=True)
        return True
