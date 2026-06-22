"""TTS souverain FR self-host via Piper (voix française native, local, MIT).

Choix retenu pour VindIA : souveraineté + français. Piper tourne en local (CPU),
sans cloud, et produit du PCM int16 mono (pas de MP3 → pas de transcodage pour
`LiveKitRoomOut.play`, qu'on configure au `sample_rate` de la voix).

Le SDK `piper` est lazy-importé → ce module reste importable en CI (0 dépendance).
`synth` (texte -> PCM int16 bytes, bloquant) est injectable → testable offline ;
en live, `load_piper(model_path)` le construit et expose le sample_rate de la voix.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Tuple

TtsTransport = Callable[[str, str], Awaitable[bytes]]
# Synthèse bloquante : texte -> PCM int16 mono (bytes).
Synth = Callable[[str], bytes]


def piper_tts_transport(synth: Synth) -> TtsTransport:
    """Construit un transport TTS (texte, locale) -> PCM int16 bytes.

    La synthèse Piper est bloquante (CPU) → déportée hors de la boucle async
    via `asyncio.to_thread`. La locale est ignorée : la voix porte déjà la langue.
    """

    async def _transport(text: str, locale: str) -> bytes:
        return await asyncio.to_thread(synth, text)

    return _transport


def load_piper(model_path: str) -> Tuple[Synth, int]:  # pragma: no cover - piper + modèle
    """Charge une voix Piper. Retourne (synth, sample_rate).

    `model_path` : chemin du `.onnx` (le `.onnx.json` doit être à côté).
    """
    from piper import PiperVoice

    voice = PiperVoice.load(model_path)

    def _synth(text: str) -> bytes:
        return b"".join(chunk.audio_int16_bytes for chunk in voice.synthesize(text))

    return _synth, voice.config.sample_rate
