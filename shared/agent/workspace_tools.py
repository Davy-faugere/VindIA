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

from .officegen import OFFICE_TYPES as _A_CONSTRUIRE
from .projects import ExtractionError, extract_text, safe_filename
from .sync_store import CREATIONS, SyncStore, slug_workspace
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


class FolderWriteTool(_WorkspaceTool):
    """Crée un fichier dans « Créations VindIA » — le dossier de l'ordinateur.

    RÉTABLI le 24/08/2026 après avoir été retiré par erreur le matin même. Le retrait
    partait d'un constat juste (des fichiers restaient sur le serveur) mais d'une
    conclusion fausse : ce chemin n'était pas un cul-de-sac, c'est LE chemin qui mène
    à l'ordinateur de la personne. L'application de bureau descend ensuite ces fichiers
    dans le dossier qu'elle a choisi — sans Syncthing, sans service tiers.
    """

    def __init__(self, sync, member_id, allowed=None, *, office_builder=None) -> None:
        super().__init__(sync, member_id, allowed)
        self._office_builder = office_builder
        self.spec = ToolSpec(
            name="folder_write_file",
            description=(
                "Crée un document dans le dossier de l'utilisateur, sur SON ordinateur "
                "(sous-dossier « Créations VindIA »). C'est le chemin à privilégier "
                "pour livrer un document : rapport, compte-rendu, note, tableau. "
                "Formats : .docx, .xlsx, .pptx, .pdf, .odt, .ods, .md, .txt, .csv…"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Nom du fichier, ex. compte-rendu.docx"},
                    "content": {"type": "string", "description": "Contenu complet du document."},
                    "folder": {"type": "string", "description": "Dossier de destination (inutile s'il n'y en a qu'un)."},
                },
                "required": ["filename", "content"],
            },
        )

    async def run(self, args: dict) -> str:
        filename = safe_filename(args.get("filename") or "")
        content = args.get("content") or ""
        if not content.strip():
            return "Erreur : contenu vide, rien à écrire."
        slug, err = self._resolve(args.get("folder") or "")
        if err:
            return err
        rel = f"{CREATIONS}/{filename}"
        ext = Path(filename).suffix.lower().lstrip(".")
        # Liste LUE d'officegen, jamais recopiée : c'est une liste figée ici qui avait
        # laissé passer .odt et .ods en markdown brut.
        if ext in _A_CONSTRUIRE:
            builder = self._office_builder or _default_office_builder
            try:
                # base_dir = le dossier de la personne → ses images sont trouvables.
                base = str(self._sync.workspace_dir(self._member_id, slug))
                payload, _ = builder(filename, content, base)
            except Exception as exc:  # noqa: BLE001
                return f"Génération du fichier impossible : {str(exc)[:160]}"
        else:
            # Transparence IA (AI Act art. 50) : marquage en tête des fichiers texte.
            from .officegen import AI_NOTICE

            marked = content if content.startswith(AI_NOTICE) else f"{AI_NOTICE}\n\n{content}"
            payload = marked.encode("utf-8")
        if not self._sync.put(self._member_id, slug, rel, payload):
            return "Écriture refusée : nom de fichier invalide."
        return (
            f"Fichier « {filename} » créé dans « {CREATIONS} ». Il arrive sur "
            "l'ordinateur de la personne à la prochaine synchronisation de "
            "l'application de bureau."
        )


def _default_office_builder(name: str, content: str, base_dir=None):  # pragma: no cover
    from .officegen import build_file

    return build_file(name, content, base_dir)


def build_workspace_tools(
    sync: SyncStore, member_id: str, allowed: Optional[Sequence[str]] = None
) -> List[Tool]:
    """Outils de dossier liés à CE membre (et, si fourni, à CES dossiers seulement).

    L'écriture était le chemin qui mène à l'ordinateur de la personne : VindIA écrit
    ici, l'application de bureau descend le fichier dans le dossier qu'elle a choisi.
    Retirée par erreur le 24/08/2026, rétablie le jour même.
    """
    return [
        FolderListTool(sync, member_id, allowed),
        FolderReadTool(sync, member_id, allowed),
        FolderWriteTool(sync, member_id, allowed),
    ]
