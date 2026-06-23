"""Serveur web VindIA : sert la page + endpoint /token (mint LiveKit).

La clé et le secret LiveKit ne quittent JAMAIS le serveur : le navigateur appelle
/token et reçoit seulement un JWT court (1 h) pour rejoindre la room. Écoute sur
127.0.0.1 ; nginx fait le TLS devant (le micro du navigateur exige HTTPS).

    set -a; . server/.env; set +a
    .venv/bin/python web/server.py
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path

from aiohttp import web
from livekit import api
import edge_tts

ROOM = os.environ.get("VINDIA_ROOM", "vindia")
URL = os.environ["LIVEKIT_URL"]
KEY = os.environ["LIVEKIT_API_KEY"]
SECRET = os.environ["LIVEKIT_API_SECRET"]
PORT = int(os.environ.get("VINDIA_WEB_PORT", "8092"))
WEB_DIR = Path(__file__).resolve().parent
TTS_VOICE = os.environ.get("VINDIA_TTS_VOICE", "fr-FR-DeniseNeural")


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
    if not text:
        return web.Response(status=400)
    audio = bytearray()
    try:
        communicate = edge_tts.Communicate(text, voice)
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


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/token", token)
    app.router.add_post("/tts", tts)
    app.router.add_get("/{name}", static_file)
    return app


if __name__ == "__main__":
    web.run_app(build_app(), host="127.0.0.1", port=PORT)
