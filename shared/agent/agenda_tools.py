"""Outils d'agenda — ce qui rend le fil d'Ariane utilisable À LA VOIX.

La personne dit « rappelle-moi mon comprimé tous les matins à 8 h » ou « qu'est-ce que
j'ai aujourd'hui ? » ; VindIA appelle ces outils. Elle n'écrit rien elle-même dans
l'agenda et n'en invente rien : elle transmet, et rend compte de ce qui est revenu.

ISOLATION : chaque outil est construit pour UN member_id, figé à la construction. Le
modèle ne fournit jamais d'identifiant de personne — il ne peut donc pas désigner
l'agenda de quelqu'un d'autre.

DEUX GARDE-FOUS, parce qu'ici l'erreur ne se rattrape pas :

1. La date est calculée par `dates_fr`, à partir d'une horloge réelle. Le modèle ne
   fournit qu'une expression française telle qu'elle a été dite.
2. Une expression non comprise ne devient JAMAIS une date par défaut : l'outil répond
   qu'il n'a pas compris, ce qui conduit à redemander. Un rendez-vous placé au hasard
   est pire que pas de rendez-vous.

À l'oral, personne ne dit d'identifiant : marquer fait, annuler et chercher se font
donc par le TITRE, sur l'événement le plus proche dans le temps.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Callable, List, Optional

from .agenda import CATEGORIES, Agenda
from .dates_fr import analyse, detecte_recurrence
from .tools import Tool, ToolSpec

_JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
         "septembre", "octobre", "novembre", "décembre")


def dit_la_date(quand: datetime) -> str:
    """« lundi 24 août à 14 h 30 » — une date à dire, pas à lire."""
    heure = (f"{quand.hour} h {quand.minute:02d}" if quand.minute
             else f"{quand.hour} h")
    return (f"{_JOURS[quand.weekday()]} {quand.day} {_MOIS[quand.month - 1]} "
            f"à {heure}")


# Mots trop courants pour identifier quoi que ce soit.
_VIDES = {"mon", "ma", "mes", "le", "la", "les", "de", "du", "des", "un", "une",
          "ce", "cet", "cette", "au", "aux", "pour", "avec", "chez"}


def _mots(texte: str) -> set:
    import unicodedata
    n = unicodedata.normalize("NFD", (texte or "").lower())
    plat = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return {m for m in re.split(r"[^a-z0-9]+", plat) if len(m) > 2 and m not in _VIDES}


def _correspond(dit: str, titre: str) -> bool:
    """« mon comprimé » désigne-t-il « Comprimé du matin » ?

    À l'oral, personne ne répète le titre exact : la comparaison se fait sur les mots
    significatifs, pas sur la chaîne entière. Sans ça, « je l'ai pris » suivi de
    « mon comprimé » ne retrouvait rien et la personne s'entendait répondre qu'elle
    n'avait rien à faire.
    """
    a, b = _mots(dit), _mots(titre)
    return bool(a and b and a & b)


def _chercher_par_mots(agenda: Agenda, member_id: str, phrase: str) -> List[dict]:
    """Cherche sur chaque mot significatif, pas sur la phrase entière.

    À l'oral la personne dit « mon rendez-vous chez le cardiologue » ; une recherche
    SQL sur cette chaîne complète ne trouve rien, alors que le mot « cardiologue »
    suffisait. Sans ça, VindIA répondait qu'elle ne trouvait rien — sur un agenda
    d'aide à la mémoire, c'est exactement la réponse qu'il ne faut pas donner.
    """
    vus, trouves = set(), []
    for mot in sorted(_mots(phrase), key=len, reverse=True)[:4]:
        for e in agenda.chercher(member_id, mot):
            if e["id"] not in vus:
                vus.add(e["id"])
                trouves.append(e)
    return trouves


def _resume(evenements: List[dict], vide: str) -> str:
    if not evenements:
        return vide
    lignes = []
    for e in evenements:
        quand = datetime.strptime(e["debut"], "%Y-%m-%d %H:%M:%S")
        etat = " (fait)" if e.get("fait_le") else ""
        lignes.append(f"- {dit_la_date(quand)} : {e['titre']}{etat}")
    return "\n".join(lignes)


class _OutilAgenda(Tool):
    def __init__(self, agenda: Agenda, member_id: str,
                 horloge: Optional[Callable[[], datetime]] = None) -> None:
        self._agenda = agenda
        self._member_id = member_id
        self._horloge = horloge or datetime.now


class AjouterTool(_OutilAgenda):
    """Enregistre un rendez-vous, un traitement, une activité."""

    def __init__(self, agenda, member_id, horloge=None) -> None:
        super().__init__(agenda, member_id, horloge)
        self.spec = ToolSpec(
            name="agenda_ajouter",
            description=(
                "Enregistre un événement dans l'agenda de la personne : rendez-vous, "
                "prise de traitement, activité, tâche. À utiliser dès qu'elle demande "
                "de retenir ou de rappeler quelque chose de daté."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "titre": {"type": "string",
                              "description": "Ce dont il s'agit, ex. « comprimé du matin »"},
                    "quand": {"type": "string",
                              "description": "L'expression EXACTE dite par la personne : "
                                             "« demain à 14h », « tous les matins à 8h », "
                                             "« le 3 septembre ». Ne calcule pas la date."},
                    "categorie": {"type": "string",
                                  "description": "rendez-vous, traitement, activite, tache, repas, autre"},
                    "detail": {"type": "string", "description": "Précision éventuelle."},
                },
                "required": ["titre", "quand"],
            },
        )

    async def run(self, args: dict) -> str:
        titre = (args.get("titre") or "").strip()
        quand_dit = (args.get("quand") or "").strip()
        if not titre:
            return "Erreur : je n'ai pas compris de quoi il s'agit."
        maintenant = self._horloge()
        debut = analyse(quand_dit, maintenant)
        if debut is None:
            # On ne place RIEN au hasard : mieux vaut redemander.
            return ("Je n'ai pas compris la date. Demande-lui de la préciser "
                    "(par exemple « demain à 14 heures » ou « tous les matins à 8 heures »).")
        categorie = (args.get("categorie") or "rendez-vous").strip().lower()
        if categorie not in CATEGORIES:
            categorie = "rendez-vous"
        self._agenda.ajouter(
            self._member_id, titre, debut,
            categorie=categorie,
            detail=(args.get("detail") or ""),
            recurrence=detecte_recurrence(quand_dit),
            maintenant=maintenant,
        )
        repete = detecte_recurrence(quand_dit)
        suite = "" if repete == "aucune" else f", et ensuite en {repete}"
        return f"Enregistré : {titre}, {dit_la_date(debut)}{suite}."


class JourneeTool(_OutilAgenda):
    """Ce qui est prévu aujourd'hui."""

    def __init__(self, agenda, member_id, horloge=None) -> None:
        super().__init__(agenda, member_id, horloge)
        self.spec = ToolSpec(
            name="agenda_journee",
            description=("Ce que la personne a de prévu aujourd'hui. À utiliser pour "
                         "« qu'est-ce que j'ai aujourd'hui ? », « ma journée »."),
            parameters={"type": "object", "properties": {}},
        )

    async def run(self, args: dict) -> str:
        return _resume(self._agenda.du_jour(self._member_id, self._horloge()),
                       "Rien de prévu aujourd'hui.")


