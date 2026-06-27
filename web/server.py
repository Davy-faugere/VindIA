"""Serveur web VindIA : page + /token (LiveKit) + /auth + /ask + /session/end + /tts + /build.

/auth  : identifie l'utilisateur par code → renvoie display_name + charge la mémoire
/ask   : appel Mistral direct avec mémoire long-terme injectée (remplace le webhook n8n)
/session/end : extrait les faits de la session et les persiste en MariaDB

    set -a; . server/.env; set +a
    .venv/bin/python web/server.py
"""

from __future__ import annotations

import asyncio
import datetime
import os
import secrets as _secrets
import sys
import time
from collections import defaultdict
from pathlib import Path

# shared.agent est au niveau parent (vindia-work/) ; on s'assure qu'il est importable.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from aiohttp import web
from livekit import api
import edge_tts

from filegen import build_file, OFFICE_TYPES
from shared.agent.projects import ProjectStore, extract_text, ExtractionError
from shared.agent.vault import CredentialVault, fernet_crypto
from shared.agent.oauth_google import GoogleOAuth, secrets_from_token_response

ROOM = os.environ.get("VINDIA_ROOM", "vindia")
URL = os.environ["LIVEKIT_URL"]
KEY = os.environ["LIVEKIT_API_KEY"]
SECRET = os.environ["LIVEKIT_API_SECRET"]
PORT = int(os.environ.get("VINDIA_WEB_PORT", "8092"))
WEB_DIR = Path(__file__).resolve().parent
TTS_VOICE = os.environ.get("VINDIA_TTS_VOICE", "fr-FR-VivienneMultilingualNeural")
TTS_RATE = os.environ.get("VINDIA_TTS_RATE", "-6%")

# ──────────────────────────────────────────────────────────────
# Identités VindIA : code d'accès → profil + member_id fixe
# (IDs déterministes : pas de collision avec les UUIDs générés)
# ──────────────────────────────────────────────────────────────
_TENANT_ID = "00000001-0001-0001-0001-000000000001"
_CODE_MAP: dict[str, dict] = {
    os.environ.get("VINDIA_CODE_DAVY", "kV7p-Faugere-2026"): {
        "display_name": "Davy",
        "member_id": "00000001-0001-0001-0002-000000000001",
    },
    os.environ.get("VINDIA_CODE_LUDIVINE", "Ludivine-MLM-2026"): {
        "display_name": "Ludivine",
        "member_id": "00000001-0001-0001-0003-000000000001",
    },
    os.environ.get("VINDIA_CODE_INVITE", "Invite-VindIA-2026"): {
        "display_name": "Invité",
        "member_id": "00000001-0001-0001-0004-000000000001",
    },
}

# Services lazily initialisés (MariaDB optionnel : la mémoire est désactivée si absent)
_store = None
_memory = None
_llm = None
_projects = None  # ProjectStore : espaces projet PRIVÉS par membre (persistance disque)
_vault = None     # CredentialVault : coffre chiffré des connexions (Google, mail…)
_google = None    # GoogleOAuth : config app OAuth (None/non configuré si clés absentes)

# Espace de données VindIA (projets/fichiers) — hors repo, hors MariaDB.
_DATA_DIR = os.environ.get("VINDIA_DATA_DIR", "/root/vindia-data")
# Taille max d'un fichier uploadé (anti-DoS) : 10 Mo.
_MAX_UPLOAD = 10 * 1024 * 1024
# URL publique (pour le redirect OAuth). Ex : https://vindia.faugere-davy.fr
_PUBLIC_URL = os.environ.get("VINDIA_PUBLIC_URL", "").rstrip("/")
# States OAuth en cours : state -> (member_id, timestamp monotonic). Anti-CSRF, TTL court.
_oauth_states: dict = {}
_OAUTH_STATE_TTL = 600.0

# Rate limiting : compteur glissant par code d'accès (60 req / heure)
_RATE_LIMIT = 60
_RATE_WINDOW = 3600.0
_rate_buckets: dict = defaultdict(list)


def _check_rate(code: str) -> bool:
    now = time.monotonic()
    bucket = [t for t in _rate_buckets[code] if now - t < _RATE_WINDOW]
    if len(bucket) >= _RATE_LIMIT:
        _rate_buckets[code] = bucket
        return False
    bucket.append(now)
    _rate_buckets[code] = bucket
    return True


