"""Descripteur de session conversationnelle.

Une session lie une room LiveKit à un membre identifié d'un tenant, en portant
l'état de consentement. Compliant by design : pas de traitement sans consentement,
isolation tenant explicite, identité non dérivée de la diarisation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class SessionDescriptor:
    """Identifie de façon non ambiguë une session active.

    1 personne = 1 device = 1 identité : `member_id` est l'identité résolue,
    distincte du `speaker_id` de diarisation (label transitoire).
    """

    session_id: str
    tenant_id: str
    room: str
    member_id: Optional[str] = None
    locale: str = "fr-FR"
    consent_granted: bool = False
    metadata: dict = field(default_factory=dict)

    def can_process(self) -> bool:
        """Garde-fou : on ne traite l'audio que si le consentement est accordé."""
        return self.consent_granted and self.member_id is not None

    def with_member(self, member_id: str) -> "SessionDescriptor":
        """Retourne une copie liée à une identité résolue (immutabilité préservée)."""
        return SessionDescriptor(
            session_id=self.session_id,
            tenant_id=self.tenant_id,
            room=self.room,
            member_id=member_id,
            locale=self.locale,
            consent_granted=self.consent_granted,
            metadata=dict(self.metadata),
        )
