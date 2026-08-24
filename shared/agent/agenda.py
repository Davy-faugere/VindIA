"""Agenda de VindIA : le fil des événements d'une personne.

Pensé pour quelqu'un dont la mémoire flanche — après un accident vasculaire, avec
l'âge — et qui a besoin d'un fil conducteur fiable : ce qu'il y a aujourd'hui, ce qui
a été fait hier, ce qui arrive demain.

RÈGLE FONDATRICE : ici, rien ne passe par le modèle de langage. Un rendez-vous, une
prise de traitement, une date vivent dans cette table, avec une horloge. Le modèle
comprend ce que la personne dit et formule ce qu'elle entend — il ne décide jamais de
ce qui est vrai ni de l'heure qu'il est. C'est la même règle que le garde-fou
anti-mensonge, appliquée là où l'erreur coûte le plus cher.

La mémoire conversationnelle existante (`member_memories`) reste ce qu'elle est : des
faits reformulés par le modèle, parfaits pour « il aime le café serré », inutilisables
pour un traitement. Les deux mémoires sont séparées, volontairement.

Rien n'est connecté à l'extérieur : pas d'agenda tiers, pas de service de calendrier.
Tout appartient à VindIA.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from .ids import new_id

# Catégories. « traitement » est distinguée : c'est une donnée de santé au sens de
# l'article 9 du RGPD, elle exige un consentement explicite et une trace.
CATEGORIES = ("rendez-vous", "traitement", "activite", "tache", "repas", "autre")

# Récurrences volontairement simples : ce qu'une personne dit à voix haute.
RECURRENCES = ("aucune", "quotidien", "hebdomadaire", "mensuel")

_FMT = "%Y-%m-%d %H:%M:%S"


def _txt(valeur, longueur: int) -> str:
    return (str(valeur or "").strip())[:longueur]


class Agenda:
    """Événements d'une personne. Isolation par member_id à CHAQUE requête.

    Reçoit une connexion DB-API, comme `Store` : MariaDB en production, SQLite dans
    les tests. Aucune dépendance externe.
    """

    def __init__(self, conn: object, paramstyle: str = "qmark") -> None:
        self._conn = conn
        self._ph = "?" if paramstyle == "qmark" else "%s"

    def _q(self, sql: str) -> str:
        return sql.replace("?", self._ph)

    def _exec(self, sql: str, params: tuple = ()):
        # Même garde-fou que Store : MariaDB ferme les connexions inactives, et
        # l'agenda est justement consulté après de longues heures de silence.
        try:
            cur = self._conn.cursor()
            cur.execute(self._q(sql), params)
            return cur
        except Exception:
            ping = getattr(self._conn, "ping", None)
            if ping is None:
                raise
            ping(reconnect=True)
            cur = self._conn.cursor()
            cur.execute(self._q(sql), params)
            return cur

    def creer_tables(self) -> None:
        """Crée les tables si besoin. Idempotent."""
        self._exec(
            """CREATE TABLE IF NOT EXISTS agenda_events (
                 id          CHAR(36)     NOT NULL PRIMARY KEY,
                 member_id   CHAR(36)     NOT NULL,
                 titre       VARCHAR(200) NOT NULL,
                 detail      TEXT,
                 debut       VARCHAR(19)  NOT NULL,
                 categorie   VARCHAR(20)  NOT NULL,
                 recurrence  VARCHAR(20)  NOT NULL,
                 fait_le     VARCHAR(19),
                 annule      INTEGER      NOT NULL DEFAULT 0,
                 cree_le     VARCHAR(19)  NOT NULL
               )"""
        )
        # Deux lectures dominent : « ce que j'ai aujourd'hui » et « ce qui vient ».
        # Sans cet index elles balaient toute la table dès quelques mois d'usage.
        try:
            self._exec(
                "CREATE INDEX idx_agenda_membre_debut ON agenda_events (member_id, debut)"
            )
        except Exception:
            pass                       # index déjà présent
        self._commit()

    def _commit(self) -> None:
        commit = getattr(self._conn, "commit", None)
        if commit:
            commit()

    # ------------------------------------------------------------------ écriture

    def ajouter(
        self,
        member_id: str,
        titre: str,
        debut: datetime,
        *,
        categorie: str = "rendez-vous",
        detail: str = "",
        recurrence: str = "aucune",
        maintenant: Optional[datetime] = None,
    ) -> str:
        """Enregistre un événement et retourne son identifiant."""
        if not member_id or not titre.strip():
            raise ValueError("member_id et titre sont obligatoires")
        if categorie not in CATEGORIES:
            categorie = "autre"
        if recurrence not in RECURRENCES:
            recurrence = "aucune"
        eid = new_id()
        self._exec(
            """INSERT INTO agenda_events
               (id, member_id, titre, detail, debut, categorie, recurrence, fait_le,
                annule, cree_le)
               VALUES (?,?,?,?,?,?,?,NULL,0,?)""",
            (eid, member_id, _txt(titre, 200), _txt(detail, 2000),
             debut.strftime(_FMT), categorie, recurrence,
             (maintenant or datetime.now()).strftime(_FMT)),
        )
        self._commit()
        return eid

    def marquer_fait(self, member_id: str, event_id: str,
                     maintenant: Optional[datetime] = None) -> bool:
        """Note qu'un événement a été accompli. C'est ce qui fait le fil d'Ariane :
        sans trace de ce qui est FAIT, impossible de répondre à « je l'ai pris ? »."""
        cur = self._exec(
            "UPDATE agenda_events SET fait_le=? WHERE id=? AND member_id=? AND annule=0",
            ((maintenant or datetime.now()).strftime(_FMT), event_id, member_id),
        )
        self._commit()
        return bool(getattr(cur, "rowcount", 0))

    def annuler(self, member_id: str, event_id: str) -> bool:
        """Annule sans effacer : l'historique d'une personne ne se réécrit pas."""
        cur = self._exec(
            "UPDATE agenda_events SET annule=1 WHERE id=? AND member_id=?",
            (event_id, member_id),
        )
        self._commit()
        return bool(getattr(cur, "rowcount", 0))

    # ------------------------------------------------------------------ lecture

    def _lire(self, sql: str, params: tuple) -> List[dict]:
        cur = self._exec(sql, params)
        colonnes = ("id", "titre", "detail", "debut", "categorie", "recurrence",
                    "fait_le", "annule")
        return [dict(zip(colonnes, ligne)) for ligne in cur.fetchall()]

    _CHAMPS = "id, titre, detail, debut, categorie, recurrence, fait_le, annule"

    def du_jour(self, member_id: str, jour: Optional[datetime] = None) -> List[dict]:
        """Tout ce qui est prévu ce jour-là, dans l'ordre des heures."""
        j = (jour or datetime.now()).strftime("%Y-%m-%d")
        return self._lire(
            f"""SELECT {self._CHAMPS} FROM agenda_events
                WHERE member_id=? AND annule=0 AND debut LIKE ?
                ORDER BY debut""",
            (member_id, j + "%"),
        )

    def a_venir(self, member_id: str, jours: int = 7,
                maintenant: Optional[datetime] = None) -> List[dict]:
        """Ce qui arrive dans les prochains jours."""
        m = maintenant or datetime.now()
        return self._lire(
            f"""SELECT {self._CHAMPS} FROM agenda_events
                WHERE member_id=? AND annule=0 AND debut >= ? AND debut <= ?
                ORDER BY debut""",
            (member_id, m.strftime(_FMT), (m + timedelta(days=jours)).strftime(_FMT)),
        )

    def passe(self, member_id: str, jours: int = 2,
              maintenant: Optional[datetime] = None) -> List[dict]:
        """Ce qui s'est passé récemment — le fil d'Ariane : « qu'est-ce que j'ai fait
        hier ? », « est-ce que je l'ai pris ce matin ? »."""
        m = maintenant or datetime.now()
        return self._lire(
            f"""SELECT {self._CHAMPS} FROM agenda_events
                WHERE member_id=? AND annule=0 AND debut < ? AND debut >= ?
                ORDER BY debut DESC""",
            (member_id, m.strftime(_FMT), (m - timedelta(days=jours)).strftime(_FMT)),
        )

    def en_retard(self, member_id: str, minutes: int = 30,
                  maintenant: Optional[datetime] = None) -> List[dict]:
        """Ce qui était prévu, n'a pas été marqué fait, et dont l'heure est passée.

        C'est la question qui compte vraiment pour un traitement : non pas « qu'y
        avait-il ? » mais « qu'est-ce qui a été oublié ? ».
        """
        m = maintenant or datetime.now()
        limite = (m - timedelta(minutes=minutes)).strftime(_FMT)
        return self._lire(
            f"""SELECT {self._CHAMPS} FROM agenda_events
                WHERE member_id=? AND annule=0 AND fait_le IS NULL
                  AND debut <= ? AND debut >= ?
                ORDER BY debut""",
            (member_id, limite, (m - timedelta(days=1)).strftime(_FMT)),
        )

    def chercher(self, member_id: str, mot: str, limite: int = 20) -> List[dict]:
        """Recherche par mot dans le titre — « quand est mon rendez-vous chez le
        cardiologue ? »."""
        return self._lire(
            f"""SELECT {self._CHAMPS} FROM agenda_events
                WHERE member_id=? AND annule=0 AND titre LIKE ?
                ORDER BY debut DESC LIMIT {int(limite)}""",
            (member_id, f"%{_txt(mot, 80)}%"),
        )