def _init_services() -> None:
    global _store, _memory, _llm, _projects, _vault, _google
    if _llm is not None:
        return
    # Projets : magasin disque isolé par membre (indépendant de MariaDB).
    _projects = ProjectStore(os.path.join(_DATA_DIR, "projects"))
    # Coffre à credentials : actif seulement si une clé de chiffrement est fournie.
    # Sans VINDIA_VAULT_KEY → pas de coffre (on refuse de stocker des jetons en clair).
    vault_key = os.environ.get("VINDIA_VAULT_KEY", "").strip()
    if vault_key:
        try:
            _vault = CredentialVault(os.path.join(_DATA_DIR, "vault"), fernet_crypto(vault_key))
        except Exception as exc:
            print(f"[VindIA] coffre désactivé (clé invalide ?) : {exc}")
            _vault = None
    # App OAuth Google : configurée si client_id/secret + URL publique présents.
    gid = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    gsecret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if gid and gsecret and _PUBLIC_URL:
        _google = GoogleOAuth(gid, gsecret, f"{_PUBLIC_URL}/oauth/google/callback")
        print("[VindIA] OAuth Google configuré.")
    from shared.agent.adapters import MistralLLM
    from shared.agent.tools import build_web_tool_registry
    # Accès web optionnel : activé si SEARXNG_URL est défini (souverain, self-host).
    # Absent → VindIA répond sans outils (comportement historique).
    _web_tools = build_web_tool_registry()
    _llm = MistralLLM(tools=_web_tools)
    if _web_tools:
        print(f"[VindIA] Accès web activé ({len(_web_tools)} outils).")
    try:
        from server.db import open_store
        from shared.agent.memory import MemoryStore
        _store = open_store()
        # Bootstrap : crée le tenant et les membres si absents.
        _store.ensure_tenant(_TENANT_ID, "VindIA")
        for profile in _CODE_MAP.values():
            _store.ensure_member(profile["member_id"], _TENANT_ID, profile["display_name"])
        # Transport Mistral léger pour l'extraction (modèle small → économique).
        async def _extract_transport(messages):  # type: ignore[return]
            from mistralai import Mistral
            client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
            resp = await client.chat.complete_async(
                model="mistral-small-latest",
                messages=list(messages),
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content
        _memory = MemoryStore(_store, _extract_transport)
    except Exception as exc:
        print(f"[VindIA] MariaDB indisponible — mémoire désactivée : {exc}")
        _store = None
        _memory = None


async def token(request: web.Request) -> web.Response:
    identity = (request.query.get("identity") or "web-user")[:40]
    jwt = (
        api.AccessToken(KEY, SECRET)
        .with_identity(identity)
        .with_grants(
            api.VideoGrants(
                room_join=True, room=ROOM, can_publish=True, can_subscribe=True
            )
        )
        .with_ttl(datetime.timedelta(hours=1))
        .to_jwt()
    )
    return web.json_response({"url": URL, "token": jwt})


async def index(_: web.Request) -> web.Response:
    return web.FileResponse(WEB_DIR / "index.html")


# Fichiers statiques de la PWA (liste blanche : pas de traversée de répertoire).
_STATIC = {"manifest.json", "sw.js", "icon-192.png", "icon-512.png"}


async def static_file(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    if name not in _STATIC:
        return web.Response(status=404)
    return web.FileResponse(WEB_DIR / name)


async def tts(request: web.Request) -> web.Response:
    """Génère l'audio de la voix (edge-tts, voix FR neurale) depuis du texte."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    text = (data.get("text") or "").strip()[:2000]
    voice = data.get("voice") or TTS_VOICE
    rate = data.get("rate") or TTS_RATE
    if not text:
        return web.Response(status=400)
    audio = bytearray()
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
    except Exception as exc:  # la page bascule sur la voix navigateur si ça échoue
        return web.json_response({"error": str(exc)[:200]}, status=502)
    return web.Response(
        body=bytes(audio),
        content_type="audio/mpeg",
        headers={"Access-Control-Allow-Origin": "*"},
    )


async def build(request: web.Request) -> web.Response:
    """Construit un fichier bureautique (docx/xlsx/pptx/pdf) depuis du texte.

    VindIA renvoie le contenu dans le marqueur [[FICHIER:nom.ext]] ; la page poste
    ici {name, content} et reçoit le binaire prêt à télécharger. Rien n'est stocké.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    name = (data.get("name") or "").strip()[:120]
    content = data.get("content") or ""
    if not name:
        return web.json_response({"error": "missing name"}, status=400)
    try:
        payload, content_type = build_file(name, content)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    except Exception as exc:  # la page bascule sur un .txt si la génération échoue
        return web.json_response({"error": str(exc)[:200]}, status=502)
    return web.Response(
        body=payload,
        content_type=content_type,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Content-Disposition": f'attachment; filename="{name}"',
        },
    )


async def auth(request: web.Request) -> web.Response:
    """Identifie l'utilisateur, charge sa mémoire dans le LLM.

    POST /auth  body: {code}  → {ok, display_name, has_memory}
    (POST pour éviter que le code d'accès apparaisse en clair dans les logs nginx)
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "bad json"}, status=400)
    code = (data.get("code") or "").strip()
    if code not in _CODE_MAP:
        return web.json_response({"ok": False, "error": "code invalide"}, status=401)
    _init_services()
    profile = _CODE_MAP[code]
    has_memory = False
    if _memory and _llm:
        ctx = _memory.load_context(profile["member_id"])
        if ctx:
            _llm.load_memory(code, ctx)
            has_memory = True
    return web.json_response({
        "ok": True,
        "display_name": profile["display_name"],
        "has_memory": has_memory,
    })


async def health(request: web.Request) -> web.Response:
    """Sonde de disponibilité : teste la connexion MariaDB.

    GET /health → 200 {server, db, llm} ou 503 si la DB est en erreur.
    """
    status: dict = {"server": "ok", "db": "not_init", "llm": "not_init"}
    http_status = 200
    if _llm is not None:
        status["llm"] = "ok"
        status["web_tools"] = bool(getattr(_llm, "_tools", None))
    if _store is not None:
        try:
            _store._exec("SELECT 1")
            status["db"] = "ok"
        except Exception:
            status["db"] = "error"
            http_status = 503
    return web.json_response(status, status=http_status)


async def ask(request: web.Request) -> web.Response:
    """Appel Mistral direct avec mémoire long-terme (remplace le webhook n8n).

    POST /ask  body: {message, code}  → {reply}
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    code = (data.get("code") or "").strip()
    message = (data.get("message") or "").strip()[:4000]
    if not message:
        return web.json_response({"error": "message vide"}, status=400)
    if code not in _CODE_MAP:
        return web.json_response({"error": "code invalide"}, status=401)
    if not _check_rate(code):
        return web.json_response({"error": "trop de requêtes, réessaie dans une heure"}, status=429)
    _init_services()
    if _llm is None:
        return web.json_response({"error": "LLM non initialisé"}, status=503)
    # Avec accès web, un énoncé peut enchaîner recherche + fetch + synthèse :
    # on laisse plus de marge qu'une réponse LLM directe.
    timeout = 60.0 if getattr(_llm, "_tools", None) else 30.0
    try:
        reply = await asyncio.wait_for(_llm.reply(message, session_id=code), timeout=timeout)
    except asyncio.TimeoutError:
        return web.json_response({"error": "délai dépassé, réessaie"}, status=504)
    except Exception as exc:
        return web.json_response({"error": str(exc)[:300]}, status=502)
    return web.json_response({"reply": reply})


async def session_end(request: web.Request) -> web.Response:
    """Extrait la mémoire de la session et la persiste en MariaDB.

    POST /session/end  body: {code}  → {ok, saved}
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    code = (data.get("code") or "").strip()
    if code not in _CODE_MAP or _llm is None:
        return web.json_response({"ok": True, "saved": 0})
    history = _llm.get_history(code)
    _llm.unload_memory(code)
    saved = 0
    if history and _memory:
        profile = _CODE_MAP[code]
        try:
            saved = await _memory.extract_and_save(
                profile["member_id"], _TENANT_ID, f"web-{code[:8]}", history
            )
        except Exception as exc:
            print(f"[VindIA] extract_and_save: {exc}")
    return web.json_response({"ok": True, "saved": saved})


# ──────────────────────────────────────────────────────────────
# Projets & fichiers — espaces PRIVÉS par membre (isolation stricte)
# Le member_id découle du code d'accès : un utilisateur ne touche QUE ses projets.
# ──────────────────────────────────────────────────────────────

def _member_of(code: str):
    """member_id du code d'accès, ou None si code invalide. Clé de l'isolation."""
    profile = _CODE_MAP.get(code)
    return profile["member_id"] if profile else None


async def projects_list(request: web.Request) -> web.Response:
    """POST /projects/list {code} → {projects:[{project_id,name,created_at,documents}]}"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    member_id = _member_of((data.get("code") or "").strip())
    if member_id is None:
        return web.json_response({"error": "code invalide"}, status=401)
    _init_services()
    projs = _projects.list_projects(member_id)
    return web.json_response({"projects": [p.as_dict() for p in projs]})


async def projects_create(request: web.Request) -> web.Response:
    """POST /projects/create {code, name} → {project}"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    member_id = _member_of((data.get("code") or "").strip())
    if member_id is None:
        return web.json_response({"error": "code invalide"}, status=401)
    name = (data.get("name") or "").strip()[:120]
    if not name:
        return web.json_response({"error": "nom de projet vide"}, status=400)
    _init_services()
    proj = _projects.create_project(member_id, name)
    return web.json_response({"project": proj.as_dict()})


async def projects_activate(request: web.Request) -> web.Response:
    """POST /projects/activate {code, project_id} → charge les docs du projet dans le LLM.

    project_id vide → désactive le projet courant (revient au contexte sans projet).
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    code = (data.get("code") or "").strip()
    member_id = _member_of(code)
    if member_id is None:
        return web.json_response({"error": "code invalide"}, status=401)
    _init_services()
    project_id = (data.get("project_id") or "").strip()
    ctx = ""
    name = None
    if project_id:
        proj = _projects.get_project(member_id, project_id)
        if proj is None:
            return web.json_response({"error": "projet inconnu"}, status=404)
        ctx = _projects.build_context(member_id, project_id)
        name = proj.name
    if _llm is not None and hasattr(_llm, "load_project"):
        _llm.load_project(code, ctx)
    return web.json_response({"ok": True, "active": name})


async def upload(request: web.Request) -> web.Response:
    """POST /upload (multipart: code, project_id, file) → ingère le fichier dans le projet.

    Le texte extrait est rangé dans l'espace privé du membre puis (si la session
    a ce projet actif) reflété dans le contexte du LLM.
    """
    if request.content_length and request.content_length > _MAX_UPLOAD:
        return web.json_response({"error": "fichier trop volumineux (max 10 Mo)"}, status=413)
    try:
        reader = await request.multipart()
    except Exception:
        return web.json_response({"error": "multipart attendu"}, status=400)

    code = project_id = filename = None
    payload = b""
    async for part in reader:
        if part.name == "code":
            code = (await part.text()).strip()
        elif part.name == "project_id":
            project_id = (await part.text()).strip()
        elif part.name == "file":
            filename = part.filename or "fichier"
            payload = await part.read(decode=False)
            if len(payload) > _MAX_UPLOAD:
                return web.json_response({"error": "fichier trop volumineux (max 10 Mo)"}, status=413)

    member_id = _member_of(code or "")
    if member_id is None:
        return web.json_response({"error": "code invalide"}, status=401)
    if not project_id:
        return web.json_response({"error": "project_id manquant"}, status=400)
    if not payload:
        return web.json_response({"error": "fichier vide"}, status=400)
    if not _check_rate(code):
        return web.json_response({"error": "trop de requêtes, réessaie dans une heure"}, status=429)
    _init_services()
    if _projects.get_project(member_id, project_id) is None:
        return web.json_response({"error": "projet inconnu"}, status=404)
    try:
        text = extract_text(filename, payload)
    except ExtractionError as exc:
        return web.json_response({"error": str(exc)}, status=415)
    except Exception as exc:
        return web.json_response({"error": f"extraction impossible : {str(exc)[:200]}"}, status=502)
    if not text.strip():
        return web.json_response({"error": "aucun texte exploitable dans le fichier"}, status=422)
    doc = _projects.add_document(member_id, project_id, filename, text)
    # Si ce projet est actif pour la session, rafraîchir le contexte du LLM.
    if _llm is not None and hasattr(_llm, "load_project"):
        _llm.load_project(code, _projects.build_context(member_id, project_id))
    return web.json_response({"ok": True, "filename": doc.filename, "chars": doc.chars})


# ──────────────────────────────────────────────────────────────
# Connexions & OAuth — coffre chiffré, par utilisateur
# ──────────────────────────────────────────────────────────────

# Catalogue des services proposés à la connexion (libellés affichés dans l'onglet).
_SERVICE_CATALOG = [
    {"service": "google", "label": "Google — Gmail, Agenda, Drive"},
    {"service": "notion", "label": "Notion", "soon": True},
    {"service": "imap", "label": "Autre messagerie (IMAP)", "soon": True},
]


async def connections_list(request: web.Request) -> web.Response:
    """POST /connections/list {code} → état des connexions du membre (sans secrets)."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    member_id = _member_of((data.get("code") or "").strip())
    if member_id is None:
        return web.json_response({"error": "code invalide"}, status=401)
    _init_services()
    connected = {}
    if _vault is not None:
        connected = {c.service: c.as_dict() for c in _vault.list_connections(member_id)}
    items = []
    for entry in _SERVICE_CATALOG:
        svc = entry["service"]
        configured = svc == "google" and _google is not None and _google.configured
        items.append({
            "service": svc,
            "label": entry["label"],
            "soon": entry.get("soon", False),
            "configured": configured,
            "connected": svc in connected,
            "meta": connected.get(svc, {}).get("meta", {}),
        })
    return web.json_response({"vault_ready": _vault is not None, "services": items})


async def connections_disconnect(request: web.Request) -> web.Response:
    """POST /connections/disconnect {code, service} → retire la connexion (efface les secrets)."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    code = (data.get("code") or "").strip()
    member_id = _member_of(code)
    if member_id is None:
        return web.json_response({"error": "code invalide"}, status=401)
    _init_services()
    service = (data.get("service") or "").strip()
    removed = _vault.delete(member_id, service) if _vault is not None else False
    return web.json_response({"ok": True, "removed": removed})


def _prune_oauth_states() -> None:
    now = time.monotonic()
    for st in [s for s, (_, ts) in _oauth_states.items() if now - ts > _OAUTH_STATE_TTL]:
        _oauth_states.pop(st, None)


async def oauth_google_start(request: web.Request) -> web.Response:
    """POST /oauth/google/start {code} → {auth_url} vers lequel la page redirige."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    code = (data.get("code") or "").strip()
    member_id = _member_of(code)
    if member_id is None:
        return web.json_response({"error": "code invalide"}, status=401)
    _init_services()
    if _vault is None:
        return web.json_response({"error": "coffre non configuré (VINDIA_VAULT_KEY manquante)"}, status=503)
    if _google is None or not _google.configured:
        return web.json_response({"error": "Google non configuré côté serveur"}, status=503)
    _prune_oauth_states()
    state = _secrets.token_urlsafe(24)
    _oauth_states[state] = (member_id, time.monotonic())
    return web.json_response({"auth_url": _google.build_auth_url(state)})


async def oauth_google_callback(request: web.Request) -> web.Response:
    """GET /oauth/google/callback?code&state → Google redirige ici après consentement."""
    if request.query.get("error"):
        raise web.HTTPFound("/?connect=refus")
    code = request.query.get("code") or ""
    state = request.query.get("state") or ""
    _prune_oauth_states()
    entry = _oauth_states.pop(state, None)
    if entry is None:
        raise web.HTTPFound("/?connect=expire")
    member_id, _ = entry
    _init_services()
    if _google is None or _vault is None:
        raise web.HTTPFound("/?connect=erreur")
    try:
        token = await _google.exchange_code(code)
        info = await _google.fetch_userinfo(token.get("access_token", ""))
        secrets_payload = secrets_from_token_response(token)
        # Reconnexion : Google peut ne pas renvoyer de refresh_token → garder l'ancien.
        if not secrets_payload.get("refresh_token"):
            old = _vault.get_secrets(member_id, "google") or {}
            if old.get("refresh_token"):
                secrets_payload["refresh_token"] = old["refresh_token"]
        _vault.store(
            member_id, "google", secrets_payload,
            meta={"email": info.get("email", ""), "name": info.get("name", ""), "scope": token.get("scope", "")},
        )
    except Exception as exc:
        print(f"[VindIA] OAuth Google callback: {exc}")
        raise web.HTTPFound("/?connect=erreur")
    raise web.HTTPFound("/?connect=ok")


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/token", token)
    app.router.add_get("/health", health)
    app.router.add_post("/auth", auth)
    app.router.add_post("/ask", ask)
    app.router.add_post("/session/end", session_end)
    app.router.add_post("/tts", tts)
    app.router.add_post("/build", build)
    app.router.add_post("/projects/list", projects_list)
    app.router.add_post("/projects/create", projects_create)
    app.router.add_post("/projects/activate", projects_activate)
    app.router.add_post("/upload", upload)
    app.router.add_post("/connections/list", connections_list)
    app.router.add_post("/connections/disconnect", connections_disconnect)
    app.router.add_post("/oauth/google/start", oauth_google_start)
    app.router.add_get("/oauth/google/callback", oauth_google_callback)
    app.router.add_get("/{name}", static_file)
    return app


if __name__ == "__main__":
    web.run_app(build_app(), host="127.0.0.1", port=PORT)
