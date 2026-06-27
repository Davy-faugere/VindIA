"""Outils « espace de travail projet » — VindIA travaille un dossier comme Claude.

Au lieu d'avaler tout le contenu d'un projet dans le contexte (ce qui sature et
ne passe pas à l'échelle), VindIA reçoit seulement la LISTE des fichiers et les
consulte À LA DEMANDE via ces outils. Elle peut aussi ÉCRIRE — créer un document
qui reste dans le dossier (le « point de contrôle » de l'utilisateur).

ISOLATION : chaque outil est construit pour UN (member_id, project_id) précis,
figés à la construction. Le LLM ne fournit qu'un nom de fichier ; il ne peut donc
jamais désigner l'espace d'un autre membre ni un autre projet. Le ProjectStore
assainit en plus le nom de fichier (anti path-traversal).

0 dépendance tierce au chargement (réutilise Tool/ToolSpec de tools.py et le
ProjectStore) → testable offline.
"""

from __future__ import annotations

from typing import List

from .projects import ProjectStore
from .tools import Tool, ToolSpec


class ListProjectFilesTool(Tool):
    """Liste les fichiers du projet actif (noms + taille en caractères)."""

    def __init__(self, store: ProjectStore, member_id: str, project_id: str) -> None:
        self._store = store
        self._member_id = member_id
        self._project_id = project_id
        self.spec = ToolSpec(
            name="list_project_files",
            description=(
                "Liste les fichiers du projet de référence actif. À utiliser pour "
                "savoir ce qui est disponible avant d'en lire un."
            ),
            parameters={"type": "object", "properties": {}},
        )

    async def run(self, args: dict) -> str:
        proj = self._store.get_project(self._member_id, self._project_id)
        if proj is None:
            return "Aucun projet actif."
        if not proj.documents:
            return "Le projet est vide (aucun fichier)."
        lines = [f"Projet « {proj.name} » — {len(proj.documents)} fichier(s) :"]
        for d in proj.documents:
            lines.append(f"- {d.filename} ({d.chars} caractères)")
        return "\n".join(lines)


class ReadProjectFileTool(Tool):
    """Lit le contenu d'un fichier du projet actif, à la demande."""

    def __init__(self, store: ProjectStore, member_id: str, project_id: str, *, max_chars: int = 8000) -> None:
        self._store = store
        self._member_id = member_id
        self._project_id = project_id
        self._max_chars = max_chars
        self.spec = ToolSpec(
            name="read_project_file",
            description=(
                "Lit le contenu d'un fichier du projet (utilise d'abord "
                "list_project_files pour connaître les noms exacts)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Nom exact du fichier à lire."}
                },
                "required": ["filename"],
            },
        )

    async def run(self, args: dict) -> str:
        filename = (args.get("filename") or "").strip()
        if not filename:
            return "Erreur : nom de fichier manquant."
        text = self._store.read_document(self._member_id, self._project_id, filename)
        if not text:
            return f"Fichier introuvable ou vide : « {filename} »."
        if len(text) > self._max_chars:
            text = text[: self._max_chars].rstrip() + " […]"
        return text


class WriteProjectFileTool(Tool):
    """Crée ou remplace un fichier dans le projet (il y reste = point de contrôle)."""

    def __init__(self, store: ProjectStore, member_id: str, project_id: str) -> None:
        self._store = store
        self._member_id = member_id
        self._project_id = project_id
        self.spec = ToolSpec(
            name="write_project_file",
            description=(
                "Crée ou met à jour un fichier texte/markdown dans le projet. À "
                "utiliser quand l'utilisateur demande de rédiger, créer ou enregistrer "
                "un document (note, compte-rendu, plan, fichier .md…). Le fichier est "
                "conservé dans le dossier du projet."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Nom du fichier, ex. notes.md"},
                    "content": {"type": "string", "description": "Contenu texte complet du fichier."},
                },
                "required": ["filename", "content"],
            },
        )

    async def run(self, args: dict) -> str:
        filename = (args.get("filename") or "").strip()
        content = args.get("content") or ""
        if not filename:
            return "Erreur : nom de fichier manquant."
        if not content.strip():
            return "Erreur : contenu vide, rien à écrire."
        if self._store.get_project(self._member_id, self._project_id) is None:
            return "Aucun projet actif où écrire."
        doc = self._store.add_document(self._member_id, self._project_id, filename, content)
        return f"Fichier « {doc.filename} » enregistré dans le projet ({doc.chars} caractères)."


def build_project_tools(store: ProjectStore, member_id: str, project_id: str) -> List[Tool]:
    """Trio d'outils projet liés à CE membre et CE projet (isolation par construction)."""
    return [
        ListProjectFilesTool(store, member_id, project_id),
        ReadProjectFileTool(store, member_id, project_id),
        WriteProjectFileTool(store, member_id, project_id),
    ]
