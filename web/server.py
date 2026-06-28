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
from shared.agent.project_tools import build_project_tools
from shared.agent.tools import ToolRegistry
from shared.agent.supabase_auth import SupabaseAuth, bearer_token
from shared.agent.approvals import ApprovalStore, APPROVED
from shared.agent.telegram_notify import build_telegram_notifier

ROOM = os.environ.get("VINDIA_ROOM", "vindia")
URL = os.environ["LIVEKIT_URL"]
KEY = os.environ["LIVEKIT_API_KEY"]
SECRET = os.environ["LIVEKIT_API_SECRET"]
PORT = int(os.environ.get("VINDIA_WEB_PORT", "8092"))
WEB_DIR = Path(__file__).resolve().parent
TTS_VOICE = os.environ.get("VINDIA_TTS_VOICE", "fr-FR-VivienneMultilingualNeural")
TTS_RATE = os.environ.get("VINDIA_TTS_RATE", "-6%")

# ──────────────────────────────────────────────────────────────
# Identités VindIA : VRAI login (Supabase Auth, email/mot de passe).
# La page envoie le jeton Supabase (en-tête Authorization: Bearer …) ; le serveur
# le valide → member_id = id Supabase, email, admin. Plus de code partagé.
# ──────────────────────────────────────────────────────────────
_TENANT_ID = "00000001-0001-0001-0001-000000000001"
# Emails admin (outils VPS) — liste blanche, séparés par des virgules.
_ADMIN_EMAILS = [e.strip().lower() for e in os.environ.get("VINDIA_ADMIN_EMAILS", "").split(",") if e.strip()]
_SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
_SUPABASE_ANON = os.environ.get("SUPABASE_ANON_KEY", "").strip()

# Services lazily initialisés (MariaDB optionnel : la mémoire est désactivée si absent)
_store = None
_memory = None
_llm = None
_auth = None      # SupabaseAuth : valide les jetons de login (None si non configuré)
_projects = None  # ProjectStore : espaces projet PRIVÉS par membre (persistance disque)
_vault = None     # CredentialVault : coffre chiffré des connexions (Google, mail…)
_google = None    # GoogleOAuth : config app OAuth (None/non configuré si clés absentes)
_vps_tools = []   # outils VPS (lecture seule) — RÉSERVÉS à l'admin, hors registre global
_approvals = None # ApprovalStore : validation humaine des comptes (pending/approved/refused)
_telegram = None  # TelegramNotifier : alerte l'admin d'une nouvelle inscription (ou None)

