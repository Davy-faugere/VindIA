"""Outils « compétences » — VindIA consulte ses méthodes à la demande.

Le sommaire des compétences est injecté dans le contexte (noms + descriptions) ;
le CONTENU, lui, ne l'est jamais d'office : VindIA ouvre la fiche utile au moment
où elle en a besoin. C'est ce qui permet d'en avoir beaucoup sans saturer.

L'utilisateur peut aussi dicter sa propre méthode : `save_skill` l'enregistre dans
son espace, et elle prime dès lors sur la version livrée du même nom.

ISOLATION : `member_id` est figé à la construction — le modèle ne le fournit jamais.
"""

from __future__ import annotations

from typing import List, Optional

from .skills import SkillStore
from .tools import Tool, ToolSpec


class ListSkillsTool(Tool):
    """Liste les compétences disponibles (nom + quand s'en servir)."""

    def __init__(self, store: SkillStore, member_id: Optional[str]) -> None:
        self._store = store
        self._member_id = member_id
        self.spec = ToolSpec(
            name="list_skills",
            description=(
                "Liste les compétences (fiches de méthode) dont tu disposes. À utiliser "
                "si tu ne sais pas laquelle s'applique à la demande en cours."
            ),
            parameters={"type": "object", "properties": {}},
        )

    async def run(self, args: dict) -> str:
        skills = self._store.list_skills(self._member_id)
        if not skills:
            return "Aucune compétence disponible."
        return "Compétences disponibles :\n" + "\n".join(
            f"- {s.name} : {s.description or s.title}" for s in skills
        )


class ReadSkillTool(Tool):
    """Ouvre une fiche de méthode et la retourne intégralement."""

    def __init__(self, store: SkillStore, member_id: Optional[str]) -> None:
        self._store = store
        self._member_id = member_id
        self.spec = ToolSpec(
            name="read_skill",
            description=(
                "Lit une compétence (fiche de méthode) et applique-la. À utiliser AVANT "
                "de rédiger un document, de mener un exercice ou d'exécuter une tâche "
                "méthodique, quand une compétence correspond à la demande."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nom de la compétence, ex. compte-rendu-reunion"}
                },
                "required": ["name"],
            },
        )

    async def run(self, args: dict) -> str:
        name = (args.get("name") or "").strip()
        if not name:
            return "Erreur : nom de compétence manquant."
        text = self._store.read_skill(self._member_id, name)
        if not text:
            dispo = ", ".join(s.name for s in self._store.list_skills(self._member_id)) or "aucune"
            return f"Compétence « {name} » introuvable. Disponibles : {dispo}."
        return text


class SaveSkillTool(Tool):
    """Enregistre une méthode dictée par l'utilisateur (compétence personnelle)."""

    def __init__(self, store: SkillStore, member_id: str) -> None:
        self._store = store
        self._member_id = member_id
        self.spec = ToolSpec(
            name="save_skill",
            description=(
                "Enregistre une nouvelle compétence (fiche de méthode) pour cet "
                "utilisateur. À utiliser quand il explique comment il veut que tu fasses "
                "quelque chose et demande que tu t'en souviennes durablement : « retiens "
                "ma façon de… », « voici ma méthode pour… ». Une compétence du même nom "
                "qu'une compétence livrée la remplace."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Identifiant court, ex. mes-comptes-rendus"},
                    "title": {"type": "string", "description": "Titre lisible de la méthode."},
                    "description": {"type": "string", "description": "En une phrase : quand s'en servir."},
                    "content": {"type": "string", "description": "La méthode, structurée et détaillée."},
                },
                "required": ["name", "content"],
            },
        )

    async def run(self, args: dict) -> str:
        name = (args.get("name") or "").strip()
        content = (args.get("content") or "").strip()
        if not name:
            return "Erreur : nom de compétence manquant."
        if not content:
            return "Erreur : contenu vide, rien à enregistrer."
        try:
            skill = self._store.save_skill(
                self._member_id, name,
                (args.get("title") or name).strip(),
                (args.get("description") or "").strip(),
                content,
            )
        except ValueError as exc:
            return f"Enregistrement impossible : {exc}"
        return (
            f"Compétence « {skill.title} » enregistrée. Je l'appliquerai désormais "
            "quand la situation s'y prête."
        )


def build_skill_tools(store: SkillStore, member_id: Optional[str]) -> List[Tool]:
    """Outils compétences pour CE membre (save_skill seulement s'il est identifié)."""
    tools: List[Tool] = [ListSkillsTool(store, member_id), ReadSkillTool(store, member_id)]
    if member_id:
        tools.append(SaveSkillTool(store, member_id))
    return tools
