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
import re
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

from shared.agent.officegen import build_file, OFFICE_TYPES
from shared.agent.projects import ProjectStore, extract_text, ExtractionError
from shared.agent.vault import CredentialVault, fernet_crypto
from shared.agent.oauth_google import GoogleOAuth, secrets_from_token_response
from shared.agent.project_tools import build_project_tools
from shared.agent.tools import ToolRegistry
from shared.agent.supabase_auth import SupabaseAuth, bearer_token
from shared.agent.agenda_tools import build_agenda_tools
from shared.agent.verifie_actions import controle as controle_actions
from shared.agent.approvals import ApprovalStore, APPROVED, PENDING
from shared.agent.telegram_notify import build_telegram_notifier
from shared.agent.email_notify import build_email_notifier, decision_message, signup_message
from shared.agent.adapters import ENGLISH_TUTOR_PROMPT
from shared.agent.connectors import (catalogue as connecteurs_catalogue, get_connecteur,
                                     page_id_depuis_url, vault_service, verifie_jeton)
from shared.agent.llm_transports import build_transports
from shared.agent.notion_tools import build_notion_tools
from shared.agent.providers import VAULT_SERVICE, catalogue, get_provider, verifie_cle
from shared.agent.skill_tools import build_skill_tools
from shared.agent.skills import SkillStore
from shared.agent.sync_store import SyncStore
from shared.agent.workspace_tools import build_workspace_tools
from shared.agent.synced_tools import build_synced_tools
from shared.agent.transcribe_tools import build_transcribe_tool

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
# Clé de service : seule à ouvrir l'API admin de Supabase. Sert à relire l'état réel
# de confirmation d'une adresse au moment d'une validation d'accès.
_SUPABASE_SERVICE = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
# PHASE D'ESSAI (VINDIA_AUTO_APPROVE=1) : l'accès s'ouvre sans validation manuelle.
# Ce n'est PAS un contournement de la confirmation d'adresse : arriver jusqu'ici
# suppose un jeton que Supabase a validé, or Supabase refuse la connexion tant que
# l'adresse n'est pas confirmée. Ce qui saute, c'est le seul aval humain.
# L'administrateur reste prévenu de chaque inscription et peut retirer un accès.
# Repasser à 0 (défaut) rétablit la validation manuelle, sans toucher au code.
_AUTO_APPROVE = os.environ.get("VINDIA_AUTO_APPROVE", "0").strip().lower() not in ("0", "", "false", "no")

# Services lazily initialisés (MariaDB optionnel : la mémoire est désactivée si absent)
_store = None
_memory = None
_agenda = None   # Agenda : mémoire factuelle (rendez-vous, traitements)
_llm = None
_auth = None      # SupabaseAuth : valide les jetons de login (None si non configuré)
_projects = None  # ProjectStore : espaces projet PRIVÉS par membre (persistance disque)
_vault = None     # CredentialVault : coffre chiffré des connexions (Google, mail…)
_google = None    # GoogleOAuth : config app OAuth (None/non configuré si clés absentes)
_vps_tools = []   # outils VPS (lecture seule) — RÉSERVÉS à l'admin, hors registre global
_approvals = None # ApprovalStore : validation humaine des comptes (pending/approved/refused)
_telegram = None  # TelegramNotifier : alerte l'admin d'une nouvelle inscription (ou None)
_email = None     # EmailNotifier : même alerte par e-mail (ou None si SMTP non configuré)
_skills = None    # SkillStore : fiches de méthode (livrées + personnelles)
_sync = None      # SyncStore : espaces de travail synchronisés avec l'application de bureau

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


_STT_LIMIT = 900          # transcriptions par heure et par membre (aperçus compris)
_stt_buckets: dict = defaultdict(list)


def _check_rate_stt(member_id: str) -> bool:
    now = time.monotonic()
    bucket = [t for t in _stt_buckets[member_id] if now - t < _RATE_WINDOW]
    if len(bucket) >= _STT_LIMIT:
        _stt_buckets[member_id] = bucket
        return False
    bucket.append(now)
    _stt_buckets[member_id] = bucket
    return True