# Espace de données VindIA (projets/fichiers) — hors repo, hors MariaDB.
_DATA_DIR = os.environ.get("VINDIA_DATA_DIR", "/root/vindia-data")
# Taille max d'un fichier uploadé (anti-DoS) : 10 Mo par fichier.
_MAX_UPLOAD = 10 * 1024 * 1024
# Upload multiple (dossier local) : bornes cumulées sur une requête.
_MAX_BATCH = 60 * 1024 * 1024   # 60 Mo cumulés par requête
_MAX_FILES = 50                 # nb max de fichiers par requête
# URL publique (pour le redirect OAuth). Ex : https://vindia.faugere-davy.fr
_PUBLIC_URL = os.environ.get("VINDIA_PUBLIC_URL", "").rstrip("/")
# States OAuth en cours : state -> (member_id, timestamp monotonic). Anti-CSRF, TTL court.
_oauth_states: dict = {}
_OAUTH_STATE_TTL = 600.0
# Projet de référence actif par session (code → project_id). Détermine les outils
# fichiers (lister/lire/écrire) que VindIA reçoit pour cet utilisateur.
_active_project: dict = {}

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
    global _store, _memory, _llm, _projects, _vault, _google, _vps_tools, _auth, _approvals, _telegram
    if _llm is not None:
        return
    # Auth Supabase : valide les jetons de login. Sans config → personne ne peut
    # s'authentifier (toutes les routes protégées renverront 401).
    if _SUPABASE_URL and _SUPABASE_ANON:
        _auth = SupabaseAuth(_SUPABASE_URL, _SUPABASE_ANON, _ADMIN_EMAILS)
        print(f"[VindIA] Auth Supabase configurée (admins: {len(_ADMIN_EMAILS)}).")
    # Validation humaine des comptes : un inscrit attend l'aval de l'admin.
    _approvals = ApprovalStore(os.path.join(_DATA_DIR, "approvals"))
    # Notification Telegram à l'admin (nouvelle inscription) — None si non configuré.
    _telegram = build_telegram_notifier()
    if _telegram:
        print("[VindIA] Notifications Telegram actives.")
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
    from shared.agent.vps_ops import build_vps_tools
    # Outils GLOBAUX (tous les utilisateurs) : accès web seulement (info publique).
    _web_tools = build_web_tool_registry()
    _llm = MistralLLM(tools=_web_tools)
    if _web_tools:
        print(f"[VindIA] Accès web activé ({len(_web_tools)} outils).")
    # Outils ADMIN (réservés à Davy) : état du VPS. PAS dans le registre global →
    # Ludivine / Invité ne peuvent jamais les invoquer. Injectés par /ask si admin.
    _vps_tools = build_vps_tools()
    if _vps_tools:
        print(f"[VindIA] Connecteur VPS actif ({len(_vps_tools)} outils, admin only).")
    try:
        from server.db import open_store
        from shared.agent.memory import MemoryStore
        _store = open_store()
        # Bootstrap : crée le tenant. Les membres sont créés à la volée au login
        # (member_id = id Supabase), cf. _identify().
        _store.ensure_tenant(_TENANT_ID, "VindIA")
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
    """Vérifie le login (jeton Supabase) et charge la mémoire de l'utilisateur.

    POST /auth  (en-tête Authorization: Bearer <jeton>)  → {ok, display_name, admin, has_memory}
    """
    ident = await _identify(request)
    if ident is None:
        return web.json_response({"ok": False, "error": "non authentifié"}, status=401)
    member_id = ident["member_id"]
    # Compte non encore validé par l'admin : on renvoie le statut (la page affiche
    # « en attente »), sans charger la mémoire ni donner accès.
    if not ident.get("approved"):
        return web.json_response({
            "ok": True, "approved": False, "status": ident.get("status"),
            "display_name": (ident.get("email") or "").split("@")[0] or "toi",
            "admin": False,
        })
    has_memory = False
    if _memory and _llm:
        ctx = _memory.load_context(member_id)
        if ctx:
            _llm.load_memory(member_id, ctx)
            has_memory = True
    display = (ident.get("email") or "").split("@")[0] or "toi"
    return web.json_response({
        "ok": True,
        "approved": True,
        "display_name": display,
        "admin": ident["admin"],
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
    ident, err = await _require_approved(request)
    if err:
        return err
    member_id = ident["member_id"]
    message = (data.get("message") or "").strip()[:4000]
    if not message:
        return web.json_response({"error": "message vide"}, status=400)
    if not _check_rate(member_id):
        return web.json_response({"error": "trop de requêtes, réessaie dans une heure"}, status=429)
    if _llm is None:
        return web.json_response({"error": "LLM non initialisé"}, status=503)
    # Outils de session : projet actif (lire/écrire, scopé membre+projet) + VPS si admin.
    # Le projet actif vient du corps de la requête (la page l'envoie à chaque message) —
    # robuste aux redémarrages ; à défaut, on retombe sur l'état mémoire _active_project.
    session_tools = []
    active_pid = (data.get("project_id") or "").strip() or _active_project.get(member_id)
    if active_pid and _projects is not None and _projects.get_project(member_id, active_pid):
        session_tools += build_project_tools(_projects, member_id, active_pid)
        # Rappelle à VindIA quels fichiers existent (index léger) pour qu'elle les lise.
        if hasattr(_llm, "load_project"):
            _llm.load_project(member_id, _projects.build_index(member_id, active_pid))
    if ident["admin"] and _vps_tools:
        session_tools += _vps_tools  # état du VPS : ADMIN uniquement
    extra_tools = ToolRegistry(session_tools) if session_tools else None
    # Avec outils (web et/ou projet), un énoncé peut enchaîner plusieurs appels :
    # on laisse plus de marge qu'une réponse LLM directe.
    timeout = 60.0 if (getattr(_llm, "_tools", None) or extra_tools) else 30.0
    try:
        reply = await asyncio.wait_for(
            _llm.reply(message, session_id=member_id, extra_tools=extra_tools), timeout=timeout
        )
    except asyncio.TimeoutError:
        return web.json_response({"error": "délai dépassé, réessaie"}, status=504)
    except Exception as exc:
        return web.json_response({"error": str(exc)[:300]}, status=502)
    return web.json_response({"reply": reply})


async def session_end(request: web.Request) -> web.Response:
    """Extrait la mémoire de la session et la persiste en MariaDB.

    POST /session/end  body: {code}  → {ok, saved}
    """
    ident = await _identify(request)
    if ident is None or _llm is None:
        return web.json_response({"ok": True, "saved": 0})
    member_id = ident["member_id"]
    history = _llm.get_history(member_id)
    _llm.unload_memory(member_id)
    saved = 0
    if history and _memory:
        try:
            saved = await _memory.extract_and_save(
                member_id, _TENANT_ID, f"web-{member_id[:8]}", history
            )
        except Exception as exc:
            print(f"[VindIA] extract_and_save: {exc}")
    return web.json_response({"ok": True, "saved": saved})


# ──────────────────────────────────────────────────────────────
# Projets & fichiers — espaces PRIVÉS par membre (isolation stricte)
# Le member_id découle du LOGIN Supabase : un utilisateur ne touche QUE ses données.
# ──────────────────────────────────────────────────────────────

async def _identify(request: web.Request):
    """Identité {member_id, email, admin, approved, status} depuis le jeton Supabase,
    ou None si non authentifié. Crée le membre à la volée et gère la validation humaine
    (admin auto-approuvé ; tout autre passe en « pending » + notification Telegram)."""
    _init_services()
    if _auth is None:
        return None
    ident = await _auth.verify(bearer_token(request.headers.get("Authorization", "")))
    if not ident:
        return None
    if _store is not None:
        try:
            _store.ensure_member(ident["member_id"], _TENANT_ID, ident.get("email") or "membre")
        except Exception:
            pass
    # Validation humaine : l'admin est toujours approuvé ; les autres attendent l'aval.
    if ident["admin"]:
        ident["status"], ident["approved"] = APPROVED, True
    else:
        status, is_new = _approvals.request(ident["member_id"], ident.get("email") or "")
        ident["status"], ident["approved"] = status, (status == APPROVED)
        if is_new and _telegram is not None:
            await _telegram.notify(
                f"VindIA — nouvelle inscription en attente de validation : {ident.get('email') or ident['member_id']}"
            )
    return ident


async def _require_approved(request: web.Request):
    """(identité, None) si connecté ET approuvé ; (None, réponse d'erreur) sinon."""
    ident = await _identify(request)
    if ident is None:
        return None, web.json_response({"error": "non authentifié"}, status=401)
    if not ident.get("approved"):
        return None, web.json_response(
            {"error": "compte en attente de validation", "status": ident.get("status")}, status=403
        )
    return ident, None


async def projects_list(request: web.Request) -> web.Response:
    """POST /projects/list → {projects:[…]} du membre connecté."""
    ident, err = await _require_approved(request)
    if err:
        return err
    projs = _projects.list_projects(ident["member_id"])
    return web.json_response({"projects": [p.as_dict() for p in projs]})


async def projects_create(request: web.Request) -> web.Response:
    """POST /projects/create {name} → {project}"""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident, err = await _require_approved(request)
    if err:
        return err
    name = (data.get("name") or "").strip()[:120]
    if not name:
        return web.json_response({"error": "nom de projet vide"}, status=400)
    proj = _projects.create_project(ident["member_id"], name)
    return web.json_response({"project": proj.as_dict()})


async def project_file(request: web.Request) -> web.Response:
    """POST /projects/file {project_id, filename} → contenu d'un fichier (pour télécharger).

    Récupère un fichier que VindIA a créé dans le projet. Lecture confinée à l'espace
    du membre connecté.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident, err = await _require_approved(request)
    if err:
        return err
    project_id = (data.get("project_id") or "").strip()
    filename = (data.get("filename") or "").strip()
    content = _projects.read_document(ident["member_id"], project_id, filename) if _projects else ""
    if not content:
        return web.json_response({"error": "fichier introuvable"}, status=404)
    return web.json_response({"filename": filename, "content": content})


async def projects_activate(request: web.Request) -> web.Response:
    """POST /projects/activate {code, project_id} → charge les docs du projet dans le LLM.

    project_id vide → désactive le projet courant (revient au contexte sans projet).
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident, err = await _require_approved(request)
    if err:
        return err
    member_id = ident["member_id"]
    project_id = (data.get("project_id") or "").strip()
    ctx = ""
    name = None
    if project_id:
        proj = _projects.get_project(member_id, project_id)
        if proj is None:
            return web.json_response({"error": "projet inconnu"}, status=404)
        # Index LÉGER (noms seulement) : VindIA lira les fichiers à la demande.
        ctx = _projects.build_index(member_id, project_id)
        name = proj.name
        _active_project[member_id] = project_id
    else:
        _active_project.pop(member_id, None)
    if _llm is not None and hasattr(_llm, "load_project"):
        _llm.load_project(member_id, ctx)
    return web.json_response({"ok": True, "active": name})


async def upload(request: web.Request) -> web.Response:
    """POST /upload (multipart: code, project_id, file[, file…]) → ingère 1..N fichiers.

    Accepte plusieurs parts « file » (sélection multiple ou dossier local) en UNE
    requête : les formats non gérés ou vides sont ignorés (listés dans `skipped`),
    les autres rangés dans l'espace privé du membre. Une seule actualisation du
    contexte LLM à la fin. Rétrocompatible avec l'envoi d'un fichier unique.
    """
    ident, err = await _require_approved(request)
    if err:
        return err
    member_id = ident["member_id"]
    try:
        reader = await request.multipart()
    except Exception:
        return web.json_response({"error": "multipart attendu"}, status=400)

    project_id = None
    files: list = []          # (filename, payload)
    total = 0
    async for part in reader:
        if part.name == "project_id":
            project_id = (await part.text()).strip()
        elif part.name == "file":
            payload = await part.read(decode=False)
            if len(payload) > _MAX_UPLOAD:
                return web.json_response({"error": f"« {part.filename} » dépasse 10 Mo"}, status=413)
            total += len(payload)
            if total > _MAX_BATCH:
                return web.json_response({"error": "envoi trop volumineux (max 60 Mo au total)"}, status=413)
            files.append((part.filename or "fichier", payload))
            if len(files) > _MAX_FILES:
                return web.json_response({"error": f"trop de fichiers (max {_MAX_FILES})"}, status=413)

    if not project_id:
        return web.json_response({"error": "project_id manquant"}, status=400)
    if not files:
        return web.json_response({"error": "aucun fichier"}, status=400)
    if not _check_rate(member_id):
        return web.json_response({"error": "trop de requêtes, réessaie dans une heure"}, status=429)
    if _projects.get_project(member_id, project_id) is None:
        return web.json_response({"error": "projet inconnu"}, status=404)

    added, skipped = [], []
    for filename, payload in files:
        if not payload:
            skipped.append({"filename": filename, "reason": "vide"})
            continue
        try:
            text = extract_text(filename, payload)
        except ExtractionError as exc:
            skipped.append({"filename": filename, "reason": str(exc)})
            continue
        except Exception as exc:
            skipped.append({"filename": filename, "reason": f"extraction: {str(exc)[:120]}"})
            continue
        if not text.strip():
            skipped.append({"filename": filename, "reason": "aucun texte exploitable"})
            continue
        doc = _projects.add_document(member_id, project_id, filename, text)
        added.append({"filename": doc.filename, "chars": doc.chars})

    # Rafraîchit l'index léger (noms) si ce projet est actif pour la session.
    if added and _active_project.get(member_id) == project_id and _llm is not None and hasattr(_llm, "load_project"):
        _llm.load_project(member_id, _projects.build_index(member_id, project_id))
    return web.json_response({"ok": True, "added": added, "skipped": skipped})


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
    ident, err = await _require_approved(request)
    if err:
        return err
    member_id = ident["member_id"]
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
    ident, err = await _require_approved(request)
    if err:
        return err
    service = (data.get("service") or "").strip()
    removed = _vault.delete(ident["member_id"], service) if _vault is not None else False
    return web.json_response({"ok": True, "removed": removed})


def _prune_oauth_states() -> None:
    now = time.monotonic()
    for st in [s for s, (_, ts) in _oauth_states.items() if now - ts > _OAUTH_STATE_TTL]:
        _oauth_states.pop(st, None)


async def oauth_google_start(request: web.Request) -> web.Response:
    """POST /oauth/google/start → {auth_url} vers lequel la page redirige."""
    ident, err = await _require_approved(request)
    if err:
        return err
    member_id = ident["member_id"]
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


# ──────────────────────────────────────────────────────────────
# Mémoire — l'utilisateur voit et gère ce que VindIA retient sur lui
# ──────────────────────────────────────────────────────────────

async def memory_list(request: web.Request) -> web.Response:
    """POST /memory/list → souvenirs du membre connecté (id + texte)."""
    ident, err = await _require_approved(request)
    if err:
        return err
    if _store is None:
        return web.json_response({"enabled": False, "memories": []})
    return web.json_response({"enabled": True, "memories": _store.list_memories(ident["member_id"])})


async def memory_forget(request: web.Request) -> web.Response:
    """POST /memory/forget {code, id} → efface UN souvenir du membre (RGPD/contrôle)."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident, err = await _require_approved(request)
    if err:
        return err
    member_id = ident["member_id"]
    if _store is None:
        return web.json_response({"ok": True, "removed": False})
    removed = _store.delete_memory(member_id, (data.get("id") or "").strip())
    # Rafraîchit la mémoire injectée dans la session courante (le souvenir effacé disparaît).
    if removed and _llm is not None and _memory is not None:
        _llm.load_memory(member_id, _memory.load_context(member_id))
    return web.json_response({"ok": True, "removed": removed})


# ──────────────────────────────────────────────────────────────
# Administration — validation humaine des comptes (admin uniquement)
# ──────────────────────────────────────────────────────────────

async def admin_pending(request: web.Request) -> web.Response:
    """POST /admin/pending → liste des comptes en attente. Admin uniquement."""
    ident = await _identify(request)
    if ident is None:
        return web.json_response({"error": "non authentifié"}, status=401)
    if not ident.get("admin"):
        return web.json_response({"error": "réservé à l'administrateur"}, status=403)
    pending = _approvals.list_by_status("pending") if _approvals else []
    return web.json_response({"pending": pending})


async def admin_decide(request: web.Request) -> web.Response:
    """POST /admin/decide {member_id, approve:bool} → valide ou refuse un compte. Admin only."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident = await _identify(request)
    if ident is None:
        return web.json_response({"error": "non authentifié"}, status=401)
    if not ident.get("admin"):
        return web.json_response({"error": "réservé à l'administrateur"}, status=403)
    target = (data.get("member_id") or "").strip()
    approve = bool(data.get("approve"))
    ok = _approvals.decide(target, approve) if _approvals else False
    return web.json_response({"ok": ok, "decision": "approved" if approve else "refused"})


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
    app.router.add_post("/projects/file", project_file)
    app.router.add_post("/upload", upload)
    app.router.add_post("/connections/list", connections_list)
    app.router.add_post("/connections/disconnect", connections_disconnect)
    app.router.add_post("/memory/list", memory_list)
    app.router.add_post("/memory/forget", memory_forget)
    app.router.add_post("/admin/pending", admin_pending)
    app.router.add_post("/admin/decide", admin_decide)
    app.router.add_post("/oauth/google/start", oauth_google_start)
    app.router.add_get("/oauth/google/callback", oauth_google_callback)
    app.router.add_get("/{name}", static_file)
    return app


if __name__ == "__main__":
    web.run_app(build_app(), host="127.0.0.1", port=PORT)
