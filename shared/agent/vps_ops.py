"""Connecteur MCP VPS — VindIA consulte l'état du serveur (LECTURE SEULE).

VindIA peut renseigner sur la santé du VPS et l'état d'un service, via l'API ops
du mcp-server (déjà sécurisée côté serveur : services en liste blanche, clé X-API-Key).

GARDE-FOU STRICT : ce connecteur n'expose que des LECTURES — santé, état d'un
service, et contenu d'un fichier. Les endpoints qui AGISSENT (restart, reload,
dispatch-mission…) ne sont pas branchés → le LLM ne peut pas les invoquer. Toute
action sur le VPS reste hors de portée de VindIA (cohérent avec les garde-fous flotte).

La lecture de fichier s'appuie sur la liste blanche de chemins déjà appliquée par
l'API ops elle-même : le filtrage a lieu côté serveur, pas ici — un garde-fou qui
ne dépend pas de ce que le modèle envoie.

Style maison : 0 dépendance tierce au chargement ; le transport HTTP est injectable
(aiohttp en prod, fake en test) → testable 100 % offline.
"""

from __future__ import annotations

import os
from typing import Awaitable, Callable, List, Optional

from .tools import Tool, ToolSpec

# Transport : (path, params) -> JSON. La clé X-API-Key est portée par le transport.
OpsTransport = Callable[[str, dict], Awaitable[dict]]


class VpsHealthTool(Tool):
    """Santé globale du VPS + liste des services consultables."""

    def __init__(self, transport: OpsTransport) -> None:
        self._transport = transport
        self.spec = ToolSpec(
            name="vps_health",
            description=(
                "Donne l'état de santé du serveur VPS et la liste des services que "
                "l'on peut consulter. Lecture seule."
            ),
            parameters={"type": "object", "properties": {}},
        )

    async def run(self, args: dict) -> str:
        data = await self._transport("/ops/health", {})
        return _summarize(data)


class VpsServiceStatusTool(Tool):
    """État d'un service systemd précis (liste blanche imposée par l'API)."""

    def __init__(self, transport: OpsTransport) -> None:
        self._transport = transport
        self.spec = ToolSpec(
            name="vps_service_status",
            description=(
                "Donne l'état (actif/arrêté, depuis quand) d'un service du VPS. "
                "Le service doit faire partie des services autorisés (voir vps_health). "
                "Lecture seule, aucune action."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Nom du service, ex. nginx."}
                },
                "required": ["service"],
            },
        )

    async def run(self, args: dict) -> str:
        service = (args.get("service") or "").strip()
        if not service:
            return "Erreur : nom de service manquant."
        try:
            data = await self._transport("/ops/systemctl-status", {"service": service})
        except Exception as exc:  # service hors liste blanche → l'API renvoie une erreur
            return f"Impossible de lire « {service} » : {str(exc)[:160]}"
        return _summarize(data)


def _summarize(data: object) -> str:
    """Rend la réponse JSON de l'API ops lisible par le LLM (compacte)."""
    if isinstance(data, dict):
        # On garde les champs courants sans présumer du schéma exact.
        parts = []
        for k in ("status", "active", "service", "since", "uptime", "services", "allowed_services", "detail", "summary"):
            if k in data and data[k] not in (None, ""):
                parts.append(f"{k}: {data[k]}")
        return "\n".join(parts) if parts else str(data)[:800]
    return str(data)[:800]


def ops_http_transport(base_url: str, api_key: str, *, timeout: float = 8.0) -> OpsTransport:
    """Transport live vers l'API ops (GET + en-tête X-API-Key). aiohttp paresseux."""

    async def _call(path: str, params: dict) -> dict:  # pragma: no cover - live
        import aiohttp

        url = base_url.rstrip("/") + path
        headers = {"X-API-Key": api_key}
        async with aiohttp.ClientSession(headers=headers) as sess:
            async with sess.get(url, params=params, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                resp.raise_for_status()
                return await resp.json()

    return _call


class VpsReadFileTool(Tool):
    """Lit un fichier du serveur, parmi les chemins autorisés par l'API ops."""

    MAX = 6000

    def __init__(self, transport: OpsTransport) -> None:
        self._transport = transport
        self.spec = ToolSpec(
            name="vps_read_file",
            description=(
                "Lit un fichier de configuration ou un journal du serveur "
                "(configuration nginx, journaux, fichiers du site). Utilise "
                "vps_health pour connaître les emplacements autorisés. Lecture "
                "seule : aucune modification n'est possible."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Chemin absolu du fichier."}
                },
                "required": ["path"],
            },
        )

    async def run(self, args: dict) -> str:
        chemin = (args.get("path") or "").strip()
        if not chemin:
            return "Erreur : chemin manquant."
        try:
            data = await self._transport("/ops/file-read", {"path": chemin})
        except Exception as exc:  # noqa: BLE001
            return f"Lecture impossible : {str(exc)[:180]}"
        if isinstance(data, dict) and data.get("error"):
            return f"Refusé par le serveur : {str(data['error'])[:180]}"
        contenu = (data or {}).get("content") if isinstance(data, dict) else None
        if contenu is None:
            return "Le serveur n'a renvoyé aucun contenu pour ce fichier."
        contenu = str(contenu)
        if len(contenu) > self.MAX:
            # On garde la FIN : sur un journal, c'est le récent qui compte.
            contenu = "[…début tronqué…]\n" + contenu[-self.MAX:]
        return contenu or "Fichier vide."


def build_vps_tools() -> List[Tool]:
    """Outils VPS (lecture seule) depuis l'environnement, ou [] si non configuré.

    Activé si MCP_OPS_URL + MCP_API_KEY sont définis (ex. URL = http://127.0.0.1:9150).
    """
    base = (os.environ.get("MCP_OPS_URL") or "").strip()
    key = (os.environ.get("MCP_API_KEY") or "").strip()
    if not base or not key:
        return []
    transport = ops_http_transport(base, key)
    return [VpsHealthTool(transport), VpsServiceStatusTool(transport),
            VpsReadFileTool(transport)]
