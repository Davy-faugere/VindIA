"""Compétences (« skills ») : le savoir-faire méthodique de VindIA.

Un modèle de langage sait rédiger, mais il ne sait pas comment TOI tu veux que les
choses soient faites. Une compétence est une fiche de méthode — comment structurer
un compte-rendu, quoi vérifier avant de livrer un tableur, comment mener un cours
d'anglais. VindIA en reçoit la LISTE dans son contexte et lit la fiche utile À LA
DEMANDE, exactement comme pour les fichiers d'un projet : le contexte reste court
même avec cinquante compétences.

Deux origines :
  - LIVRÉES avec l'application (`shared/agent/skills/*.md`), versionnées avec le code ;
  - PROPRES à l'utilisateur, écrites par lui ou dictées à VindIA, rangées sous
    `<base>/<member_id>/`. Une compétence personnelle de même nom REMPLACE la version
    livrée : l'utilisateur garde le dernier mot sur sa méthode.

Format d'une fiche (volontairement minimal, lisible et éditable à la main) :

    # Titre lisible
    > Une phrase qui dit quand s'en servir.

    Le corps de la méthode…

0 dépendance tierce.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

_MEMBER_RE = re.compile(r"^[0-9a-fA-F-]{1,36}$")
_NAME_RE = re.compile(r"[^a-z0-9]+")

# Bornes : une fiche est une méthode, pas un livre.
MAX_SKILL_CHARS = 12000


def safe_name(name: str) -> str:
    """Nom de fichier sûr pour une compétence (a-z0-9-, borné)."""
    s = _NAME_RE.sub("-", (name or "").strip().lower()).strip("-")
    return s[:60]


def _safe_member(member_id: str) -> str:
    if not member_id or not _MEMBER_RE.match(member_id):
        raise ValueError("member_id invalide")
    return member_id


@dataclass(frozen=True)
class Skill:
    name: str          # identifiant (slug)
    title: str         # titre lisible
    description: str   # quand s'en servir
    source: str        # "livrée" ou "perso"

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def parse_skill(name: str, text: str, source: str) -> Skill:
    """Extrait titre et description de l'en-tête ; tolère une fiche mal formée."""
    title, description = "", ""
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not title and stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            continue
        if title and not description and stripped.startswith(">"):
            description = stripped.lstrip(">").strip()
            break
        if title:
            break
    return Skill(name, title or name, description, source)


class SkillStore:
    """Compétences livrées + compétences propres à chaque membre."""

    def __init__(self, builtin_dir: str, user_base: Optional[str] = None) -> None:
        self._builtin = Path(builtin_dir)
        self._user_base = Path(user_base) if user_base else None

    # -- chemins -------------------------------------------------------------- #
    def _user_dir(self, member_id: str) -> Optional[Path]:
        if self._user_base is None:
            return None
        return self._user_base / _safe_member(member_id)

    def _find(self, member_id: Optional[str], name: str):
        """(chemin, source) de la fiche, la version perso primant sur la livrée."""
        slug = safe_name(name)
        if not slug:
            return None, ""
        if member_id:
            udir = self._user_dir(member_id)
            if udir is not None:
                p = udir / f"{slug}.md"
                if p.is_file():
                    return p, "perso"
        p = self._builtin / f"{slug}.md"
        return (p, "livrée") if p.is_file() else (None, "")

    # -- lecture -------------------------------------------------------------- #
    def list_skills(self, member_id: Optional[str] = None) -> List[Skill]:
        found: Dict[str, Skill] = {}
        if self._builtin.is_dir():
            for p in sorted(self._builtin.glob("*.md")):
                found[p.stem] = parse_skill(p.stem, self._read(p), "livrée")
        if member_id:
            udir = self._user_dir(member_id)
            if udir is not None and udir.is_dir():
                for p in sorted(udir.glob("*.md")):
                    # Écrase la version livrée : la méthode de l'utilisateur prime.
                    found[p.stem] = parse_skill(p.stem, self._read(p), "perso")
        return [found[k] for k in sorted(found)]

    def read_skill(self, member_id: Optional[str], name: str) -> str:
        path, _ = self._find(member_id, name)
        return self._read(path) if path else ""

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    # -- écriture (compétences personnelles) ---------------------------------- #
    def save_skill(self, member_id: str, name: str, title: str, description: str, content: str) -> Skill:
        if self._user_base is None:
            raise ValueError("compétences personnelles désactivées")
        slug = safe_name(name) or safe_name(title)
        if not slug:
            raise ValueError("nom de compétence vide")
        udir = self._user_dir(member_id)
        udir.mkdir(parents=True, exist_ok=True)
        body = (content or "").strip()[:MAX_SKILL_CHARS]
        text = f"# {(title or slug).strip()}\n> {(description or '').strip()}\n\n{body}\n"
        (udir / f"{slug}.md").write_text(text, encoding="utf-8")
        return parse_skill(slug, text, "perso")

    def delete_skill(self, member_id: str, name: str) -> bool:
        """Supprime une compétence PERSONNELLE (les livrées ne sont jamais touchées)."""
        udir = self._user_dir(member_id)
        if udir is None:
            return False
        p = udir / f"{safe_name(name)}.md"
        if not p.is_file():
            return False
        p.unlink()
        return True

    # -- contexte -------------------------------------------------------------- #
    def build_index(self, member_id: Optional[str] = None, *, limit: int = 40) -> str:
        """Sommaire injecté au prompt : noms + descriptions, JAMAIS le contenu."""
        skills = self.list_skills(member_id)[:limit]
        if not skills:
            return ""
        lignes = [f"- {s.name} : {s.description or s.title}" for s in skills]
        return (
            "[Compétences disponibles — méthodes à suivre]\n"
            "Avant de rédiger un document, de mener un exercice ou d'exécuter une tâche "
            "méthodique, consulte la compétence correspondante avec read_skill et applique-la. "
            "Ne devine pas la méthode si une compétence existe.\n" + "\n".join(lignes)
        )
