"""Connecteur Notion — VindIA consulte l'espace de travail de SON utilisateur.

Chacun branche SON Notion : le jeton d'intégration vit dans le coffre chiffré, rangé
par membre. VindIA n'accède donc jamais qu'aux pages de la personne qui lui parle, et
seulement à celles que cette personne a explicitement partagées avec l'intégration
côté Notion — c'est Notion lui-même qui pose cette limite, pas nous.

Lecture partout, écriture NULLE PART sauf sous une page d'accueil que l'utilisateur
désigne lui-même. VindIA peut donc déposer ses comptes rendus au bon endroit, sans
pouvoir modifier ni écraser une page existante de l'espace de travail : elle ne sait
que créer des sous-pages sous ce parent, et rien d'autre.

Le transport réseau est injectable → testable hors ligne, comme le reste du projet.
0 dépendance tierce.
"""

from __future__ import annotations

import json
from typing import Awaitable, Callable, List, Optional

from .tools import Tool, ToolSpec

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"          # version d'API épinglée : Notion casse sans prévenir

# (méthode, chemin, corps) -> réponse décodée. Injectable pour les tests.
NotionCall = Callable[[str, str, Optional[dict]], Awaitable[dict]]

# Bornes : ce qui part dans le contexte du modèle doit rester lisible.
MAX_RESULTATS = 12
MAX_CARACTERES = 6000


def live_call(token: str) -> NotionCall:  # pragma: no cover - réseau
    """Appel réel de l'API Notion (urllib, aucune dépendance)."""

    async def _call(methode: str, chemin: str, corps: Optional[dict] = None) -> dict:
        import asyncio
        import urllib.error
        import urllib.request

        def _bloquant() -> dict:
            data = json.dumps(corps).encode("utf-8") if corps is not None else None
            req = urllib.request.Request(
                f"{API}{chemin}", data=data, method=methode,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Notion-Version": VERSION,
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:200]
                raise RuntimeError(_message(exc.code, detail)) from None

        return await asyncio.get_running_loop().run_in_executor(None, _bloquant)

    return _call


def _message(code: int, detail: str) -> str:
    if code == 401:
        return ("Le jeton Notion est refusé. Vérifie-le dans « Connexions », "
                "ou régénère-le sur notion.so/my-integrations.")
    if code == 404:
        return ("Page introuvable, ou non partagée avec l'intégration. Dans Notion, "
                "ouvre la page, menu « … », « Connexions », et ajoute VindIA.")
    if code == 429:
        return "Notion limite le rythme des requêtes. Réessaie dans un instant."
    return f"Notion a répondu une erreur ({code}). {detail[:120]}"


# --------------------------------------------------------------------------- #
#  Conversion des blocs Notion en texte lisible
# --------------------------------------------------------------------------- #

def _rich(items) -> str:
    return "".join((i.get("plain_text") or "") for i in (items or []))


def titre_page(page: dict) -> str:
    """Titre d'une page, quel que soit le nom de sa propriété titre."""
    props = page.get("properties") or {}
    for prop in props.values():
        if prop.get("type") == "title":
            t = _rich(prop.get("title"))
            if t:
                return t
    # Une entrée de base de données peut n'avoir aucun titre renseigné.
    return "(sans titre)"


def bloc_en_texte(bloc: dict) -> str:
    """Un bloc Notion → une ligne de texte, en gardant la structure utile."""
    t = bloc.get("type") or ""
    corps = bloc.get(t) or {}
    texte = _rich(corps.get("rich_text"))
    if t == "heading_1":
        return f"\n# {texte}"
    if t == "heading_2":
        return f"\n## {texte}"
    if t == "heading_3":
        return f"\n### {texte}"
    if t in ("bulleted_list_item", "toggle"):
        return f"- {texte}"
    if t == "numbered_list_item":
        return f"1. {texte}"
    if t == "to_do":
        coche = "x" if corps.get("checked") else " "
        return f"[{coche}] {texte}"
    if t == "code":
        return texte
    if t == "quote":
        return f"> {texte}"
    if t == "callout":
        return f"! {texte}"
    if t == "child_page":
        return f"[sous-page] {corps.get('title') or ''}"
    if t == "child_database":
        return f"[base de données] {corps.get('title') or ''}"
    if t == "divider":
        return "---"
    if t == "table_row":
        cellules = [_rich(c) for c in (corps.get("cells") or [])]
        return "| " + " | ".join(cellules) + " |"
    return texte


# --------------------------------------------------------------------------- #
#  Outils
# --------------------------------------------------------------------------- #

class NotionSearchTool(Tool):
    """Cherche des pages dans le Notion de l'utilisateur."""

    def __init__(self, call: NotionCall) -> None:
        self._call = call
        self.spec = ToolSpec(
            name="notion_search",
            description=(
                "Cherche une page ou une base de données dans l'espace Notion de "
                "l'utilisateur, par mots-clés. Renvoie les titres et leurs "
                "identifiants. À utiliser avant notion_read pour trouver la bonne page."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Mots-clés à chercher."}
                },
                "required": ["query"],
            },
        )

    async def run(self, args: dict) -> str:
        q = (args.get("query") or "").strip()
        if not q:
            return "Erreur : indique ce qu'il faut chercher."
        try:
            data = await self._call("POST", "/search",
                                    {"query": q, "page_size": MAX_RESULTATS})
        except Exception as exc:  # noqa: BLE001
            return str(exc)[:250]
        resultats = data.get("results") or []
        if not resultats:
            return (f"Aucune page Notion ne correspond à « {q} ». Rappel : seules les "
                    "pages partagées avec l'intégration VindIA sont visibles.")
        lignes = []
        for r in resultats[:MAX_RESULTATS]:
            genre = "base de données" if r.get("object") == "database" else "page"
            lignes.append(f"- {titre_page(r)} ({genre}, id {r.get('id')})")
        return f"{len(lignes)} résultat(s) dans Notion :\n" + "\n".join(lignes)


