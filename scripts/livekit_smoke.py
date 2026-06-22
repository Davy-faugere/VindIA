#!/usr/bin/env python3
"""Smoke LiveKit : prouve qu'on peut se connecter à la room et publier de l'audio.

OUTIL DE DIAGNOSTIC, hors CI. Nécessite `livekit` + `livekit-api` (cf.
requirements.txt) et les creds dans l'environnement (server/.env) :
LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET.

    set -a; . server/.env; set +a
    .venv/bin/python scripts/livekit_smoke.py

Se connecte à une room jetable, publie une piste audio, pousse quelques frames
de silence, puis se déconnecte. Sortie « OK » = la connexion WebRTC du VPS vers
LiveKit Cloud fonctionne (risque réseau n°1 de J4 levé).
"""

from __future__ import annotations

import asyncio
import os

ROOM = "vindia-smoke"
SAMPLE_RATE = 48000
NUM_CHANNELS = 1


async def _smoke() -> None:
    import livekit.api as api
    import livekit.rtc as rtc

    url = os.environ["LIVEKIT_URL"]
    key = os.environ["LIVEKIT_API_KEY"]
    secret = os.environ["LIVEKIT_API_SECRET"]

    token = (
        api.AccessToken(key, secret)
        .with_identity("vindia-agent-smoke")
        .with_name("VindIA smoke")
        .with_grants(
            api.VideoGrants(
                room_join=True, room=ROOM, can_publish=True, can_subscribe=True
            )
        )
        .to_jwt()
    )

    room = rtc.Room()
    await asyncio.wait_for(room.connect(url, token), timeout=15)
    print(f"CONNECTÉ à la room: {room.name}")

    source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
    track = rtc.LocalAudioTrack.create_audio_track("vindia-tts", source)
    await room.local_participant.publish_track(track, rtc.TrackPublishOptions())
    print("PISTE audio publiée OK")

    frame = rtc.AudioFrame(bytes(480 * 2), SAMPLE_RATE, NUM_CHANNELS, 480)  # 10 ms
    for _ in range(5):
        await source.capture_frame(frame)
    print("FRAMES capturées OK")

    await room.disconnect()
    print("DÉCONNEXION OK — connexion WebRTC VPS -> LiveKit Cloud fonctionnelle")


def main() -> None:
    required = ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"Variables manquantes : {', '.join(missing)} (cf. server/.env)")
    asyncio.run(asyncio.wait_for(_smoke(), timeout=25))


if __name__ == "__main__":
    main()
