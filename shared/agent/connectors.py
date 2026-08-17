"""Catalogue des services que chacun peut brancher sur VindIA.

Principe : personne n'hérite des accès de personne. L'administrateur branche SON
Notion, un autre utilisateur branchera le sien — même mécanisme, mêmes limites. Le
jeton vit dans le coffre chiffré, rangé par membre, et les outils correspondants ne
sont donnés au modèle que pour la session de ce membre.

Comme pour les fournisseurs d'IA, le catalogue porte le MODE D'EMPLOI : où aller,
quoi cliquer, et le piège propre à chaque service — sans quoi personne ne va au bout
de la connexion.

0 dépendance tierce.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Connecteur:
    code: str
    nom: str
    resume: str          # ce que ça apporte, en une phrase
    console_url: str
    prefixe_jeton: str
    etapes: List[str]
    piege: str           # l'erreur que tout le monde fait
    page_accueil: str = ""   # si renseigné, le service accepte une page de dépôt

    def as_dict(self) -> dict:
        return self.__dict__.copy()


CONNECTEURS: Dict[str, Connecteur] = {
    c.code: c
    for c in [
        Connecteur(
            code="notion",
            nom="Notion",
            resume="VindIA peut chercher et lire vos pages Notion pour s'appuyer dessus.",
            console_url="https://www.notion.so/my-integrations",
            prefixe_jeton="ntn_",
            etapes=[
                "Ouvrez notion.so/my-integrations et cliquez « New integration ».",
                "Donnez-lui un nom (par exemple VindIA), choisissez votre espace de "
                "travail, et gardez les autorisations en LECTURE seule.",
                "Copiez le jeton affiché (« Internal Integration Secret »).",
                "Collez-le ci-dessous.",
                "Dans Notion, ouvrez chaque page à partager : menu « … » en haut à "
                "droite, « Connexions », puis choisissez VindIA. Partager une page "
                "partage aussi toutes ses sous-pages.",
            ],
            piege="Créer le jeton ne suffit PAS : tant qu'aucune page n'est partagée "
                  "avec l'intégration, VindIA ne voit rien du tout.",
            page_accueil="Collez l'adresse de la page où VindIA doit ranger ce "
                         "qu'elle produit. Elle ne pourra créer QUE sous cette page, "
                         "et ne modifiera jamais vos pages existantes.",
        ),
    ]
}

# Préfixe du service dans le coffre : « conn:notion », « conn:supabase »…
def vault_service(code: str) -> str:
    return f"conn:{code}"


def get_connecteur(code: str) -> Optional[Connecteur]:
    return CONNECTEURS.get((code or "").strip().lower())


def catalogue() -> List[dict]:
    return [c.as_dict() for c in CONNECTEURS.values()]


def verifie_jeton(code: str, jeton: str) -> Optional[str]:
    """Message d'erreur si le jeton est manifestement mauvais, sinon None."""
    c = get_connecteur(code)
    if c is None:
        return "Service inconnu."
    jeton = (jeton or "").strip()
    if not jeton:
        return "Jeton vide."
    if " " in jeton or "\n" in jeton:
        return "Le jeton contient un espace : recopiez-le sans rien autour."
    if len(jeton) < 20:
        return "Ce jeton est trop court : il manque probablement une partie."
    if c.prefixe_jeton and not jeton.startswith(c.prefixe_jeton):
        # Notion a longtemps préfixé « secret_ » : on accepte l'ancien format plutôt
        # que de refuser un jeton valide créé il y a quelques mois.
        if not (c.code == "notion" and jeton.startswith("secret_")):
            return (f"Un jeton {c.nom} commence normalement par « {c.prefixe_jeton} ». "
                    "Vérifiez que vous avez copié le bon.")
    return None


import re as _re

# On cherche l'identifiant sur la chaîne BRUTE, tirets compris. Les retirer d'abord
# collait le titre à l'identifiant (« Vindia-3bfa… » → « Vindia3bfa… ») et le motif
# démarrait un caractère trop tôt, sur le « a » de Vindia : identifiant faux, page
# introuvable. Le tiret est justement ce qui marque la frontière.
_ID = _re.compile(
    r"[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}"
)


def page_id_depuis_url(url: str) -> str:
    """Identifiant d'une page à partir de son adresse (ou d'un id déjà nu).

    Les gens collent l'URL complète du navigateur, pas un identifiant : la refuser
    serait un obstacle inutile.
    """
    trouves = _ID.findall((url or "").strip())
    # Le DERNIER : une URL Notion place l'identifiant en fin de segment, après le titre.
    return trouves[-1].replace("-", "") if trouves else ""