class AVenirTool(_OutilAgenda):
    """Les jours qui viennent."""

    def __init__(self, agenda, member_id, horloge=None) -> None:
        super().__init__(agenda, member_id, horloge)
        self.spec = ToolSpec(
            name="agenda_a_venir",
            description=("Ce qui arrive dans les prochains jours. À utiliser pour "
                         "« ma semaine », « qu'est-ce qui m'attend ? »."),
            parameters={
                "type": "object",
                "properties": {"jours": {"type": "integer",
                                         "description": "Nombre de jours à regarder (7 par défaut)."}},
            },
        )

    async def run(self, args: dict) -> str:
        try:
            jours = max(1, min(60, int(args.get("jours") or 7)))
        except (TypeError, ValueError):
            jours = 7
        return _resume(self._agenda.a_venir(self._member_id, jours, self._horloge()),
                       f"Rien de prévu dans les {jours} prochains jours.")


class OublisTool(_OutilAgenda):
    """Ce qui est passé sans avoir été fait."""

    def __init__(self, agenda, member_id, horloge=None) -> None:
        super().__init__(agenda, member_id, horloge)
        self.spec = ToolSpec(
            name="agenda_oublis",
            description=("Ce qui était prévu, dont l'heure est passée, et qui n'a pas "
                         "été marqué comme fait. À utiliser pour « est-ce que j'ai "
                         "oublié quelque chose ? », « j'ai pris mon traitement ? »."),
            parameters={"type": "object", "properties": {}},
        )

    async def run(self, args: dict) -> str:
        return _resume(self._agenda.en_retard(self._member_id, 30, self._horloge()),
                       "Rien d'oublié, tout est à jour.")


