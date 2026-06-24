"""Serveur web VindIA : page + /token (LiveKit) + /auth + /ask + /session/end + /tts + /build.

/auth  : identifie l'utilisateur par code → renvoie display_name + charge la mémoire
/ask   : appel Mistral direct avec mémoire long-terme injectée (remplace le webhook n8n)
/session/end : extrait les faits de la session et les persiste en MariaDB

    set -a; . server/.env; set +a
    .venv/bin/python web/server.py
"""

from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path

# shared.agent est au niveau parent (vindia-work/) ; on s'assure qu'il est importable.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from aiohttp import web
from livekit import api
import edge_tts

from filegen import build_file, OFFICE_TYPES

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


def _init_services() -> None:
    global _store, _memory, _llm
    if _llm is not None:
        return
    from shared.agent.adapters import MistralLLM
    _llm = MistralLLM()
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

    GET /auth?code=CODE → {ok, display_name, has_memory}
    """
    code = (request.query.get("code") or "").strip()
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
    _init_services()
    if _llm is None:
        return web.json_response({"error": "LLM non initialisé"}, status=503)
    try:
        reply = await _llm.reply(message, session_id=code)
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


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/token", token)
    app.router.add_get("/auth", auth)
    app.router.add_post("/ask", ask)
    app.router.add_post("/session/end", session_end)
    app.router.add_post("/tts", tts)
    app.router.add_post("/build", build)
    app.router.add_get("/{name}", static_file)
    return app


if __name__ == "__main__":
    web.run_app(build_app(), host="127.0.0.1", port=PORT)
