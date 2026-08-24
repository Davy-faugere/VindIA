"""Charte de mise en page des documents produits par VindIA.

Avant ce module, les documents sortaient en titres bruts et paragraphes collés : la
mise en page se résumait à « du gras et des puces ». L'utilisateur l'a dit sans
détour — « ça ne me donne même pas envie d'utiliser VindIA pour faire des documents ».

Deux choses ici, et une seule fois pour tous les formats :

1. La CHARTE : couleurs, tailles, marges. Une source unique — c'est la répétition des
   listes de formats en dur qui a déjà coûté trois corrections en deux jours.

2. L'EN-TÊTE de document : un bloc `---` en tête du contenu où l'on déclare titre,
   sous-titre, auteur et couleur. C'est ainsi que la personne choisit ses couleurs sans
   toucher au code, et que le document gagne une page de garde.

Format de l'en-tête, volontairement simple à produire pour un modèle de langage :

    ---
    titre: Rapport commercial
    sous-titre: Trimestre 3
    auteur: EI Faugère Davy
    couleur: #0891b2
    ---
    # Première partie
    ...
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Tuple

# Palettes nommées : la personne dit « en bleu » ou « en vert », pas « #0891b2 ».
PALETTES: Dict[str, str] = {
    "cyan": "#0891b2",
    "bleu": "#1d4ed8",
    "indigo": "#4f46e5",
    "violet": "#7c3aed",
    "vert": "#047857",
    "orange": "#c2410c",
    "rouge": "#b91c1c",
    "rose": "#be185d",
    "ardoise": "#334155",
    "noir": "#111827",
}

COULEUR_DEFAUT = PALETTES["cyan"]

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def couleur_valide(valeur: str) -> str:
    """Rend une couleur hexadécimale sûre à partir d'un nom ou d'un code.

    Tout ce qui n'est pas reconnu retombe sur la couleur par défaut : une valeur
    fantaisiste dans l'en-tête ne doit jamais casser la génération du document.
    """
    v = (valeur or "").strip().lower()
    if _HEX.match(v):
        return v
    return PALETTES.get(v, COULEUR_DEFAUT)


def _eclaircir(hexa: str, facteur: float) -> str:
    """Variante claire d'une couleur, pour les fonds d'encadré et les en-têtes de
    tableau. Évite d'imposer une seconde couleur à choisir."""
    h = hexa.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = lambda c: max(0, min(255, int(c + (255 - c) * facteur)))  # noqa: E731
    return f"#{m(r):02x}{m(g):02x}{m(b):02x}"


@dataclass(frozen=True)
class Charte:
    """Toutes les valeurs de mise en page d'un document."""

    couleur: str = COULEUR_DEFAUT
    titre: str = ""
    sous_titre: str = ""
    auteur: str = ""
    date: str = ""

    # Tailles en points. Écart franc entre les niveaux : c'est ce qui donne une
    # hiérarchie lisible d'un coup d'œil, plus que la couleur.
    taille_titre_couverture: int = 32
    taille_h1: int = 19
    taille_h2: int = 15
    taille_h3: int = 12
    taille_corps: int = 11
    taille_legende: int = 9

    @property
    def fond_clair(self) -> str:
        return _eclaircir(self.couleur, 0.90)

    @property
    def fond_moyen(self) -> str:
        return _eclaircir(self.couleur, 0.75)

    @property
    def gris_texte(self) -> str:
        return "#4b5563"

    @property
    def gris_filet(self) -> str:
        return "#d1d5db"

    @property
    def a_couverture(self) -> bool:
        """Une page de garde n'a de sens que si le document porte un titre."""
        return bool(self.titre.strip())


_LIGNE = re.compile(r"^\s*([\w\-àéèêîôûç]+)\s*:\s*(.*?)\s*$", re.IGNORECASE)

_CLES = {
    "titre": "titre", "title": "titre",
    "sous-titre": "sous_titre", "sous_titre": "sous_titre", "subtitle": "sous_titre",
    "auteur": "auteur", "author": "auteur",
    "couleur": "couleur", "color": "couleur",
    "date": "date",
}


def lire_entete(contenu: str) -> Tuple[Charte, str]:
    """Sépare l'en-tête `---` du corps. Retourne (charte, corps).

    Sans en-tête, on rend la charte par défaut et le contenu inchangé : les documents
    déjà produits gardent exactement le même rendu.
    """
    texte = (contenu or "").lstrip("﻿")
    lignes = texte.splitlines()
    if not lignes or lignes[0].strip() != "---":
        return Charte(), texte

    valeurs: Dict[str, str] = {}
    fin = None
    for i, ligne in enumerate(lignes[1:], start=1):
        if ligne.strip() == "---":
            fin = i
            break
        m = _LIGNE.match(ligne)
        if m:
            cle = _CLES.get(m.group(1).strip().lower())
            if cle:
                valeurs[cle] = m.group(2).strip().strip('"').strip("'")
    if fin is None:                       # en-tête jamais refermé : on n'y touche pas
        return Charte(), texte

    couleur = couleur_valide(valeurs.pop("couleur", ""))
    return Charte(couleur=couleur, **valeurs), "\n".join(lignes[fin + 1:]).lstrip("\n")
