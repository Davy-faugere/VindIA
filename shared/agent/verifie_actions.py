"""Empêche VindIA d'affirmer une action qu'elle n'a pas faite.

Constaté en réel à répétition : « J'ai créé le document et je l'ai déposé dans ton
dossier » alors qu'aucun fichier n'existait. La personne cherche, ne trouve rien, et
perd confiance dans tout le reste — y compris dans ce qui est vrai.

La consigne système ne suffit pas : un modèle de langage produit le texte le plus
plausible, et « j'ai créé le fichier » est très plausible après une demande de
document. On ne corrige donc pas ça par du prompt, mais par un contrôle DÉTERMINISTE
posé entre le modèle et l'utilisateur.

Règle unique : une affirmation de livraison n'est autorisée que si une PREUVE existe —
soit un outil d'écriture réellement appelé, soit le marqueur [[FICHIER:]] présent dans
la réponse. Sans preuve, l'affirmation est retirée et remplacée par la vérité.

Le contrôle ne juge JAMAIS le contenu du document : inventer un fait reste possible,
aucun garde-fou mécanique ne l'attrape. Il ne traite que ce qui est vérifiable.
"""

from __future__ import annotations

import re
from typing import Iterable, Tuple

# Outils qui écrivent réellement un fichier quelque part.
OUTILS_ECRITURE = {
    "synced_write_file",     # dossier synchronisé avec l'ordinateur
    "write_project_file",    # fichiers du projet
    "folder_write_file",     # retiré le 24/08/2026, gardé au cas où il reviendrait
}

# Une affirmation de livraison = un verbe d'action AU PASSÉ + un objet livrable.
# Le passé composé compte, le futur et le conditionnel non : « je vais créer » ou
# « je peux te préparer » n'affirment rien.
_VERBES = (
    r"(?:ai|a)\s+(?:bien\s+)?(?:créé|cree|crée|généré|genere|enregistré|enregistre|"
    r"déposé|depose|écrit|ecrit|sauvegardé|sauvegarde|placé|place|mis|ajouté|ajoute|"
    r"produit|rédigé|redige|exporté|exporte)"
)
_OBJETS = (
    r"(?:fichier|document|classeur|tableur|présentation|presentation|rapport|note|"
    r"compte[- ]rendu|pdf|docx|xlsx|pptx|odt|ods|csv|\.md)"
)

# « J'ai créé le document » — verbe puis objet, quelques mots entre les deux.
_AFFIRMATION = re.compile(
    rf"\b(?:j['’]\s*{_VERBES}|je\s+l['’]\s*{_VERBES})\b[^.!?\n]{{0,80}}?\b{_OBJETS}\b",
    re.IGNORECASE,
)
# « Le document a été créé », « il est enregistré dans ton dossier ».
_AFFIRMATION_PASSIVE = re.compile(
    rf"\b{_OBJETS}\b[^.!?\n]{{0,60}}?\b(?:a\s+été|est|sont|ont\s+été)\s+"
    r"(?:bien\s+)?(?:créé|cree|crée|généré|genere|enregistré|enregistre|déposé|depose|"
    r"écrit|ecrit|sauvegardé|sauvegarde|placé|place|ajouté|ajoute|disponible)",
    re.IGNORECASE,
)
# « Tu le trouveras dans ton dossier », « il apparaîtra sur ton ordinateur ».
_LOCALISATION = re.compile(
    r"\b(?:tu\s+(?:le|la|les)\s+(?:trouveras|retrouveras|verras)|"
    r"(?:il|elle)\s+(?:apparaîtra|apparaitra|se\s+trouve|est)\s+(?:dans|sur))\b"
    r"[^.!?\n]{0,60}?\b(?:dossier|ordinateur|répertoire|repertoire|bureau)\b",
    re.IGNORECASE,
)

MARQUEUR_FICHIER = re.compile(r"\[\[FICHIER:[^\]]+\]\]")

_PHRASE = re.compile(r"[^.!?\n]+[.!?]?")

_REMPLACEMENT = (
    "Je n'ai pas créé de fichier : je n'ai pas réussi à le produire. "
    "Redemande-le-moi en précisant le format voulu."
)


def preuve_de_livraison(outils_appeles: Iterable[str], texte: str) -> bool:
    """Un fichier a-t-il RÉELLEMENT été produit ?

    Deux preuves possibles : un outil d'écriture a tourné, ou la réponse porte le
    marqueur que la page transforme en téléchargement.
    """
    if MARQUEUR_FICHIER.search(texte or ""):
        return True
    return any(nom in OUTILS_ECRITURE for nom in (outils_appeles or ()))


def affirme_une_livraison(texte: str) -> bool:
    """Le texte prétend-il qu'un document a été produit ou déposé ?"""
    t = texte or ""
    return bool(
        _AFFIRMATION.search(t) or _AFFIRMATION_PASSIVE.search(t) or _LOCALISATION.search(t)
    )


def controle(texte: str, outils_appeles: Iterable[str]) -> Tuple[str, bool]:
    """Retourne (texte vérifié, une correction a-t-elle été appliquée).

    Sans preuve, les phrases qui affirment une livraison sont RETIRÉES — pas
    signalées, pas nuancées : retirées. Une phrase fausse laissée en place avec un
    avertissement à côté reste lue à voix haute, donc entendue comme vraie.
    """
    t = texte or ""
    if not t.strip():
        return t, False
    if preuve_de_livraison(outils_appeles, t):
        return t, False
    if not affirme_une_livraison(t):
        return t, False

    gardees = []
    for phrase in _PHRASE.findall(t):
        if affirme_une_livraison(phrase):
            continue
        if phrase.strip():
            gardees.append(phrase.strip())

    reste = " ".join(gardees).strip()
    # On garde ce qui reste utile (le raisonnement, le plan), on remplace le mensonge.
    return ((reste + " " + _REMPLACEMENT).strip() if reste else _REMPLACEMENT), True