def _init_services() -> None:
    global _store, _memory, _llm, _projects, _vault, _google, _vps_tools, _auth, _approvals, _telegram, _email, _sync, _skills, _agenda
    if _llm is not None:
        return
    # Auth Supabase : valide les jetons de login. Sans config → personne ne peut
    # s'authentifier (toutes les routes protégées renverront 401).
    if _SUPABASE_URL and _SUPABASE_ANON:
        _auth = SupabaseAuth(_SUPABASE_URL, _SUPABASE_ANON, _ADMIN_EMAILS,
                             service_key=_SUPABASE_SERVICE)
        print(f"[VindIA] Auth Supabase configurée (admins: {len(_ADMIN_EMAILS)}).")
    # Validation humaine des comptes : un inscrit attend l'aval de l'admin.
    _approvals = ApprovalStore(os.path.join(_DATA_DIR, "approvals"))
    # Notification Telegram à l'admin (nouvelle inscription) — None si non configuré.
    _telegram = build_telegram_notifier()
    if _telegram:
        print("[VindIA] Notifications Telegram actives.")
    _email = build_email_notifier()
    if _email:
        print("[VindIA] Alertes e-mail actives (nouvelles inscriptions).")
    # Espaces de travail synchronisés avec l'application de bureau.
    _sync = SyncStore(os.path.join(_DATA_DIR, "workspaces"))
    # Projets : magasin disque isolé par membre (indépendant de MariaDB).
    _projects = ProjectStore(os.path.join(_DATA_DIR, "projects"))
    # Compétences : fiches livrées avec le code + fiches personnelles par membre.
    _skills = SkillStore(
        str(_ROOT / "shared" / "agent" / "skills"),   # livrées avec le code
        os.path.join(_DATA_DIR, "skills"),            # personnelles, hors repo
    )
    print(f"[VindIA] Compétences chargées : {len(_skills.list_skills())} fiches livrées.")
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
        # Agenda : la mémoire FACTUELLE (rendez-vous, traitements, activités). Elle
        # partage la connexion MariaDB mais reste une table distincte de la mémoire
        # conversationnelle — l'une est reformulée par le modèle, l'autre fait foi.
        from shared.agent.agenda import Agenda
        _agenda = Agenda(_store._conn, paramstyle="format")
        _agenda.creer_tables()
        print("[VindIA] Agenda actif (fil d'Ariane, rappels).")
    except Exception as exc:
        print(f"[VindIA] MariaDB indisponible — mémoire désactivée : {exc}")
        _store = None
        _memory = None
        _agenda = None


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
            "display_name": ident.get("prenom") or "",
            "admin": False,
        })
    has_memory = False
    if _memory and _llm:
        ctx = _memory.load_context(member_id)
        if ctx:
            _llm.load_memory(member_id, ctx)
            has_memory = True
    # Le prénom est saisi à l'inscription : c'est lui qui doit servir. À défaut —
    # comptes créés avant que le formulaire le demande — on n'affiche RIEN plutôt que
    # de fabriquer un pseudo à partir de l'adresse : « Bonjour faugredavy » n'appelle
    # personne par son nom, et la page sait très bien se passer du prénom.
    return web.json_response({
        "ok": True,
        "approved": True,
        "display_name": ident.get("prenom") or "",
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
    # Mode de conversation. « english » = professeur d'anglais : prompt dédié qui REMPLACE
    # le prompt par défaut (lequel impose de répondre en français). Historique de session
    # séparé pour ne pas mélanger les deux conversations.
    mode = (data.get("mode") or "").strip().lower()
    system_override = ENGLISH_TUTOR_PROMPT if mode == "english" else None
    # Clé d'historique distincte du member_id : celui-ci reste l'identifiant d'isolation
    # (projets, fichiers, mémoire) et ne doit JAMAIS être altéré.
    session_key = f"{member_id}#en" if mode == "english" else member_id
    # Outils de session : projet actif (lire/écrire, scopé membre+projet) + VPS si admin.
    # Le projet actif vient du corps de la requête (la page l'envoie à chaque message) —
    # robuste aux redémarrages ; à défaut, on retombe sur l'état mémoire _active_project.
    session_tools = []
    # Compétences : le SOMMAIRE part dans le contexte, les fiches se lisent à la demande.
    # Canal distinct du projet → changer de projet ne fait pas oublier les méthodes.
    if _skills is not None:
        session_tools += build_skill_tools(_skills, member_id)
        if hasattr(_llm, "load_skills"):
            _llm.load_skills(session_key, _skills.build_index(member_id))
    active_pid = (data.get("project_id") or "").strip() or _active_project.get(member_id)
    active_proj = (
        _projects.get_project(member_id, active_pid) if (active_pid and _projects) else None
    )
    if active_proj is not None:
        session_tools += build_project_tools(_projects, member_id, active_pid)
        # Rappelle à VindIA quels fichiers existent (index léger) pour qu'elle les lise.
        if hasattr(_llm, "load_project"):
            _llm.load_project(member_id, _projects.build_index(member_id, active_pid))
    # Dossiers de l'ordinateur (application de bureau) : accessibles à TOUT membre, dans
    # son seul espace. Un projet actif AVEC des dossiers rattachés restreint la vue à
    # ceux-là — c'est le « dossier associé au projet » ; sinon, tous ses dossiers.
    if _sync is not None:
        allowed = active_proj.workspaces if (active_proj and active_proj.workspaces) else None
        session_tools += build_workspace_tools(_sync, member_id, allowed)
    # Agenda : le fil d'Ariane. Fourni a TOUT membre — c'est le coeur de l'usage,
    # pas une option reservee. Les outils sont figes sur ce member_id.
    if _agenda is not None:
        session_tools += build_agenda_tools(_agenda, member_id)
    session_tools += _outils_connectes(member_id)
    if ident["admin"] and _vps_tools:
        session_tools += _vps_tools  # état du VPS : ADMIN uniquement
    if ident["admin"]:
        # Dossier PC synchronisé (Syncthing) : lire/écrire + transcrire — ADMIN uniquement.
        _synced_dir = os.path.join(_DATA_DIR, "synced")
        session_tools += build_synced_tools(_synced_dir)
        session_tools.append(build_transcribe_tool(_synced_dir))
    extra_tools = ToolRegistry(session_tools) if session_tools else None
    # Avec outils (web et/ou projet), un énoncé peut enchaîner plusieurs appels :
    # on laisse plus de marge qu'une réponse LLM directe.
    timeout = 60.0 if (getattr(_llm, "_tools", None) or extra_tools) else 30.0
    # Trace des outils réellement appelés : sert à vérifier que la réponse n'affirme
    # pas une action qui n'a pas eu lieu.
    outils_appeles: list = []
    try:
        reply = await asyncio.wait_for(
            _llm.reply(
                message, session_id=session_key, extra_tools=extra_tools,
                system_override=system_override,
                transports=_transports_du_membre(member_id),
                journal_outils=outils_appeles,
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return web.json_response({"error": "délai dépassé, réessaie"}, status=504)
    except Exception as exc:
        return web.json_response({"error": str(exc)[:300]}, status=502)
    # Garde-fou anti-mensonge : une affirmation de livraison n'est autorisee que si un
    # outil d'ecriture a tourne, ou si la reponse porte le marqueur [[FICHIER:]]. Sans
    # preuve, la phrase est RETIREE. La consigne systeme ne suffit pas : « j'ai cree le
    # fichier » est la suite la plus plausible apres une demande de document, donc le
    # modele la produit meme quand c'est faux.
    reply, corrige = controle_actions(reply, outils_appeles)
    if corrige:
        print(f"[VindIA] affirmation non prouvee retiree (outils: {outils_appeles or 'aucun'})",
              flush=True)
    # Le fichier produit rejoint AUSSI le dossier synchronisé quand la personne en a
    # un. Sans cela, tout reposait sur le choix d'outil du modèle : il émettait le
    # marqueur de téléchargement, la personne cherchait dans ses dossiers, et ne
    # trouvait rien. Une consigne ne suffit pas — le modèle en dévie.
    if ident["admin"] and "synced_write_file" not in outils_appeles:
        depose = await _deposer_dans_le_dossier(reply)
        if depose:
            reply = f"{reply}\n\nJe l'ai aussi déposé dans ton dossier : {depose}."
    return web.json_response({"reply": reply})


async def _deposer_dans_le_dossier(texte: str) -> str:
    """Écrit dans le dossier synchronisé le fichier annoncé par [[FICHIER:…]].

    Retourne le nom déposé, ou "" si rien n'a été écrit.

    Pourquoi côté serveur plutôt qu'en consigne : le modèle choisissait le marqueur de
    téléchargement alors que la personne allait chercher le fichier dans ses dossiers,
    et ne trouvait rien. Une consigne ne suffit pas — il en dévie. Ici, dès qu'un
    fichier est produit et qu'un dossier synchronisé existe, il y est écrit, quel que
    soit le chemin choisi par le modèle.

    Best-effort : un échec ne doit jamais faire perdre la réponse ni le téléchargement.
    """
    m = re.search(r"\[\[FICHIER:([^\]]+)\]\](.*?)\[\[/FICHIER\]\]", texte or "", re.S)
    if not m:
        return ""
    nom, contenu = m.group(1).strip(), m.group(2)
    if not nom or not contenu.strip():
        return ""
    try:
        from shared.agent.synced_tools import SyncedWriteTool

        outil = SyncedWriteTool(os.path.join(_DATA_DIR, "synced"))
        retour = await outil.run({"filename": nom, "content": contenu})
        if str(retour).lower().startswith("erreur"):
            return ""
        return nom
    except Exception as exc:  # noqa: BLE001
        print(f"[VindIA] dépôt dans le dossier impossible : {exc}", flush=True)
        return ""


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
        # Arriver ici signifie que Supabase a validé un jeton — donc que l'adresse a
        # été confirmée. C'est la seule preuve dont on dispose côté serveur.
        _approvals.marquer_adresse_confirmee(ident["member_id"])
        # Phase d'essai : on ouvre l'accès tout de suite plutôt que de laisser la
        # personne devant un écran d'attente. L'administrateur est prévenu quand même.
        if _AUTO_APPROVE and status == PENDING:
            _approvals.decide(ident["member_id"], True)
            status = APPROVED
        ident["status"], ident["approved"] = status, (status == APPROVED)
        if is_new:
            # Alerter l'administrateur : sans cela une inscription passe inaperçue et
            # la personne attend indéfiniment. Best-effort sur les deux canaux.
            who = ident.get("email") or ident["member_id"]
            if _telegram is not None:
                await _telegram.notify(
                    f"VindIA — nouvelle inscription en attente de validation : {who}"
                )
            if _email is not None:
                subject, body = signup_message(ident.get("email", ""), ident["member_id"], _PUBLIC_URL)
                await _email.notify(subject, body)
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


def _outils_connectes(member_id: str) -> list:
    """Outils des services que CE membre a branchés (Notion…), et eux seuls.

    Aucun accès n'est hérité : le jeton vient du coffre du membre, et les outils sont
    construits pour ce jeton. Un autre utilisateur branchera son propre espace.
    """
    if _vault is None:
        return []
    outils = []
    secrets = _vault.get_secrets(member_id, vault_service("notion")) or {}
    if secrets.get("token"):
        outils += build_notion_tools(secrets["token"], parent_id=secrets.get("parent") or "")
    return outils


def _transports_du_membre(member_id: str):
    """(texte, outils) bâtis sur la clé du membre, ou None s'il n'en a pas posé.

    La clé vit dans le coffre chiffré, isolée par membre : elle ne transite jamais
    par la page une fois enregistrée, et un membre ne peut pas lire celle d'un autre.
    """
    if _vault is None:
        return None
    secrets = _vault.get_secrets(member_id, VAULT_SERVICE)
    if not secrets or not secrets.get("api_key"):
        return None
    p = get_provider(secrets.get("provider") or "")
    if p is None:
        return None
    modele = (secrets.get("model") or "").strip() or p.modele_defaut
    return build_transports(p.famille, p.base_url, secrets["api_key"], modele)


# Alerte à l'INSCRIPTION, pas à la première connexion. L'inscription se fait chez
# Supabase, directement depuis la page : le serveur n'en sait rien tant que la
# personne ne s'est pas connectée. Quelqu'un qui s'inscrit puis ne revient jamais
# resterait donc invisible — c'est arrivé.
# Cet endpoint est forcément ANONYME (aucune session tant que l'adresse n'est pas
# confirmée), d'où une limite stricte par adresse IP : sans elle, il suffirait de
# le découvrir pour inonder la boîte de l'administrateur.
_SIGNUP_LIMIT = 5           # inscriptions signalées par heure et par IP
_signup_buckets: dict = defaultdict(list)


def _check_rate_signup(ip: str) -> bool:
    now = time.monotonic()
    bucket = [t for t in _signup_buckets[ip] if now - t < _RATE_WINDOW]
    if len(bucket) >= _SIGNUP_LIMIT:
        _signup_buckets[ip] = bucket
        return False
    bucket.append(now)
    _signup_buckets[ip] = bucket
    return True


async def admin_supprimer(request: web.Request) -> web.Response:
    """POST /admin/supprimer {member_id} → retire le compte de la liste.

    Le dossier VindIA est supprimé : le compte n'apparaît plus et n'a plus aucun
    accès. Le compte d'authentification Supabase, lui, n'est effacé qu'à condition
    de disposer d'une clé d'administration — on ne l'exige pas, car héberger cette
    clé donnerait au serveur un pouvoir bien plus large que ce seul usage.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident = await _identify(request)
    if ident is None:
        return web.json_response({"error": "non authentifié"}, status=401)
    if not ident.get("admin"):
        return web.json_response({"error": "réservé à l'administrateur"}, status=403)
    cible = (data.get("member_id") or "").strip()
    if cible == ident["member_id"]:
        return web.json_response({"error": "tu ne peux pas supprimer ton propre compte"}, status=400)
    dossier = _approvals.get(cible) if _approvals else None
    if dossier is None:
        return web.json_response({"error": "compte inconnu"}, status=404)
    email = dossier.get("email") or ""
    _approvals.supprimer(cible)

    # Suppression chez Supabase : seulement si une clé d'administration est fournie.
    supprime_partout = False
    cle_admin = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
    if cle_admin:
        try:
            import aiohttp

            async with aiohttp.ClientSession() as sess:
                async with sess.delete(
                    f"{_SUPABASE_URL}/auth/v1/admin/users/{cible}",
                    headers={"apikey": cle_admin, "Authorization": f"Bearer {cle_admin}"},
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    supprime_partout = resp.status < 300
        except Exception:
            supprime_partout = False

    return web.json_response({
        "ok": True, "email": email, "supprime_partout": supprime_partout,
        "message": (f"{email} supprimé définitivement."
                    if supprime_partout
                    else f"{email} retiré de VindIA — il n'a plus aucun accès. "
                         "Son compte de connexion subsiste chez Supabase."),
    })


async def admin_relancer(request: web.Request) -> web.Response:
    """POST /admin/relancer {member_id, type} → renvoie un e-mail à la personne.

    `type` = "confirmation" (relancer la confirmation d'adresse) ou "motdepasse"
    (lien de réinitialisation). Quelqu'un qui n'a jamais confirmé, ou qui a oublié
    son mot de passe, est aujourd'hui bloqué sans recours visible côté administrateur.
    Les deux passent par les points d'entrée PUBLICS de Supabase : aucune clé
    d'administration n'est nécessaire, donc aucun secret supplémentaire à héberger.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident = await _identify(request)
    if ident is None:
        return web.json_response({"error": "non authentifié"}, status=401)
    if not ident.get("admin"):
        return web.json_response({"error": "réservé à l'administrateur"}, status=403)
    dossier = _approvals.get((data.get("member_id") or "").strip()) if _approvals else None
    email = (dossier or {}).get("email") or ""
    if not email:
        return web.json_response({"error": "compte inconnu"}, status=404)
    genre = (data.get("type") or "confirmation").strip()
    chemin = "/auth/v1/recover" if genre == "motdepasse" else "/auth/v1/resend"
    corps = ({"email": email} if genre == "motdepasse"
             else {"type": "signup", "email": email})
    try:
        import aiohttp

        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                f"{_SUPABASE_URL}{chemin}",
                json=corps,
                headers={"apikey": _SUPABASE_ANON, "Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status >= 400:
                    detail = (await resp.text())[:160]
                    return web.json_response(
                        {"error": f"Supabase a refusé l'envoi ({resp.status}). {detail}"},
                        status=502)
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": f"envoi impossible : {str(exc)[:140]}"}, status=502)
    quoi = "lien de réinitialisation" if genre == "motdepasse" else "e-mail de confirmation"
    return web.json_response({"ok": True, "message": f"{quoi.capitalize()} renvoyé à {email}."})


async def signup_notify(request: web.Request) -> web.Response:
    """POST /signup/notify {email, member_id} → enregistre la demande et alerte l'admin.

    Appelé par la page juste après une inscription réussie.
    """
    ip = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For", "") or "?"
    ip = ip.split(",")[0].strip()
    if not _check_rate_signup(ip):
        return web.json_response({"error": "trop de demandes"}, status=429)
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    _init_services()
    email = (data.get("email") or "").strip().lower()[:200]
    member_id = (data.get("member_id") or "").strip()[:36]
    # On exige un identifiant Supabase plausible : la page le reçoit à l'inscription.
    # Sans lui, n'importe quel formulaire forgé déclencherait une alerte.
    if not email or "@" not in email or not re.match(r"^[0-9a-fA-F-]{36}$", member_id):
        return web.json_response({"error": "demande invalide"}, status=400)
    if _approvals is None:
        return web.json_response({"ok": False}, status=503)
    statut, nouveau = _approvals.request(member_id, email)
    if nouveau:
        if _telegram is not None:
            await _telegram.notify(f"VindIA — nouvelle inscription en attente de validation : {email}")
        if _email is not None:
            sujet, corps = signup_message(email, member_id, _PUBLIC_URL)
            await _email.notify(sujet, corps)
    return web.json_response({"ok": True, "status": statut})


async def stt(request: web.Request) -> web.Response:
    """POST /stt (audio brut) → {text} — transcription par Voxtral.

    Indispensable hors de Chrome : la reconnaissance vocale du navigateur s'appuie
    sur un service Google absent d'une application installée (erreur « network »)
    et de Firefox. On transcrit donc nous-mêmes, ce qui marche partout — et reste
    en Europe, comme le reste de la chaîne.
    """
    ident, err = await _require_approved(request)
    if err:
        return err
    # Limite DÉDIÉE : l'aperçu au fil de la parole appelle cet endpoint toutes les
    # quelques secondes. Le quota conversationnel (60/h) serait épuisé en quelques
    # messages — ce qui couperait le micro sans raison apparente.
    if not _check_rate_stt(ident["member_id"]):
        return web.json_response({"error": "trop de transcriptions, patiente un peu"}, status=429)
    data = await request.read()
    if not data:
        return web.json_response({"error": "audio vide"}, status=400)
    if len(data) > _MAX_UPLOAD:
        return web.json_response({"error": "enregistrement trop long"}, status=413)
    try:
        audio = await asyncio.get_running_loop().run_in_executor(None, _vers_mp3, data)
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": f"audio illisible : {str(exc)[:120]}"}, status=400)
    try:
        from shared.agent.adapters import VoxtralSTT

        texte = await asyncio.wait_for(VoxtralSTT().transcribe(audio, "fr-FR"), timeout=90)
    except asyncio.TimeoutError:
        return web.json_response({"error": "transcription trop longue"}, status=504)
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": str(exc)[:200]}, status=502)
    return web.json_response({"text": (texte or "").strip()})


def _vers_mp3(data: bytes) -> bytes:
    """Convertit l'enregistrement du navigateur (webm/opus) en MP3 mono 16 kHz.

    Le format produit par MediaRecorder varie selon le navigateur ; ffmpeg le
    normalise, ce qui évite de dépendre de ce que le poste a bien voulu encoder.
    """
    import subprocess

    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
         "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", "-f", "mp3", "pipe:1"],
        input=data, capture_output=True, timeout=120,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError((proc.stderr or b"").decode("utf-8", "replace")[:160] or "conversion échouée")
    return proc.stdout


async def connect_catalogue(request: web.Request) -> web.Response:
    """POST /connect/catalogue → services branchables + ceux déjà branchés."""
    ident, err = await _require_approved(request)
    if err:
        return err
    branches = []
    if _vault is not None:
        for c in connecteurs_catalogue():
            sec = _vault.get_secrets(ident["member_id"], vault_service(c["code"])) or {}
            if sec.get("token"):
                # On dit ce qui est branché et si l'écriture est possible — jamais le jeton.
                branches.append({"code": c["code"], "ecriture": bool(sec.get("parent"))})
    return web.json_response({"services": connecteurs_catalogue(), "branches": branches})


async def connect_save(request: web.Request) -> web.Response:
    """POST /connect/save {service, token} → range le jeton dans le coffre du membre."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident, err = await _require_approved(request)
    if err:
        return err
    if _vault is None:
        return web.json_response({"error": "coffre indisponible"}, status=503)
    code = (data.get("service") or "").strip().lower()
    jeton = (data.get("token") or "").strip()
    probleme = verifie_jeton(code, jeton)
    if probleme:
        return web.json_response({"error": probleme}, status=400)
    # Page de dépôt : collée telle quelle depuis le navigateur. Sans elle, VindIA
    # lit mais n'écrit pas — elle n'aurait aucun endroit légitime où créer.
    parent = page_id_depuis_url(data.get("parent") or "")
    if (data.get("parent") or "").strip() and not parent:
        return web.json_response(
            {"error": "Adresse de page Notion non reconnue. Copie le lien depuis Notion."},
            status=400)
    _vault.store(ident["member_id"], vault_service(code),
                 {"token": jeton, "parent": parent},
                 {"service": code, "a_page_depot": bool(parent)})
    return web.json_response({"ok": True, "service": get_connecteur(code).nom,
                              "ecriture": bool(parent)})


async def connect_remove(request: web.Request) -> web.Response:
    """POST /connect/remove {service} → débranche le service."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident, err = await _require_approved(request)
    if err:
        return err
    code = (data.get("service") or "").strip().lower()
    ok = _vault.delete(ident["member_id"], vault_service(code)) if _vault else False
    return web.json_response({"ok": bool(ok)})


async def llm_catalogue(request: web.Request) -> web.Response:
    """POST /llm/catalogue → fournisseurs disponibles + connexion actuelle du membre."""
    ident, err = await _require_approved(request)
    if err:
        return err
    actuel = None
    if _vault is not None:
        s = _vault.get_secrets(ident["member_id"], VAULT_SERVICE) or {}
        if s.get("api_key"):
            # On renvoie le fournisseur et le modèle, JAMAIS la clé.
            actuel = {"provider": s.get("provider"), "model": s.get("model") or ""}
    return web.json_response({"providers": catalogue(), "actuel": actuel})


async def llm_connect(request: web.Request) -> web.Response:
    """POST /llm/connect {provider, api_key, model} → range la clé dans le coffre."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident, err = await _require_approved(request)
    if err:
        return err
    if _vault is None:
        return web.json_response({"error": "coffre indisponible"}, status=503)
    code = (data.get("provider") or "").strip().lower()
    cle = (data.get("api_key") or "").strip()
    probleme = verifie_cle(code, cle)
    if probleme:
        return web.json_response({"error": probleme}, status=400)
    p = get_provider(code)
    modele = (data.get("model") or "").strip() or p.modele_defaut
    _vault.store(
        ident["member_id"], VAULT_SERVICE,
        {"provider": code, "api_key": cle, "model": modele},
        {"provider": code, "model": modele},          # méta sans secret
    )
    return web.json_response({"ok": True, "provider": p.nom, "model": modele})


async def llm_disconnect(request: web.Request) -> web.Response:
    """POST /llm/disconnect → retire sa clé (retour au fournisseur par défaut)."""
    ident, err = await _require_approved(request)
    if err:
        return err
    removed = _vault.delete(ident["member_id"], VAULT_SERVICE) if _vault else False
    return web.json_response({"ok": bool(removed)})


async def skills_list(request: web.Request) -> web.Response:
    """POST /skills/list → compétences visibles par ce membre (livrées + perso)."""
    ident, err = await _require_approved(request)
    if err:
        return err
    if _skills is None:
        return web.json_response({"skills": []})
    skills = _skills.list_skills(ident["member_id"])
    return web.json_response({"skills": [s.as_dict() for s in skills]})


async def skills_read(request: web.Request) -> web.Response:
    """POST /skills/read {name} → contenu d'une fiche."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident, err = await _require_approved(request)
    if err:
        return err
    content = _skills.read_skill(ident["member_id"], (data.get("name") or "")) if _skills else ""
    if not content:
        return web.json_response({"error": "compétence introuvable"}, status=404)
    return web.json_response({"content": content})


async def skills_delete(request: web.Request) -> web.Response:
    """POST /skills/delete {name} → supprime une compétence PERSONNELLE.

    Les fiches livrées ne sont jamais supprimables : si le membre en avait remplacé
    une, la suppression rétablit simplement la version d'origine.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident, err = await _require_approved(request)
    if err:
        return err
    ok = _skills.delete_skill(ident["member_id"], (data.get("name") or "")) if _skills else False
    return web.json_response({"ok": ok})


async def project_folders(request: web.Request) -> web.Response:
    """POST /projects/folders {project_id, workspaces:[…]} → rattache des dossiers au projet.

    Un projet n'est pas qu'un nom : il désigne un sujet ET les dossiers de l'ordinateur
    qui vont avec. Une fois rattachés, VindIA ne voit QUE ces dossiers quand le projet
    est actif — ce qui cadre son travail au lieu de tout lui exposer.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident, err = await _require_approved(request)
    if err:
        return err
    if _projects is None:
        return web.json_response({"error": "projets indisponibles"}, status=503)
    project_id = (data.get("project_id") or "").strip()
    workspaces = data.get("workspaces")
    if not isinstance(workspaces, list):
        return web.json_response({"error": "workspaces doit être une liste"}, status=400)
    # On n'accepte que des dossiers qui existent RÉELLEMENT chez ce membre : le client
    # ne peut donc pas rattacher l'espace d'un autre, même en forgeant la requête.
    member_id = ident["member_id"]
    known = {w["workspace"] for w in (_sync.list_workspaces(member_id) if _sync else [])}
    asked = [str(w) for w in workspaces][:20]
    valid = [w for w in asked if w in known]
    try:
        proj = _projects.set_workspaces(member_id, project_id, valid)
    except ValueError:
        return web.json_response({"error": "projet inconnu"}, status=404)
    # Le projet actif change de périmètre → l'index injecté au LLM doit suivre.
    if _active_project.get(member_id) == project_id and _llm is not None and hasattr(_llm, "load_project"):
        _llm.load_project(member_id, _projects.build_index(member_id, project_id))
    return web.json_response({"project": proj.as_dict(), "ignored": [w for w in asked if w not in known]})


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
    # On renvoie TOUS les comptes, pas seulement ceux en attente : n'afficher que
    # l'attente donnait un écran vide dès la dernière validation, sans qu'on sache
    # si la décision avait été prise ou si l'écran était cassé.
    if _approvals is None:
        return web.json_response({"pending": [], "comptes": []})
    attente = _approvals.list_by_status("pending")
    comptes = attente + _approvals.list_by_status("approved") + _approvals.list_by_status("refused")
    return web.json_response({"pending": attente, "comptes": comptes})



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
    avertissement = ""   # rempli si l'accès est ouvert sans avoir pu vérifier l'adresse
    # L'adresse est lue AVANT la décision : après, l'enregistrement peut avoir changé.
    dossier = _approvals.get(target) if _approvals else None
    email_cible = (dossier or {}).get("email") or ""
    # Ouvrir un accès à une adresse jamais confirmée revient à faire confiance à une
    # boîte que personne n'a prouvé posséder — elle peut même ne pas exister. Le
    # refus est posé ICI, côté serveur : un clic accidentel ne suffit pas à passer.
    if approve and dossier is not None and not dossier.get("adresse_confirmee"):
        # Le drapeau local ne se pose qu'au premier passage DANS l'application. Quelqu'un
        # qui a cliqué le lien reçu par e-mail sans revenir ensuite restait coincé ici :
        # adresse confirmée chez Supabase, mais impossible à valider. On redemande donc
        # à Supabase, seule source qui fasse foi, avant de refuser.
        confirme = await _auth.email_confirme(target) if _auth is not None else None
        if confirme:
            _approvals.marquer_adresse_confirmee(target)
        elif confirme is False:
            # Preuve NÉGATIVE : Supabase affirme que l'adresse n'est pas confirmée.
            return web.json_response({
                "error": "Cette adresse n'a pas encore été confirmée : Supabase indique "
                         "qu'elle n'a jamais été validée. Attends que la personne clique "
                         "le lien reçu par e-mail avant de lui ouvrir l'accès.",
                "adresse_non_confirmee": True,
            }, status=409)
        else:
            # On ne SAIT PAS (clé de service absente ou Supabase injoignable). Bloquer
            # ici reviendrait à condamner tout compte que le hasard n'a pas fait repasser
            # par l'application — c'est ce qui a coincé des inscriptions légitimes après
            # la mise en place du garde-fou. On laisse donc décider l'administrateur,
            # mais on le dit au lieu de le taire.
            avertissement = ("Adresse non vérifiée : la vérification automatique auprès "
                             "de Supabase est indisponible (clé de service absente). "
                             "L'accès a été ouvert sur ta seule décision.")
    ok = _approvals.decide(target, approve) if _approvals else False
    # Prévenir la personne : sans cela, quelqu'un dont le compte vient d'être validé
    # n'en sait rien et devrait revenir essayer au hasard.
    prevenu = False
    if ok and email_cible and _email is not None:
        sujet, corps = decision_message(approve, _PUBLIC_URL)
        prevenu = await _email.notify(sujet, corps, to=[email_cible])
    return web.json_response({"ok": ok, "decision": "approved" if approve else "refused",
                              "personne_prevenue": prevenu,
                              "avertissement": avertissement})



# ──────────────────────────────────────────────────────────────
# Synchronisation avec l'application de bureau
# L'app envoie les fichiers des dossiers choisis par l'utilisateur et récupère les
# créations de VindIA. Comparaison par empreinte : seul ce qui a changé transite.
# ──────────────────────────────────────────────────────────────

async def sync_workspaces(request: web.Request) -> web.Response:
    """POST /sync/workspaces → espaces de travail du membre connecté."""
    ident, err = await _require_approved(request)
    if err:
        return err
    return web.json_response({"workspaces": _sync.list_workspaces(ident["member_id"])})


async def sync_register(request: web.Request) -> web.Response:
    """POST /sync/register {workspace, label} → déclare un dossier de travail."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident, err = await _require_approved(request)
    if err:
        return err
    label = (data.get("label") or data.get("workspace") or "").strip()[:120]
    if not label:
        return web.json_response({"error": "nom de dossier manquant"}, status=400)
    ws = _sync.register_workspace(ident["member_id"], data.get("workspace") or label, label)
    return web.json_response({"ok": True, "workspace": ws, "label": label})


async def sync_index(request: web.Request) -> web.Response:
    """POST /sync/index {workspace} → empreinte de chaque fichier côté serveur.

    L'application compare avec son propre relevé pour n'envoyer que les différences.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident, err = await _require_approved(request)
    if err:
        return err
    ws = (data.get("workspace") or "").strip()
    if not ws:
        return web.json_response({"error": "workspace manquant"}, status=400)
    return web.json_response({"files": _sync.index(ident["member_id"], ws)})


async def sync_push(request: web.Request) -> web.Response:
    """POST /sync/push (multipart: workspace, path, file) → dépose un fichier."""
    ident, err = await _require_approved(request)
    if err:
        return err
    try:
        reader = await request.multipart()
    except Exception:
        return web.json_response({"error": "multipart attendu"}, status=400)
    workspace = rel = None
    payload = b""
    async for part in reader:
        if part.name == "workspace":
            workspace = (await part.text()).strip()
        elif part.name == "path":
            rel = (await part.text()).strip()
        elif part.name == "file":
            payload = await part.read(decode=False)
            if len(payload) > _MAX_UPLOAD:
                return web.json_response({"error": "fichier trop volumineux (max 10 Mo)"}, status=413)
    if not workspace or not rel:
        return web.json_response({"error": "workspace ou chemin manquant"}, status=400)
    if not _check_rate(ident["member_id"]):
        return web.json_response({"error": "trop de requêtes"}, status=429)
    if not _sync.put(ident["member_id"], workspace, rel, payload):
        return web.json_response({"error": "chemin refusé"}, status=400)
    return web.json_response({"ok": True, "path": rel, "size": len(payload)})


async def sync_pull(request: web.Request) -> web.Response:
    """POST /sync/pull {workspace, path} → renvoie un fichier (créations de VindIA)."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    ident, err = await _require_approved(request)
    if err:
        return err
    content = _sync.get(ident["member_id"], (data.get("workspace") or "").strip(),
                        (data.get("path") or "").strip())
    if content is None:
        return web.json_response({"error": "fichier introuvable"}, status=404)
    return web.Response(body=content, content_type="application/octet-stream")


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
    app.router.add_post("/projects/folders", project_folders)
    app.router.add_post("/signup/notify", signup_notify)
    app.router.add_post("/stt", stt)
    app.router.add_post("/connect/catalogue", connect_catalogue)
    app.router.add_post("/connect/save", connect_save)
    app.router.add_post("/connect/remove", connect_remove)
    app.router.add_post("/llm/catalogue", llm_catalogue)
    app.router.add_post("/llm/connect", llm_connect)
    app.router.add_post("/llm/disconnect", llm_disconnect)
    app.router.add_post("/skills/list", skills_list)
    app.router.add_post("/skills/read", skills_read)
    app.router.add_post("/skills/delete", skills_delete)
    app.router.add_post("/upload", upload)
    app.router.add_post("/sync/workspaces", sync_workspaces)
    app.router.add_post("/sync/register", sync_register)
    app.router.add_post("/sync/index", sync_index)
    app.router.add_post("/sync/push", sync_push)
    app.router.add_post("/sync/pull", sync_pull)
    app.router.add_post("/connections/list", connections_list)
    app.router.add_post("/connections/disconnect", connections_disconnect)
    app.router.add_post("/memory/list", memory_list)
    app.router.add_post("/memory/forget", memory_forget)
    app.router.add_post("/admin/pending", admin_pending)
    app.router.add_post("/admin/decide", admin_decide)
    app.router.add_post("/admin/relancer", admin_relancer)
    app.router.add_post("/admin/supprimer", admin_supprimer)
    app.router.add_post("/oauth/google/start", oauth_google_start)
    app.router.add_get("/oauth/google/callback", oauth_google_callback)
    app.router.add_get("/{name}", static_file)
    return app


if __name__ == "__main__":
    web.run_app(build_app(), host="127.0.0.1", port=PORT)
