"""Outils appelables par le LLM (function calling) : accès web pour VindIA.

VindIA reste un agent **souverain Mistral** : ces outils étendent ses capacités
SANS changer de fournisseur. Le LLM décide quand chercher sur le web ; le runtime
exécute l'outil et lui renvoie le résultat (boucle tool-use dans `MistralLLM`).

Principe maison (cf. `adapters.CallableTTS`) : le backend réseau de chaque outil
est un **transport injectable**. Le module n'importe AUCUNE lib tierce et ne fait
AUCUN appel réseau au chargement → testable 100 % offline par la CI stdlib. Le
vrai backend (méta-moteur souverain SearXNG self-host, fetch HTTP) se branche au
déploiement derrière le même transport, sans toucher ni le runtime ni le LLM.

Sécurité : `WebFetchTool` refuse par construction toute URL non http(s) ou
pointant vers une cible interne (localhost, IP privées, link-local) — garde-fou
SSRF appliqué par le CODE avant tout appel réseau, pas par une consigne au modèle.
"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Awaitable, Callable, Dict, List, Optional, Sequence
from urllib.parse import urlsplit

# --- Frontières réseau injectables (le "joint" testable de chaque outil) ---
# Recherche : (requête, nb max de résultats) -> liste de {title, url, snippet}.
SearchTransport = Callable[[str, int], Awaitable[Sequence[dict]]]
# Fetch : URL (déjà validée) -> texte extrait de la page.
FetchTransport = Callable[[str], Awaitable[str]]


@dataclass(frozen=True)
class ToolSpec:
    """Déclaration d'un outil au format function-calling Mistral/OpenAI."""

    name: str
    description: str
    parameters: dict  # JSON Schema des arguments

    def as_mistral(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class Tool:
    """Contrat d'un outil : une spec déclarative + une exécution async.

    `run` reçoit les arguments désérialisés (dict) et retourne TOUJOURS une
    chaîne — c'est ce texte qui est réinjecté au LLM comme message `tool`.
    """

    spec: ToolSpec

    async def run(self, args: dict) -> str:  # pragma: no cover - interface
        raise NotImplementedError


# --------------------------------------------------------------------------- #
#  Outils web
# --------------------------------------------------------------------------- #

class WebSearchTool(Tool):
    """Recherche web. Le backend (méta-moteur souverain) est injecté.

    Exemple (test) :  WebSearchTool(transport=fake_async_returning_results)
    Exemple (live) :  WebSearchTool(transport=searxng_transport(url))
    """

    def __init__(self, transport: SearchTransport, *, max_results: int = 5) -> None:
        self._transport = transport
        self._max_results = max_results
        self.spec = ToolSpec(
            name="web_search",
            description=(
                "Recherche des informations à jour sur le web. À utiliser pour "
                "toute question portant sur l'actualité, des faits récents, des "
                "prix, des personnes ou des sujets que tu ne connais pas avec "
                "certitude. Retourne une liste de résultats (titre, URL, extrait)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La requête de recherche, en langage naturel.",
                    }
                },
                "required": ["query"],
            },
        )

    async def run(self, args: dict) -> str:
        query = (args.get("query") or "").strip()
        if not query:
            return "Erreur : requête de recherche vide."
        results = await self._transport(query, self._max_results)
        rows = list(results)[: self._max_results]
        if not rows:
            return "Aucun résultat web pour cette requête."
        # Format compact et lisible par le LLM (pas de JSON inutilement verbeux).
        lines = []
        for i, r in enumerate(rows, 1):
            title = (r.get("title") or "").strip() or "(sans titre)"
            url = (r.get("url") or "").strip()
            snippet = (r.get("snippet") or "").strip()
            lines.append(f"{i}. {title}\n   {url}\n   {snippet}".rstrip())
        return "\n".join(lines)


# Plages réseau internes interdites au fetch (garde-fou SSRF).
def _is_blocked_host(host: str) -> bool:
    """True si l'hôte est local/interne (à refuser). Hostnames publics → False."""
    if not host:
        return True
    h = host.strip().strip("[]").lower()  # gère [::1] et casse
    if h in ("localhost", "localhost.localdomain"):
        return True
    # Métadonnées cloud (AWS/GCP/Azure) — cible SSRF classique.
    if h in ("metadata.google.internal", "metadata"):
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        # Pas une IP littérale : hostname public présumé. La résolution DNS
        # (et donc une éventuelle ré-résolution interne) reste à la charge du
        # transport live, qui DOIT refuser les IP privées résolues.
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_fetch_url(url: str) -> Optional[str]:
    """Retourne un motif de refus, ou None si l'URL est autorisée au fetch."""
    parts = urlsplit((url or "").strip())
    if parts.scheme not in ("http", "https"):
        return "schéma non autorisé (seuls http/https le sont)"
    if not parts.hostname:
        return "URL sans hôte"
    if _is_blocked_host(parts.hostname):
        return "cible interne interdite (localhost / IP privée)"
    return None


class WebFetchTool(Tool):
    """Récupère et résume le contenu textuel d'une URL. Backend injecté.

    Le garde-fou SSRF (`validate_fetch_url`) est appliqué AVANT le transport :
    une URL interne n'atteint jamais le réseau.
    """

    def __init__(self, transport: FetchTransport, *, max_chars: int = 4000) -> None:
        self._transport = transport
        self._max_chars = max_chars
        self.spec = ToolSpec(
            name="web_fetch",
            description=(
                "Récupère le contenu textuel d'une page web à partir de son URL "
                "(typiquement une URL trouvée via web_search) pour en lire le détail."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "L'URL http(s) complète de la page à lire.",
                    }
                },
                "required": ["url"],
            },
        )

    async def run(self, args: dict) -> str:
        url = (args.get("url") or "").strip()
        reason = validate_fetch_url(url)
        if reason is not None:
            return f"Erreur : URL refusée — {reason}."
        text = (await self._transport(url) or "").strip()
        if not text:
            return "La page n'a retourné aucun contenu textuel exploitable."
        if len(text) > self._max_chars:
            text = text[: self._max_chars].rstrip() + " […]"
        return text


