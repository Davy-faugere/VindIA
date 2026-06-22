#!/usr/bin/env python3
"""Runner VindIA — agent vocal connecté à une room LiveKit.

Assemble STT (Voxtral) + LLM (Mistral) + TTS (Piper FR souverain) dans le
`ConversationRuntime`, se connecte à une room, joue un accueil, puis écoute et
répond en français.

    set -a; . server/.env; set +a
    .venv/bin/python scripts/run_agent.py --room vindia

Prérequis : mistralai, livekit, livekit-api, piper-tts installés (venv), voix
Piper téléchargée, server/.env renseigné (MISTRAL_API_KEY + LIVEKIT_*).

NB 1er test : utiliser un CASQUE côté participant (le half-duplex protège la
sortie de l'agent, mais sans casque le micro du participant capte l'agent).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Rend le package `shared` importable quel que soit le cwd de lancement.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import livekit.api as api
import livekit.rtc as rtc

from shared.agent.adapters import CallableTTS, MistralLLM, VoxtralSTT
from shared.agent.audio.livekit_io import (
    LiveKitAudioBridge,
    LiveKitRoomOut,
    RoomSessionRegistry,
)
from shared.agent.piper_tts import load_piper, piper_tts_transport
from shared.agent.runtime import ConversationRuntime
from shared.agent.session import SessionDescriptor

DEFAULT_VOICE = "/root/vindia-work/.voices/fr_FR-siwis-medium.onnx"
SYSTEM_PROMPT = (
    "Tu es VindIA, un assistant vocal francophone. Réponds de façon brève, "
    "claire et naturelle, en une ou deux phrases maximum."
)
GREETING = "Bonjour, je suis VindIA, votre assistant vocal. Je vous écoute."


async def run(room_name: str, *, tenant_id: str = "t-demo", member_id: str = "davy") -> None:
    url = os.environ["LIVEKIT_URL"]
    key = os.environ["LIVEKIT_API_KEY"]
    secret = os.environ["LIVEKIT_API_SECRET"]
    voice_path = os.environ.get("VINDIA_VOICE", DEFAULT_VOICE)

    # Briques : TTS Piper FR (PCM @ son sample_rate), STT Voxtral, LLM Mistral.
    synth, tts_sr = load_piper(voice_path)
    tts = CallableTTS(piper_tts_transport(synth))
    runtime = ConversationRuntime(
        VoxtralSTT(), MistralLLM(system_prompt=SYSTEM_PROMPT), tts
    )
    registry = RoomSessionRegistry()

    token = (
        api.AccessToken(key, secret)
        .with_identity("vindia-agent")
        .with_name("VindIA")
        .with_grants(
            api.VideoGrants(
                room_join=True, room=room_name, can_publish=True, can_subscribe=True
            )
        )
        .to_jwt()
    )
    room = rtc.Room()
    await room.connect(url, token)
    print(f"[VindIA] connecté à la room '{room_name}' (TTS {tts_sr} Hz)", flush=True)

    session_id = f"sess-{room_name}"
    desc = SessionDescriptor(
        session_id=session_id,
        tenant_id=tenant_id,
        room=room_name,
        member_id=member_id,      # identité résolue (démo) ...
        locale="fr-FR",
        consent_granted=True,     # ... + consentement accordé -> can_process() OK
    )
    registry.bind(room_name, session_id)
    room_out = LiveKitRoomOut(room, sample_rate=tts_sr)  # PCM Piper, pas de resampling
    await runtime.open(desc, room_out)

    bridge = LiveKitAudioBridge(registry, sample_rate=48000)  # entrée LiveKit @ 48 kHz

    async def on_utterance(sid: str, audio: object) -> None:
        try:
            await runtime.handle(sid, audio)
        except Exception as exc:  # noqa: BLE001 - on logge et on continue
            print(f"[VindIA] erreur handle: {exc!r}", flush=True)

    bridge.on_utterance = on_utterance
    await bridge.start(room)

    # Accueil audible (confirme la sortie même avant que le participant parle).
    await asyncio.sleep(1.0)
    await room_out.play(await tts.synthesize(GREETING, "fr-FR"))
    print("[VindIA] accueil joué — en écoute. Ctrl-C pour arrêter.", flush=True)

    await asyncio.Future()  # tourne jusqu'à interruption


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Runner agent vocal VindIA")
    ap.add_argument("--room", default="vindia", help="nom de la room LiveKit")
    args = ap.parse_args()
    try:
        asyncio.run(run(args.room))
    except KeyboardInterrupt:
        print("\n[VindIA] arrêt.")
