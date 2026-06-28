"""Transcription audio/vidéo → texte pour VindIA (Voxtral, souverain).

VindIA peut transcrire un fichier audio ou vidéo du dossier synchronisé : ffmpeg
extrait la piste audio (mono 16 kHz, léger), puis Mistral Voxtral la transcrit.

Style maison : ffmpeg et la transcription sont des frontières INJECTABLES (sous-
processus / réseau en prod, fakes en test) → la logique est testable 100 % offline.
Garde-fou : le fichier visé est résolu sous le dossier racine (anti path-traversal).
"""

from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable, Optional

from .tools import Tool, ToolSpec

# Extensions reconnues (audio + vidéo) — ffmpeg gère le reste.
_MEDIA_EXT = {
    ".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac", ".opus", ".wma",
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mpeg", ".mpg",
}

# Extraction audio : chemin média -> octets audio (mp3 mono 16 kHz).
ExtractAudio = Callable[[str], bytes]
# Transcription : (octets audio, locale) -> texte.
TranscribeFn = Callable[[bytes, str], Awaitable[str]]


def _safe_under(base: Path, rel: str) -> Path:
    base = base.resolve()
    target = (base / rel.lstrip("/")).resolve()
    if target != base and base not in target.parents:
        raise ValueError("chemin hors du dossier synchronisé")
    return target


class TranscribeTool(Tool):
    """Transcrit un fichier audio/vidéo du dossier synchronisé en texte."""

    def __init__(
        self,
        base_dir: str,
        transcribe: TranscribeFn,
        *,
        extract_audio: Optional[ExtractAudio] = None,
        max_chars: int = 12000,
    ) -> None:
        self._base = Path(base_dir)
        self._transcribe = transcribe
        self._extract = extract_audio
        self._max_chars = max_chars
        self.spec = ToolSpec(
            name="transcribe_media",
            description=(
                "Transcrit en texte un fichier audio ou vidéo du dossier synchronisé "
                "(mp4, mov, mp3, wav, m4a…). Donne le nom du fichier ; renvoie la "
                "transcription, que tu peux ensuite résumer ou enregistrer."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Nom/chemin du fichier média à transcrire."},
                },
                "required": ["filename"],
            },
        )

    async def run(self, args: dict) -> str:
        filename = (args.get("filename") or "").strip()
        if not filename:
            return "Erreur : nom de fichier manquant."
        if Path(filename).suffix.lower() not in _MEDIA_EXT:
            return "Ce fichier n'est pas un média audio/vidéo reconnu."
        try:
            path = _safe_under(self._base, filename)
        except ValueError:
            return "Erreur : chemin refusé."
        if not path.is_file():
            return f"Fichier introuvable : « {filename} »."
        extract = self._extract or _ffmpeg_extract
        try:
            audio = extract(str(path))
        except Exception as exc:  # noqa: BLE001
            return f"Extraction audio impossible : {str(exc)[:160]}"
        if not audio:
            return "Aucune piste audio exploitable dans ce fichier."
        try:
            text = (await self._transcribe(audio, "fr-FR") or "").strip()
        except Exception as exc:  # noqa: BLE001
            return f"Transcription impossible : {str(exc)[:160]}"
        if not text:
            return "La transcription est vide (pas de parole détectée ?)."
        if len(text) > self._max_chars:
            text = text[: self._max_chars].rstrip() + " […]"
        return text


def _ffmpeg_extract(path: str) -> bytes:  # pragma: no cover - dépend de ffmpeg
    """Extrait la piste audio en MP3 mono 16 kHz (léger, adapté à la transcription)."""
    import os
    import subprocess
    import tempfile

    out = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", "-f", "mp3", out],
            capture_output=True, timeout=600, check=True,
        )
        with open(out, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(out):
            os.unlink(out)


def voxtral_transcribe() -> TranscribeFn:  # pragma: no cover - live
    """Transport de transcription via Mistral Voxtral (réutilise VoxtralSTT)."""
    from .adapters import VoxtralSTT

    stt = VoxtralSTT()

    async def _call(audio: bytes, locale: str) -> str:
        return await stt.transcribe(audio, locale)

    return _call


def build_transcribe_tool(base_dir: str) -> TranscribeTool:
    """Outil de transcription prêt pour la prod (ffmpeg + Voxtral)."""
    return TranscribeTool(base_dir, voxtral_transcribe())