class NotionReadTool(Tool):
    """Lit le contenu d'une page Notion."""

    def __init__(self, call: NotionCall) -> None:
        self._call = call
        self.spec = ToolSpec(
            name="notion_read",
            description=(
                "Lit le contenu d'une page Notion à partir de son identifiant "
                "(obtenu avec notion_search). N'invente jamais le contenu d'une page : "
                "lis-la."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Identifiant de la page."}
                },
                "required": ["page_id"],
            },
        )

    async def run(self, args: dict) -> str:
        pid = (args.get("page_id") or "").strip().replace("-", "")
        if not pid:
            return "Erreur : identifiant de page manquant."
        try:
            blocs = await self._call("GET", f"/blocks/{pid}/children?page_size=100", None)
        except Exception as exc:  # noqa: BLE001
            return str(exc)[:250]
        lignes = [bloc_en_texte(b) for b in (blocs.get("results") or [])]
        texte = "\n".join(l for l in lignes if l.strip())
        if not texte.strip():
            return "Cette page Notion est vide (ou ne contient que des éléments non lisibles)."
        if len(texte) > MAX_CARACTERES:
            texte = texte[:MAX_CARACTERES].rstrip() + "\n[…] (page tronquée)"
        return texte


def build_notion_tools(token: str, call: Optional[NotionCall] = None,
                       parent_id: str = "") -> List[Tool]:
    """Outils Notion pour UN jeton — donc pour un seul utilisateur.

    L'écriture n'est proposée que si une page d'accueil a été désignée : sans elle,
    VindIA n'aurait aucun endroit légitime où créer, et choisir seule serait pire.
    """
    appel = call or live_call(token)
    outils = [NotionSearchTool(appel), NotionReadTool(appel)]
    if parent_id:
        outils.append(NotionWriteTool(appel, parent_id))
    return outils


class NotionWriteTool(Tool):
    """Crée une sous-page sous la page d'accueil désignée par l'utilisateur.

    Le parent est FIGÉ à la construction : le modèle ne fournit qu'un titre et un
    contenu. Il ne peut donc ni choisir où écrire, ni modifier une page existante —
    la seule opération possible est « créer sous cette page-ci ».
    """

    def __init__(self, call: NotionCall, parent_id: str) -> None:
        self._call = call
        self._parent = (parent_id or "").replace("-", "")
        self.spec = ToolSpec(
            name="notion_write",
            description=(
                "Enregistre un document dans Notion, sous la page d'accueil de "
                "l'utilisateur. À utiliser quand il demande de « mettre ça dans "
                "Notion », de garder une trace ou d'archiver un compte rendu. "
                "Le contenu accepte les titres « # », les puces « - » et le gras."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "titre": {"type": "string", "description": "Titre de la page à créer."},
                    "contenu": {"type": "string", "description": "Contenu complet, en texte structuré."},
                },
                "required": ["titre", "contenu"],
            },
        )

    async def run(self, args: dict) -> str:
        titre = (args.get("titre") or "").strip()
        contenu = (args.get("contenu") or "").strip()
        if not titre:
            return "Erreur : titre manquant."
        if not contenu:
            return "Erreur : contenu vide, rien à enregistrer."
        corps = {
            "parent": {"page_id": self._parent},
            "properties": {"title": {"title": [{"text": {"content": titre[:200]}}]}},
            "children": texte_en_blocs(contenu),
        }
        try:
            page = await self._call("POST", "/pages", corps)
        except Exception as exc:  # noqa: BLE001
            return str(exc)[:250]
        return f"Page « {titre} » créée dans Notion, sous ta page d'accueil."


# Notion refuse un envoi de plus de 100 blocs, et 2000 caractères par bloc.
MAX_BLOCS = 100
MAX_TEXTE_BLOC = 1900


def texte_en_blocs(contenu: str) -> list:
    """Texte structuré → blocs Notion. L'inverse de bloc_en_texte."""
    blocs = []
    for ligne in (contenu or "").splitlines():
        l = ligne.rstrip()
        if not l.strip():
            continue
        if l.startswith("### "):
            genre, texte = "heading_3", l[4:]
        elif l.startswith("## "):
            genre, texte = "heading_2", l[3:]
        elif l.startswith("# "):
            genre, texte = "heading_1", l[2:]
        elif l.lstrip().startswith(("- ", "* ")):
            genre, texte = "bulleted_list_item", l.lstrip()[2:]
        elif l.lstrip()[:2].rstrip(".").isdigit() and ". " in l:
            genre, texte = "numbered_list_item", l.split(". ", 1)[1]
        else:
            genre, texte = "paragraph", l
        # Le gras markdown n'a pas d'équivalent direct ici : on retire les marqueurs
        # plutôt que de les laisser s'afficher tels quels dans Notion.
        texte = texte.replace("**", "").strip()
        if not texte:
            continue
        blocs.append({
            "object": "block", "type": genre,
            genre: {"rich_text": [{"type": "text", "text": {"content": texte[:MAX_TEXTE_BLOC]}}]},
        })
        if len(blocs) >= MAX_BLOCS:
            break
    return blocs or [{"object": "block", "type": "paragraph",
                      "paragraph": {"rich_text": [{"type": "text", "text": {"content": contenu[:MAX_TEXTE_BLOC]}}]}}]
