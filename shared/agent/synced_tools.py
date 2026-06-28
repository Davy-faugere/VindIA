"""Accès en LECTURE au dossier synchronisé depuis le PC (via Syncthing).

L'utilisateur synchronise un dossier de son PC vers le VPS (Syncthing). VindIA peut
alors LIRE ces fichiers à la demande — comme s'ils étaient « locaux ». Lecture seule :
VindIA ne modifie jamais le dossier (et le folder Syncthing est en réception côté VPS,
donc rien ne redescend sur le PC).

Réservé à l'admin (un seul dossier synchronisé pour l'instant = celui du propriétaire).
Garde-fou : tout chemin demandé est résolu et DOIT rester sous le dossier racine
(anti path-traversal). 0 dépendance tierce au chargement.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from .projects import ExtractionError, extract_text
from .tools import Tool, ToolSpec

# Fichiers internes Syncthing à masquer.
_HIDDEN = {".stfolder", ".stignore", ".stversions"}


def _safe_under(base: Path, rel: str) -> Path:
    """Résout `rel` sous `base`, en refusant toute sortie du dossier (traversal)."""
    base = base.resolve()
    target = (base / rel.lstrip("/")).resolve()
    if target != base and base not in target.parents:
        raise ValueError("chemin hors du dossier synchronisé")
    return target


class SyncedListTool(Tool):
    """Liste les fichiers du dossier PC synchronisé (récursif, chemins relatifs)."""

    def __init__(self, base_dir: str, *, max_files: int = 200) -> None:
        self._base = Path(base_dir)
        self._max = max_files
        self.spec = ToolSpec(
            name="synced_list_files",
            description=(
                "Liste les fichiers du dossier de l'ordinateur synchronisé avec VindIA "
                "(les fichiers locaux de l'utilisateur). À utiliser avant d'en lire un."
            ),
            parameters={"type": "object", "properties": {}},
        )

    async def run(self, args: dict) -> str:
        if not self._base.exists():
            return "Aucun dossier synchronisé pour l'instant."
        files: List[str] = []
        for p in sorted(self._base.rglob("*")):
            if p.is_file() and not any(part in _HIDDEN for part in p.parts):
                files.append(str(p.relative_to(self._base)))
                if len(files) >= self._max:
                    files.append("… (liste tronquée)")
                    break
        if not files:
            return "Le dossier synchronisé est vide."
        return "Fichiers du dossier PC synchronisé :\n" + "\n".join(f"- {f}" for f in files)


class SyncedReadTool(Tool):
    """Lit un fichier du dossier PC synchronisé (à la demande)."""

    def __init__(self, base_dir: str, *, max_chars: int = 8000) -> None:
        self._base = Path(base_dir)
        self._max_chars = max_chars
        self.spec = ToolSpec(
            name="synced_read_file",
            description=(
                "Lit le contenu d'un fichier du dossier PC synchronisé (utilise d'abord "
                "synced_list_files pour le nom exact)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Chemin relatif du fichier."}
                },
                "required": ["filename"],
            },
        )

    async def run(self, args: dict) -> str:
        filename = (args.get("filename") or "").strip()
        if not filename:
            return "Erreur : nom de fichier manquant."
        try:
            path = _safe_under(self._base, filename)
        except ValueError:
            return "Erreur : chemin refusé."
        if not path.is_file():
            return f"Fichier introuvable : « {filename} »."
        try:
            text = extract_text(path.name, path.read_bytes())
        except ExtractionError as exc:
            return f"Format non lisible : {exc}"
        except Exception as exc:  # noqa: BLE001
            return f"Lecture impossible : {str(exc)[:160]}"
        if not text.strip():
            return "Le fichier ne contient pas de texte exploitable."
        if len(text) > self._max_chars:
            text = text[: self._max_chars].rstrip() + " […]"
        return text


def build_synced_tools(base_dir: str) -> List[Tool]:
    """Outils de lecture du dossier synchronisé (liste + lecture)."""
    return [SyncedListTool(base_dir), SyncedReadTool(base_dir)]
