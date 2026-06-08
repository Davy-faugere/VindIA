"""Point d'entrée : câblage room → session → I/O audio.

`run()` est le squelette d'orchestration décrit dans le brief : à l'ouverture d'une
room, on crée un SessionDescriptor + LiveKitRoomOut, on ouvre le runtime, et on
branche le bridge entrant sur le dispatch du router.

Les appels au runtime/SDK sont des TODO tant que ces dépendances ne sont pas ajoutées.
"""

from __future__ import annotations

from typing import Optional

from .audio.livekit_io import LiveKitAudioBridge, LiveKitRoomOut, RoomSessionRegistry
from .router import Router
from .session import SessionDescriptor


async def on_room_opened(
    room: object,
    room_name: str,
    tenant_id: str,
    registry: RoomSessionRegistry,
    router: Router,
    runtime: Optional[object] = None,
) -> LiveKitAudioBridge:
    """Câble une room nouvellement ouverte.

    1) crée la session + la lie au registry,
    2) crée la sortie audio (RoomOut),
    3) ouvre le runtime sur la session avec room_out,
    4) branche le bridge entrant → router.dispatch.
    """
    session_id = f"sess-{room_name}"
    desc = SessionDescriptor(session_id=session_id, tenant_id=tenant_id, room=room_name)
    registry.bind(room_name, session_id)

    room_out = LiveKitRoomOut(room)
    if runtime is not None:
        # TODO(runtime): await runtime.open(desc, room_out=room_out)
        pass

    bridge = LiveKitAudioBridge(registry)
    bridge.on_utterance = router.dispatch
    return bridge


async def run() -> None:  # pragma: no cover - orchestration réseau
    """Boucle principale. TODO(livekit): se connecter, écouter les ouvertures de room."""
    raise NotImplementedError("run() — boucle de connexion LiveKit à câbler")
