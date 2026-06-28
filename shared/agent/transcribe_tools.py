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

# Extraction audio découpée : chemin média -> liste de segments audio (mp3 mono 16 kHz).
# Le découpage en tranches lève la limite de taille de l'API et permet les longues vidéos.
ExtractSegments = Callable[[str], list]
# Transcription : (octets audio, locale) -> texte.
TranscribeFn = Callable[[bytes, str], Awaitable[str]]

# Durée d'une tranche (secondes). 10 min → chaque segment reste petit pour l'API.
SEGMENT_SEC = 600


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
        extract_segments: Optional[ExtractSegments] = None,
        max_chars: int = 20000,
    ) -> None:
        self._base = Path(base_dir)
        self._transcribe = transcribe
        self._extract = extract_segments
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
        extract = self._extract or _ffmpeg_segments
        try:
            segments = extract(str(path))
        except Exception as exc:  # noqa: BLE001
            return f"Extraction audio impossible : {str(exc)[:160]}"
        if not segments:
            return "Aucune piste audio exploitable dans ce fichier."
        # Découpage : on transcrit chaque tranche puis on recolle (longues vidéos OK).
        parts = []
        for seg in segments:
            if not seg:
                continue
            try:
                txt = (await self._transcribe(seg, "fr-FR") or "").strip()
            except Exception as exc:  # noqa: BLE001
                return f"Transcription impossible : {str(exc)[:160]}"
            if txt:
                parts.append(txt)
        text = " ".join(parts).strip()
        if not text:
            return "La transcription est vide (pas de parole détectée ?)."
        if len(text) > self._max_chars:
            text = text[: self._max_chars].rstrip() + " […]"
        return text


def _ffmpeg_segments(path: str) -> list:  # pragma: no cover - dépend de ffmpeg
    """Extrait l'audio en MP3 mono 16 kHz, DÉCOUPÉ en tranches de SEGMENT_SEC.

    Le découpage permet de transcrire des vidéos de n'importe quelle durée sans buter
    sur la limite de taille de l'API (chaque tranche reste petite).
    """
    import glob
    import os
    import shutil
    import subprocess
    import tempfile

    d = tempfile.mkdtemp(prefix="vindia-tr-")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k",
             "-f", "segment", "-segment_time", str(SEGMENT_SEC), os.path.join(d, "seg%04d.mp3")],
            capture_output=True, timeout=1800, check=True,
        )
        segs = sorted(glob.glob(os.path.join(d, "seg*.mp3")))
        return [open(s, "rb").read() for s in segs]
    finally:
        shutil.rmtree(d, ignore_errors=True)


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
