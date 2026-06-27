"""Mémoire persistante par membre : extraction LLM → MariaDB → injection prompt.

Flow session par session :
  open()   → load_context(member_id)  → bloc texte → injecté dans system prompt
  close()  → extract_and_save(history) → appel Mistral → JSON de faits → DB
  open() suivant → les faits sont rechargés → le LLM "se souvient"

Le `transport` est le même callable que dans MistralLLM (LlmTransport), injecté
pour rester testable offline sans lib ni réseau.
"""
from __future__ import annotations

import json
from typing import Awaitable, Callable, List, Optional, Sequence

from .store import Store

LlmTransport = Callable[[Sequence[dict]], Awaitable[str]]

_EXTRACT_SYSTEM = (
    "Tu es un extracteur de mémoire pour un agent vocal français. "
    "Analyse la transcription ci-dessous et extrait UNIQUEMENT les faits "
    "durables sur l'utilisateur : profil, objectifs, blocages récurrents, "
    "contexte business, décisions importantes, préférences clairement exprimées. "
    "N'extrait PAS les détails éphémères, les formules de politesse ou les sujets "
    "hors-sujet. Réponds UNIQUEMENT en JSON strict : "
    '{\"facts\": [\"fait 1\", \"fait 2\"]}. '
    "Maximum 10 faits, en français concis. Si rien de durable : "
    '{\"facts\": []}.'
)


class MemoryStore:
    """Gestion de la mémoire long-terme par membre.

    - load_context  : sync, appelé à l'ouverture de session.
    - extract_and_save : async, appelé (fire-and-forget) à la fermeture.
    """

    def __init__(self, db: Store, transport: LlmTransport, *, max_memories: int = 100) -> None:
        self._db = db
        self._transport = transport
        # Volume long-terme conservé par membre (au-delà, on élague les plus anciens).
        self._max_memories = max_memories

    def load_context(self, member_id: str) -> str:
        """Retourne un bloc texte à injecter dans le system prompt, ou '' si vide."""
        rows = self._db.get_memories(member_id)
        if not rows:
            return ""
        lines = "\n".join(f"- {r}" for r in rows)
        return f"[Mémoire long-terme de ce membre]\n{lines}"

    async def extract_and_save(
        self,
        member_id: str,
        tenant_id: str,
        session_id: str,
        history: List[dict],
    ) -> int:
        """Extrait les faits saillants d'un historique et les persiste en DB.

        Retourne le nombre de faits sauvegardés (0 si rien d'utile ou erreur LLM).
        """
        if not history:
            return 0
        transcript = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in history
        )
        try:
            raw = await self._transport([
                {"role": "system", "content": _EXTRACT_SYSTEM},
                {"role": "user", "content": transcript},
            ])
            data = json.loads(raw)
            facts: List[str] = data.get("facts", []) if isinstance(data, dict) else []
        except Exception:
            return 0
        saved = 0
        for fact in facts[:10]:
            if isinstance(fact, str) and fact.strip():
                self._db.save_memory(member_id, tenant_id, session_id, fact.strip())
                saved += 1
        if saved:
            self._db.trim_memories(member_id, self._max_memories)
        return saved
