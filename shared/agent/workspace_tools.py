"""Outils « dossiers de l'ordinateur » — VindIA lit et écrit les dossiers synchronisés.

L'application de bureau envoie les dossiers choisis par l'utilisateur dans son
SyncStore. Sans ces outils, ces fichiers étaient stockés mais INVISIBLES pour
VindIA : elle ne pouvait ni les lister, ni les lire. C'est ce que ce module ouvre.

Deux principes repris du reste du projet :

  - RÉFÉRENCE, PAS CHARGEMENT. On n'injecte jamais le contenu d'un dossier dans le
    contexte : VindIA voit la liste et lit à la demande. Un dossier de 500 fichiers
    reste donc utilisable.
  - ISOLATION PAR CONSTRUCTION. `member_id` est figé à la construction, et la liste
    des dossiers autorisés aussi. Le LLM ne fournit qu'un nom de dossier ; s'il
    n'est pas dans la liste autorisée, l'accès est refusé — le modèle ne peut donc
    pas atteindre un autre membre, ni un dossier hors du projet actif.

0 dépendance tierce au chargement.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence

from .projects import ExtractionError, extract_text
from .sync_store import SyncStore, slug_workspace
from .tools import Tool, ToolSpec

# Extensions livrées en VRAI binaire bureautique (sinon le fichier serait illisible).


class _WorkspaceTool(Tool):
    """Base commune : résout le dossier demandé parmi ceux autorisés."""

    def __init__(self, sync: SyncStore, member_id: str, allowed: Optional[Sequence[str]] = None) -> None:
        self._sync = sync
        self._member_id = member_id
        # None = tous les dossiers du membre ; une liste = restreint (projet actif).
        self._allowed = [slug_workspace(a) for a in allowed] if allowed is not None else None

    def _available(self) -> List[dict]:
        listed = self._sync.list_workspaces(self._member_id)
        if self._allowed is None:
            return listed
        return [w for w in listed if w["workspace"] in self._allowed]

    def _resolve(self, folder: str):
        """(slug, None) si le dossier est utilisable, sinon (None, message d'erreur)."""
        available = self._available()
        if not available:
            return None, (
                "Aucun dossier de l'ordinateur n'est disponible. L'utilisateur doit en "
                "ajouter un depuis l'application VindIA sur son ordinateur."
            )
        wanted = (folder or "").strip()
        if not wanted:
            if len(available) == 1:
                return available[0]["workspace"], None
            noms = ", ".join(f"« {w['label']} »" for w in available)
            return None, f"Précise le dossier. Disponibles : {noms}."
        slug = slug_workspace(wanted)
        for w in available:
            if w["workspace"] == slug:
                return slug, None
        noms = ", ".join(f"« {w['label']} »" for w in available)
        return None, f"Dossier « {wanted} » introuvable ou non rattaché. Disponibles : {noms}."


class FolderListTool(_WorkspaceTool):
    """Liste les dossiers disponibles, ou les fichiers de l'un d'eux."""

    def __init__(self, sync, member_id, allowed=None, *, max_files: int = 300) -> None:
        super().__init__(sync, member_id, allowed)
        self._max = max_files
        self.spec = ToolSpec(
            name="folder_list_files",
            description=(
                "Liste les fichiers d'un dossier de l'ordinateur de l'utilisateur "
                "(dossiers synchronisés via l'application VindIA). Sans argument, "
                "liste les dossiers disponibles. À utiliser AVANT de lire un fichier."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": "Nom du dossier. Omets-le pour voir les dossiers disponibles.",
                    }
                },
            },
        )

    async def run(self, args: dict) -> str:
        available = self._available()
        if not available:
            return (
                "Aucun dossier de l'ordinateur n'est disponible. L'utilisateur doit en "
                "ajouter un depuis l'application VindIA sur son ordinateur."
            )
        folder = (args.get("folder") or "").strip()
        # Plusieurs dossiers et aucun précisé : on montre le sommaire, pas une erreur.
        if not folder and len(available) > 1:
            lignes = [f"- {w['label']} ({w['files']} fichier(s))" for w in available]
            return "Dossiers disponibles :\n" + "\n".join(lignes)
        slug, err = self._resolve(folder)
        if err:
            return err
        index = self._sync.index(self._member_id, slug)
        if not index:
            return f"Le dossier « {folder or slug} » est vide."
        noms = sorted(index)
        tronque = len(noms) > self._max
        lignes = [f"- {n}" for n in noms[: self._max]]
        if tronque:
            lignes.append(f"… ({len(noms) - self._max} fichiers supplémentaires non listés)")
        return f"Dossier « {folder or slug} » — {len(noms)} fichier(s) :\n" + "\n".join(lignes)


class FolderReadTool(_WorkspaceTool):
    """Lit un fichier d'un dossier de l'ordinateur, à la demande."""

    def __init__(self, sync, member_id, allowed=None, *, max_chars: int = 8000) -> None:
        super().__init__(sync, member_id, allowed)
        self._max_chars = max_chars
        self.spec = ToolSpec(
            name="folder_read_file",
            description=(
                "Lit le contenu d'un fichier d'un dossier de l'ordinateur de "
                "l'utilisateur (texte, Word, Excel, PowerPoint, PDF). Utilise d'abord "
                "folder_list_files pour connaître le chemin exact."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Chemin relatif du fichier dans le dossier."},
                    "folder": {"type": "string", "description": "Nom du dossier (inutile s'il n'y en a qu'un)."},
                },
                "required": ["filename"],
            },
        )

    async def run(self, args: dict) -> str:
        filename = (args.get("filename") or "").strip()
        if not filename:
            return "Erreur : nom de fichier manquant."
        slug, err = self._resolve(args.get("folder") or "")
        if err:
            return err
        data = self._sync.get(self._member_id, slug, filename)
        if data is None:
            return f"Fichier introuvable : « {filename} »."
        try:
            text = extract_text(Path(filename).name, data)
        except ExtractionError as exc:
            return f"Format non lisible : {exc}"
        except Exception as exc:  # noqa: BLE001 - un fichier corrompu ne casse pas la conversation
            return f"Lecture impossible : {str(exc)[:160]}"
        if not text.strip():
            return "Le fichier ne contient pas de texte exploitable."
        if len(text) > self._max_chars:
            text = text[: self._max_chars].rstrip() + " […]"
        return text


def build_workspace_tools(
    sync: SyncStore, member_id: str, allowed: Optional[Sequence[str]] = None
) -> List[Tool]:
    """Outils de CONSULTATION liés à CE membre (et, si fourni, à CES dossiers seulement).

    L'écriture a été retirée le 24/08/2026. Elle déposait le fichier sous
    `vindia-data/workspaces/…`, que rien ne synchronise : le fichier existait bel et
    bien sur le serveur, mais n'atteignait jamais l'ordinateur de la personne. VindIA
    annonçait donc en toute bonne foi un document que son destinataire ne trouvait
    nulle part — cinq livrables ont été perdus ainsi entre le 16 et le 23/08.

    La livraison passe désormais par un seul chemin, valable pour TOUS les membres :
    le marqueur [[FICHIER:nom.ext]], que la page convertit en téléchargement. Les
    dossiers restent consultables (lister, lire) — c'est leur usage réel.
    """
    return [
        FolderListTool(sync, member_id, allowed),
        FolderReadTool(sync, member_id, allowed),
    ]
