"""Comprendre une date dite à voix haute, en français, SANS le modèle de langage.

« demain à 14 h », « lundi prochain », « dans trois jours », « tous les matins à 8 h ».

Pourquoi pas le modèle : il ne sait pas quel jour on est, et quand il l'ignore, il
invente — il produira une date plausible plutôt que de le dire. Sur un agenda destiné
à quelqu'un dont la mémoire flanche, une date inventée est pire que pas de date. Le
calcul est donc fait ici, en Python, à partir d'une horloge réelle.

Ce module ne devine jamais : ce qu'il ne comprend pas, il le rend en None. C'est au
reste du système de demander une précision plutôt que de supposer.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional, Tuple

JOURS = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
    "vendredi": 4, "samedi": 5, "dimanche": 6,
}

MOIS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
}

NOMBRES = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6,
    "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12,
    "quinze": 15, "vingt": 20, "trente": 30,
}

# Moments de la journée : ce que les gens disent vraiment au lieu d'une heure.
MOMENTS = {
    "matin": (8, 0), "matinee": (9, 0), "midi": (12, 0), "apres-midi": (14, 0),
    "gouter": (16, 0), "soir": (19, 0), "soiree": (20, 0), "coucher": (21, 0),
    "nuit": (22, 0),
}

RECURRENCES = {
    "quotidien": ("tous les jours", "chaque jour", "tous les matins", "tous les soirs",
                  "tous les midis", "quotidien", "quotidienne", "chaque matin",
                  "chaque soir", "tous les jours a"),
    "hebdomadaire": ("toutes les semaines", "chaque semaine", "hebdomadaire",
                     "tous les lundis", "tous les mardis", "tous les mercredis",
                     "tous les jeudis", "tous les vendredis", "tous les samedis",
                     "tous les dimanches"),
    "mensuel": ("tous les mois", "chaque mois", "mensuel", "mensuelle"),
}


def _sans_accent(texte: str) -> str:
    n = unicodedata.normalize("NFD", (texte or "").lower())
    return "".join(c for c in n if unicodedata.category(c) != "Mn")


def detecte_recurrence(texte: str) -> str:
    """« tous les matins » → quotidien. « aucune » si rien n'est répété."""
    t = _sans_accent(texte)
    for cle, formes in RECURRENCES.items():
        if any(f in t for f in formes):
            return cle
    return "aucune"


def _heure(texte: str) -> Optional[Tuple[int, int]]:
    """Extrait une heure : « 14h », « 14 h 30 », « 8 heures », « à 9 »."""
    t = _sans_accent(texte)
    m = re.search(r"\b(\d{1,2})\s*(?:h|heures?|:)\s*(\d{1,2})?\b", t)
    if m:
        h = int(m.group(1))
        mn = int(m.group(2) or 0)
        if 0 <= h <= 23 and 0 <= mn <= 59:
            # « à 8 h » le soir : on ne devine pas, 8 h reste 8 h.
            return h, mn
    # Du plus long au plus court : « après-midi » contient « midi », et le tiret
    # compte comme une limite de mot — sans ce tri, « demain après-midi » donnait 12 h.
    for mot in sorted(MOMENTS, key=len, reverse=True):
        if re.search(rf"\b{mot}\b", t):
            return MOMENTS[mot]
    return None


def _applique_heure(base: datetime, texte: str, heure_defaut=(9, 0)) -> datetime:
    h, mn = _heure(texte) or heure_defaut
    return base.replace(hour=h, minute=mn, second=0, microsecond=0)


def analyse(texte: str, maintenant: Optional[datetime] = None) -> Optional[datetime]:
    """Rend la date-heure exprimée, ou None si la phrase n'en contient pas.

    None n'est pas un échec : c'est l'information « je n'ai pas compris », qui doit
    conduire à demander plutôt qu'à supposer.
    """
    if not texte:
        return None
    m = maintenant or datetime.now()
    t = _sans_accent(texte)

    # Date explicite : « le 3 septembre », « 3 septembre à 14h », « 03/09 ».
    md = re.search(r"\b(\d{1,2})\s*/\s*(\d{1,2})(?:\s*/\s*(\d{2,4}))?\b", t)
    if md:
        jour, mois = int(md.group(1)), int(md.group(2))
        annee = int(md.group(3) or m.year)
        if annee < 100:
            annee += 2000
        try:
            return _applique_heure(datetime(annee, mois, jour), t)
        except ValueError:
            return None
    mn_ = re.search(rf"\b(\d{{1,2}})\s+({'|'.join(MOIS)})\b", t)
    if mn_:
        jour, mois = int(mn_.group(1)), MOIS[mn_.group(2)]
        annee = m.year
        try:
            d = datetime(annee, mois, jour)
        except ValueError:
            return None
        # Un mois déjà passé désigne l'année suivante : « le 3 janvier » dit en août.
        if d.date() < m.date():
            d = d.replace(year=annee + 1)
        return _applique_heure(d, t)

    # « dans trois jours », « dans 2 semaines », « dans une heure »
    md = re.search(r"\bdans\s+(\d+|" + "|".join(NOMBRES) + r")\s+"
                   r"(minutes?|heures?|jours?|semaines?|mois)\b", t)
    if md:
        brut = md.group(1)
        n = int(brut) if brut.isdigit() else NOMBRES[brut]
        unite = md.group(2)
        if unite.startswith("minute"):
            return (m + timedelta(minutes=n)).replace(second=0, microsecond=0)
        if unite.startswith("heure"):
            return (m + timedelta(hours=n)).replace(second=0, microsecond=0)
        if unite.startswith("jour"):
            return _applique_heure(m + timedelta(days=n), t)
        if unite.startswith("semaine"):
            return _applique_heure(m + timedelta(weeks=n), t)
        return _applique_heure(m + timedelta(days=30 * n), t)

    if re.search(r"\bapres[- ]demain\b", t):
        return _applique_heure(m + timedelta(days=2), t)
    if re.search(r"\bdemain\b", t):
        return _applique_heure(m + timedelta(days=1), t)
    if re.search(r"\bhier\b", t):
        return _applique_heure(m - timedelta(days=1), t)
    if re.search(r"\baujourd(?:'|\s)?hui\b|\bce soir\b|\bce matin\b|"
                 r"\bcet apres[- ]midi\b|\bce midi\b", t):
        return _applique_heure(m, t)

    # « lundi », « lundi prochain », « mardi matin »
    for nom, cible in JOURS.items():
        if re.search(rf"\b{nom}\b", t):
            ecart = (cible - m.weekday()) % 7
            if ecart == 0 or "prochain" in t:
                ecart = ecart or 7
                if "prochain" in t and ecart != 7:
                    ecart = (cible - m.weekday()) % 7 or 7
            return _applique_heure(m + timedelta(days=ecart), t)

    # Une heure seule vaut pour aujourd'hui, ou demain si elle est déjà passée.
    h = _heure(texte)
    if h:
        d = m.replace(hour=h[0], minute=h[1], second=0, microsecond=0)
        return d if d > m else d + timedelta(days=1)
    return None