# --------------------------------------------------------------------------- #
#  Registre
# --------------------------------------------------------------------------- #

class ToolRegistry:
    """Collection d'outils : expose les specs au LLM, dispatche les appels.

    Tolérant aux pannes : une exception d'un outil est convertie en message
    d'erreur textuel renvoyé au LLM (qui peut alors s'excuser ou réessayer),
    plutôt que de faire planter toute la session vocale.
    """

    def __init__(self, tools: Optional[Sequence[Tool]] = None) -> None:
        self._tools: Dict[str, Tool] = {}
        for t in tools or ():
            self.register(t)

    def register(self, tool: Tool) -> None:
        self._tools[tool.spec.name] = tool

    def __len__(self) -> int:
        return len(self._tools)

    def __bool__(self) -> bool:
        return bool(self._tools)

    def specs(self) -> List[dict]:
        """Specs au format Mistral, à passer dans le paramètre `tools` de l'API."""
        return [t.spec.as_mistral() for t in self._tools.values()]

    async def dispatch(self, name: str, arguments: object) -> str:
        """Exécute l'outil `name`. `arguments` = dict OU chaîne JSON (format API)."""
        tool = self._tools.get(name)
        if tool is None:
            return f"Erreur : outil inconnu « {name} »."
        if isinstance(arguments, str):
            try:
                args = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError:
                return f"Erreur : arguments illisibles pour « {name} »."
        elif isinstance(arguments, dict):
            args = arguments
        else:
            args = {}
        try:
            return await tool.run(args)
        except Exception as exc:  # noqa: BLE001 - on protège la session
            return f"Erreur lors de l'exécution de « {name} » : {exc}"


# --------------------------------------------------------------------------- #
#  Extraction texte HTML (pure stdlib → testable offline)
# --------------------------------------------------------------------------- #

class _TextExtractor(HTMLParser):
    """Extrait le texte visible : ignore <script>/<style>, garde les coupures de bloc."""

    _SKIP = {"script", "style", "noscript", "head", "svg"}
    _BLOCK = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "article", "section"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: List[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BLOCK:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0 and data.strip():
            self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        # Collapse : espaces multiples → 1, lignes vides multiples → 1.
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n", raw)
        return raw.strip()


def html_to_text(html: str) -> str:
    """Convertit du HTML en texte lisible (sans balises, scripts ni styles)."""
    parser = _TextExtractor()
    try:
        parser.feed(html or "")
    except Exception:  # parsing tolérant : un HTML cassé ne doit pas lever
        return ""
    return parser.text()


# --------------------------------------------------------------------------- #
#  Fabriques de transports LIVE (souverains) — import paresseux, hors CI
# --------------------------------------------------------------------------- #

def searxng_search_transport(base_url: str, *, timeout: float = 8.0) -> SearchTransport:
    """Recherche via une instance SearXNG (méta-moteur souverain, self-host VPS).

    `base_url` ex. http://127.0.0.1:8888 — l'instance DOIT exposer `format=json`.
    aiohttp est importé paresseusement (déjà présent : sert le serveur web).
    """

    async def _call(query: str, n: int) -> Sequence[dict]:  # pragma: no cover - live
        import aiohttp

        params = {"q": query, "format": "json", "language": "fr"}
        url = base_url.rstrip("/") + "/search"
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, params=params, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                resp.raise_for_status()
                data = await resp.json()
        out: List[dict] = []
        for r in (data.get("results") or [])[:n]:
            out.append(
                {
                    "title": r.get("title") or "",
                    "url": r.get("url") or "",
                    "snippet": r.get("content") or "",
                }
            )
        return out

    return _call


def http_fetch_transport(*, timeout: float = 8.0, max_bytes: int = 1_500_000) -> FetchTransport:
    """Récupère une page http(s) et en extrait le texte (garde-fou SSRF déjà passé).

    Borné en octets (anti-bombe) ; l'extraction texte est faite par `html_to_text`.
    """

    async def _call(url: str) -> str:  # pragma: no cover - live
        import aiohttp

        headers = {"User-Agent": "VindIA/1.0 (+https://vindia)"}
        async with aiohttp.ClientSession(headers=headers) as sess:
            async with sess.get(url, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True) as resp:
                resp.raise_for_status()
                raw = await resp.content.read(max_bytes)
        ctype = ""  # best-effort : on tente le décodage utf-8 tolérant
        try:
            html = raw.decode("utf-8", errors="replace")
        except Exception:
            html = raw.decode("latin-1", errors="replace")
        return html_to_text(html)

    return _call


def build_web_tool_registry() -> Optional[ToolRegistry]:
    """Construit le registre d'outils web depuis l'environnement, ou None.

    Activé seulement si `SEARXNG_URL` est défini (sinon : pas d'accès web, on ne
    propose aucun outil au LLM). `web_fetch` est joint dès que la recherche l'est.
    """
    import os

    base = (os.environ.get("SEARXNG_URL") or "").strip()
    if not base:
        return None
    return ToolRegistry(
        [
            WebSearchTool(transport=searxng_search_transport(base)),
            WebFetchTool(transport=http_fetch_transport()),
        ]
    )