class SouvenirTool(_OutilAgenda):
    """Ce qui s'est passé récemment — le fil d'Ariane."""

    def __init__(self, agenda, member_id, horloge=None) -> None:
        super().__init__(agenda, member_id, horloge)
        self.spec = ToolSpec(
            name="agenda_recemment",
            description=("Ce qui s'est passé ces derniers jours. À utiliser pour "
                         "« qu'est-ce que j'ai fait hier ? », « où j'en étais ? »."),
            parameters={
                "type": "object",
                "properties": {"jours": {"type": "integer",
                                         "description": "Nombre de jours en arrière (2 par défaut)."}},
            },
        )

    async def run(self, args: dict) -> str:
        try:
            jours = max(1, min(30, int(args.get("jours") or 2)))
        except (TypeError, ValueError):
            jours = 2
        return _resume(self._agenda.passe(self._member_id, jours, self._horloge()),
                       "Rien de noté ces derniers jours.")


class FaitTool(_OutilAgenda):
    """Marque un événement comme accompli, désigné par son titre."""

    def __init__(self, agenda, member_id, horloge=None) -> None:
        super().__init__(agenda, member_id, horloge)
        self.spec = ToolSpec(
            name="agenda_marquer_fait",
            description=("Note qu'un événement a bien été fait. À utiliser quand la "
                         "personne dit « c'est fait », « je l'ai pris », « j'y suis allé »."),
            parameters={
                "type": "object",
                "properties": {"titre": {"type": "string",
                                         "description": "Ce qui a été fait, tel qu'elle le dit."}},
                "required": ["titre"],
            },
        )

    async def run(self, args: dict) -> str:
        mot = (args.get("titre") or "").strip()
        if not mot:
            return "Erreur : je ne sais pas de quoi il s'agit."
        maintenant = self._horloge()
        # On cherche d'abord parmi les oublis, puis la journée : c'est presque
        # toujours de l'un des deux qu'il s'agit.
        candidats = (self._agenda.en_retard(self._member_id, 0, maintenant)
                     + self._agenda.du_jour(self._member_id, maintenant)
                     + _chercher_par_mots(self._agenda, self._member_id, mot))
        for e in candidats:
            if e.get("fait_le"):
                continue
            if _correspond(mot, e["titre"]):
                if self._agenda.marquer_fait(self._member_id, e["id"], maintenant):
                    return f"C'est noté : « {e['titre']} » est fait."
        return (f"Je ne trouve pas « {mot} » dans ce qui reste à faire. "
                "Demande-lui de préciser.")


class AnnulerTool(_OutilAgenda):
    """Annule un événement, désigné par son titre."""

    def __init__(self, agenda, member_id, horloge=None) -> None:
        super().__init__(agenda, member_id, horloge)
        self.spec = ToolSpec(
            name="agenda_annuler",
            description=("Annule un événement prévu. À utiliser pour « annule mon "
                         "rendez-vous de jeudi », « ce n'est plus la peine »."),
            parameters={
                "type": "object",
                "properties": {"titre": {"type": "string",
                                         "description": "L'événement à annuler."}},
                "required": ["titre"],
            },
        )

    async def run(self, args: dict) -> str:
        mot = (args.get("titre") or "").strip()
        if not mot:
            return "Erreur : je ne sais pas quoi annuler."
        for e in _chercher_par_mots(self._agenda, self._member_id, mot):
            if not _correspond(mot, e["titre"]):
                continue
            if self._agenda.annuler(self._member_id, e["id"]):
                return f"Annulé : « {e['titre']} »."
        return f"Je ne trouve pas « {mot} » dans l'agenda."


class ChercherTool(_OutilAgenda):
    """Retrouve un événement par un mot."""

    def __init__(self, agenda, member_id, horloge=None) -> None:
        super().__init__(agenda, member_id, horloge)
        self.spec = ToolSpec(
            name="agenda_chercher",
            description=("Retrouve un événement par un mot. À utiliser pour « quand "
                         "est mon rendez-vous chez le cardiologue ? »."),
            parameters={
                "type": "object",
                "properties": {"mot": {"type": "string", "description": "Mot à chercher."}},
                "required": ["mot"],
            },
        )

    async def run(self, args: dict) -> str:
        mot = (args.get("mot") or "").strip()
        if not mot:
            return "Erreur : je ne sais pas quoi chercher."
        return _resume(_chercher_par_mots(self._agenda, self._member_id, mot),
                       f"Je ne trouve rien à propos de « {mot} ».")


def build_agenda_tools(agenda: Agenda, member_id: str,
                       horloge: Optional[Callable[[], datetime]] = None) -> List[Tool]:
    """Les outils d'agenda liés à CETTE personne (isolation par construction)."""
    return [
        AjouterTool(agenda, member_id, horloge),
        JourneeTool(agenda, member_id, horloge),
        AVenirTool(agenda, member_id, horloge),
        OublisTool(agenda, member_id, horloge),
        SouvenirTool(agenda, member_id, horloge),
        FaitTool(agenda, member_id, horloge),
        AnnulerTool(agenda, member_id, horloge),
        ChercherTool(agenda, member_id, horloge),
    ]
