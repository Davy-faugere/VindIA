"""Segmentation de la voix par énergie (stdlib pure, 0 dépendance).

Découpe un flux de frames PCM 16 bits mono en énoncés : une suite de frames
« voix » terminée par un silence suffisant produit un énoncé finalisé. Conçu
pour être déterministe et testable sans audio réel ni numpy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence


def frame_rms(frame: Sequence[int]) -> float:
    """RMS d'une frame d'échantillons int16. 0.0 pour une frame vide."""
    if not frame:
        return 0.0
    acc = 0
    for s in frame:
        acc += s * s
    return math.sqrt(acc / len(frame))


@dataclass
class VoiceSegmenter:
    """Machine à états voix/silence avec hangover.

    - `threshold` : RMS minimal pour considérer une frame comme « voix ».
    - `start_frames` : nb de frames voix consécutives pour ouvrir un énoncé.
    - `hangover_frames` : nb de frames silence pour clôturer un énoncé.

    `push(frame)` renvoie l'énoncé finalisé (liste de frames) au moment où il se
    clôture, sinon None. `flush()` clôture un énoncé en cours (fin de room).
    """

    threshold: float = 500.0
    start_frames: int = 3
    hangover_frames: int = 10

    _in_speech: bool = field(default=False, init=False)
    _speech_run: int = field(default=0, init=False)
    _silence_run: int = field(default=0, init=False)
    _buffer: List[Sequence[int]] = field(default_factory=list, init=False)

    def push(self, frame: Sequence[int]) -> Optional[List[Sequence[int]]]:
        is_voice = frame_rms(frame) >= self.threshold

        if not self._in_speech:
            if is_voice:
                self._speech_run += 1
                self._buffer.append(frame)
                if self._speech_run >= self.start_frames:
                    self._in_speech = True
                    self._silence_run = 0
            else:
                self._speech_run = 0
                self._buffer.clear()
            return None

        # En cours d'énoncé.
        self._buffer.append(frame)
        if is_voice:
            self._silence_run = 0
        else:
            self._silence_run += 1
            if self._silence_run >= self.hangover_frames:
                return self._finalize()
        return None

    def flush(self) -> Optional[List[Sequence[int]]]:
        if self._in_speech and self._buffer:
            return self._finalize()
        self._reset()
        return None

    def _finalize(self) -> List[Sequence[int]]:
        utterance = list(self._buffer)
        self._reset()
        return utterance

    def _reset(self) -> None:
        self._in_speech = False
        self._speech_run = 0
        self._silence_run = 0
        self._buffer = []


def segment_stream(
    frames: Iterable[Sequence[int]], **kwargs
) -> List[List[Sequence[int]]]:
    """Helper hors-ligne : segmente un flux complet en liste d'énoncés."""
    seg = VoiceSegmenter(**kwargs)
    out: List[List[Sequence[int]]] = []
    for f in frames:
        u = seg.push(f)
        if u is not None:
            out.append(u)
    tail = seg.flush()
    if tail is not None:
        out.append(tail)
    return out
