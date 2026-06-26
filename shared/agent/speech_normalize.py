"""Normalisation du texte avant synthèse vocale (TTS).

Couche DÉTERMINISTE entre la réponse du LLM et le TTS. Le LLM est probabiliste :
une consigne « ne lis pas les symboles / pas d'URL à l'oral » tenue à 95 % fuit
quand même. Cette couche, écrite en code, *garantit* qu'aucun markdown, aucune
URL ni aucun symbole brut n'arrive jamais à la voix — le code n'oublie pas.

Périmètre (décisions Davy) :
  - On NEUTRALISE : markdown (`**`, `#`, puces…), URLs/emails, symboles (`€`, `%`,
    `&`…) lus tels quels par le TTS.
  - On NE TOUCHE PAS aux mots anglais : ils sont conservés à l'identique. La
    bascule d'accent éventuelle se règle dans la config du moteur TTS, pas ici.

Contrainte CI : `re` (stdlib) uniquement → 0 dépendance, exécutable par la CI stdlib.
"""

from __future__ import annotations

import re

__all__ = ["normalize_for_speech"]

# Séparateurs de milliers possibles dans un montant FR : espace, espace insécable,
# espace fine insécable, point, virgule.
_NUM = r"\d[\d   .,]*"

# Blocs de code ``` ... ``` (multi-lignes) : jamais vocalisés.
_FENCED_CODE = re.compile(r"```.*?```", re.DOTALL)
# Filets horizontaux markdown (---, ***, ___, ===) sur une ligne seule. On
# consomme le saut de ligne final pour ne pas laisser une fausse coupure de
# paragraphe derrière soi.
_HRULE = re.compile(r"(?m)^[ \t]*([-*_=])\1{2,}[ \t]*$\n?")
# Images ![alt](url) — traitées AVANT les liens (on garde l'alt).
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
# Liens markdown [label](url) -> label (on jette l'URL, on garde le libellé).
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
# URLs nues (http(s):// ou www.) -> « le lien ».
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
# Emails -> « l'adresse e-mail ».
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# Titres markdown en début de ligne (#, ##, …).
_HEADING = re.compile(r"(?m)^[ \t]*#{1,6}[ \t]*")
# Citations « > … ».
_BLOCKQUOTE = re.compile(r"(?m)^[ \t]*>[ \t]?")
# Puces - * + en début de ligne.
_BULLET = re.compile(r"(?m)^[ \t]*[-*+][ \t]+")
# Listes numérotées « 1. ».
_ORDERED = re.compile(r"(?m)^[ \t]*\d+\.[ \t]+")
# Marqueurs d'emphase / code inline : on RETIRE le marqueur, on GARDE le contenu.
_EMPHASIS = re.compile(r"\*\*|\*|__|_|~~|`")
# Montants monétaires.
_EUR = re.compile(r"(" + _NUM + r")\s*€")
_USD = re.compile(r"(" + _NUM + r")\s*\$")
_GBP = re.compile(r"(" + _NUM + r")\s*£")
# Pourcentage.
_PERCENT = re.compile(r"(" + _NUM + r")\s*%")
# « n° » / « N° » -> « numéro ».
_NUMERO = re.compile(r"[nN]°")
# Bruit résiduel : symboles non vocalisables -> espace. On PRÉSERVE la ponctuation
# utile (. , ; : ! ? ' - « » ( )) et les lettres accentuées.
_NOISE = re.compile(r"[*#_`~|^<>\[\]{}\\/=+]+")
# Sauts de ligne : paragraphe -> pause forte, simple -> espace.
_PARA = re.compile(r"\n{2,}")
# Points qui se collent après transformation (". ." -> ".").
_DOT_DUP = re.compile(r"\.\s*\.")
# Espace parasite avant « , » et « . » (en français, PAS avant ? ! : ; qui
# prennent une espace fine — on la laisse, le TTS la gère).
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.])")
# Espaces multiples.
_WS = re.compile(r"[ \t]{2,}")


def normalize_for_speech(text: str, locale: str = "fr-FR") -> str:
    """Rend `text` propre à être lu par un TTS : sans markdown, URL ni symbole brut.

    Fonction pure et idempotente sur l'essentiel. `locale` est accepté pour
    évolutivité (règles par langue) ; la version actuelle vise le français.
    """
    if not text:
        return ""

    s = text
    s = _FENCED_CODE.sub(" ", s)
    s = _HRULE.sub("", s)
    s = _MD_IMAGE.sub(r"\1", s)
    s = _MD_LINK.sub(r"\1", s)
    s = _URL.sub("le lien", s)
    s = _EMAIL.sub("l'adresse e-mail", s)
    s = _HEADING.sub("", s)
    s = _BLOCKQUOTE.sub("", s)
    s = _BULLET.sub("", s)
    s = _ORDERED.sub("", s)
    s = _EMPHASIS.sub("", s)

    # Symboles -> mots (français).
    s = _EUR.sub(r"\1 euros", s)
    s = _USD.sub(r"\1 dollars", s)
    s = _GBP.sub(r"\1 livres", s)
    s = _PERCENT.sub(r"\1 pour cent", s)
    s = _NUMERO.sub("numéro ", s)
    s = s.replace("&", " et ")
    s = s.replace("@", " arobase ")
    s = s.replace("°", " degrés ")

    # Sauts de ligne -> ponctuation orale.
    s = _PARA.sub(". ", s)
    s = s.replace("\n", " ")

    # Bruit résiduel + resserrage.
    s = _NOISE.sub(" ", s)
    s = _DOT_DUP.sub(".", s)
    s = _SPACE_BEFORE_PUNCT.sub(r"\1", s)
    s = _WS.sub(" ", s)
    return s.strip()
