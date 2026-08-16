"""Catalogue des fournisseurs d'IA utilisables avec sa PROPRE clé.

Chacun apporte sa clé : VindIA ne facture rien et l'utilisateur garde la main sur
son fournisseur. Ce module rassemble, pour chaque fournisseur, ce qu'il faut pour
l'appeler ET ce qu'il faut expliquer à quelqu'un qui n'a jamais créé de clé API :
où aller, quoi cliquer, à quoi s'attendre.

Deux familles :
  - « openai » : OpenAI, xAI (Grok), Mistral, DeepSeek, Groq… parlent tous le même
    dialecte (/chat/completions). Un seul adaptateur les couvre, seule l'adresse
    de base change.
  - « anthropic » et « google » : dialectes propres, adaptateurs dédiés.

La TRANSPARENCE sur les données fait partie du catalogue (`hebergement`) : envoyer
ses documents à un fournisseur hors UE est un choix légitime, mais il doit être
éclairé — l'interface affiche cette mention avant la saisie de la clé.

0 dépendance tierce.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Provider:
    code: str            # identifiant interne (clé du coffre)
    nom: str             # nom affiché
    famille: str         # "openai" | "anthropic" | "google"
    base_url: str        # racine de l'API
    modele_defaut: str
    modeles: List[str]
    hebergement: str     # où partent les données — affiché à l'utilisateur
    dans_ue: bool        # champ explicite : « européenne » figure AUSSI dans
                         # « sortent de l'Union européenne », donc le déduire du
                         # texte classait les fournisseurs américains comme européens
    console_url: str     # page exacte où récupérer la clé
    prefixe_cle: str     # aide à détecter un copier-coller erroné
    gratuit: str         # ce qu'on peut faire sans payer
    etapes: List[str]    # marche à suivre, pour quelqu'un qui n'a jamais fait ça

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d.pop("base_url", None)      # inutile côté navigateur
        return d


# NB : les listes de modèles vieillissent vite. Elles ne servent qu'à proposer un
# choix par défaut raisonnable — une valeur inconnue reste acceptée.
PROVIDERS: Dict[str, Provider] = {
    p.code: p
    for p in [
        Provider(
            code="mistral",
            nom="Mistral",
            famille="openai",
            base_url="https://api.mistral.ai/v1",
            modele_defaut="mistral-large-latest",
            modeles=["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"],
            hebergement="France / Union européenne — vos données restent en Europe.",
            dans_ue=True,
            console_url="https://console.mistral.ai/api-keys",
            prefixe_cle="",
            gratuit="Offre d'essai gratuite, suffisante pour un usage personnel léger.",
            etapes=[
                "Ouvrez console.mistral.ai et connectez-vous (ou créez un compte).",
                "Dans le menu de gauche, cliquez « API Keys ».",
                "Cliquez « Create new key », donnez-lui un nom (par exemple VindIA).",
                "Copiez la clé affichée : elle ne sera plus jamais visible ensuite.",
                "Collez-la ci-dessous.",
            ],
        ),
        Provider(
            code="openai",
            nom="ChatGPT (OpenAI)",
            famille="openai",
            base_url="https://api.openai.com/v1",
            modele_defaut="gpt-4o",
            modeles=["gpt-4o", "gpt-4o-mini", "gpt-4.1"],
            hebergement="États-Unis. Vos documents sortent de l'Union européenne.",
            dans_ue=False,
            console_url="https://platform.openai.com/api-keys",
            prefixe_cle="sk-",
            gratuit="Non : il faut créditer le compte (quelques euros suffisent).",
            etapes=[
                "Ouvrez platform.openai.com/api-keys et connectez-vous.",
                "Attention : c'est un compte SÉPARÉ de votre abonnement ChatGPT, "
                "et il se crédite à part.",
                "Cliquez « Create new secret key ».",
                "Copiez la clé (elle commence par sk-) : elle ne sera plus affichée.",
                "Si les réponses échouent, vérifiez le crédit dans « Billing ».",
            ],
        ),
        Provider(
            code="xai",
            nom="Grok (xAI)",
            famille="openai",
            base_url="https://api.x.ai/v1",
            modele_defaut="grok-3",
            modeles=["grok-3", "grok-3-mini"],
            hebergement="États-Unis. Vos documents sortent de l'Union européenne.",
            dans_ue=False,
            console_url="https://console.x.ai",
            prefixe_cle="xai-",
            gratuit="Non : crédit requis. Un abonnement X Premium ne suffit PAS.",
            etapes=[
                "Ouvrez console.x.ai et connectez-vous.",
                "Allez dans « API Keys », puis « Create API Key ».",
                "Copiez la clé (elle commence par xai-).",
                "Créditez le compte dans « Billing » : l'abonnement X est distinct.",
            ],
        ),
        Provider(
            code="anthropic",
            nom="Claude (Anthropic)",
            famille="anthropic",
            base_url="https://api.anthropic.com/v1",
            modele_defaut="claude-sonnet-4-5",
            modeles=["claude-sonnet-4-5", "claude-opus-4-1", "claude-haiku-4-5"],
            hebergement="États-Unis. Vos documents sortent de l'Union européenne.",
            dans_ue=False,
            console_url="https://console.anthropic.com/settings/keys",
            prefixe_cle="sk-ant-",
            gratuit="Non : crédit requis. L'abonnement Claude Pro ne donne PAS de clé.",
            etapes=[
                "Ouvrez console.anthropic.com et connectez-vous.",
                "Attention : la console est SÉPARÉE de l'application Claude ; "
                "un abonnement Pro ou Max ne fournit pas de clé API.",
                "Allez dans « Settings », puis « API keys », puis « Create Key ».",
                "Copiez la clé (elle commence par sk-ant-).",
                "Ajoutez du crédit dans « Billing » avant la première utilisation.",
            ],
        ),
        Provider(
            code="google",
            nom="Gemini (Google)",
            famille="google",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            modele_defaut="gemini-2.5-flash",
            modeles=["gemini-2.5-flash", "gemini-2.5-pro"],
            hebergement="États-Unis. Vos documents sortent de l'Union européenne.",
            dans_ue=False,
            console_url="https://aistudio.google.com/apikey",
            prefixe_cle="AIza",
            gratuit="Oui : offre gratuite généreuse, avec une limite par minute.",
            etapes=[
                "Ouvrez aistudio.google.com/apikey avec votre compte Google.",
                "Cliquez « Create API key », puis choisissez un projet "
                "(« Create API key in new project » si vous n'en avez aucun).",
                "Copiez la clé (elle commence par AIza).",
            ],
        ),
        Provider(
            code="deepseek",
            nom="DeepSeek",
            famille="openai",
            base_url="https://api.deepseek.com/v1",
            modele_defaut="deepseek-chat",
            modeles=["deepseek-chat", "deepseek-reasoner"],
            hebergement="Chine. Vos documents sortent de l'Union européenne — "
                        "à éviter pour des documents professionnels sensibles.",
            dans_ue=False,
            console_url="https://platform.deepseek.com/api_keys",
            prefixe_cle="sk-",
            gratuit="Non, mais les tarifs sont très bas.",
            etapes=[
                "Ouvrez platform.deepseek.com et connectez-vous.",
                "Allez dans « API keys », puis « Create new API key ».",
                "Copiez la clé et créditez le compte.",
            ],
        ),
        Provider(
            code="groq",
            nom="Groq (rapide)",
            famille="openai",
            base_url="https://api.groq.com/openai/v1",
            modele_defaut="llama-3.3-70b-versatile",
            modeles=["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
            hebergement="États-Unis. Vos documents sortent de l'Union européenne.",
            dans_ue=False,
            console_url="https://console.groq.com/keys",
            prefixe_cle="gsk_",
            gratuit="Oui : offre gratuite, avec une limite par minute.",
            etapes=[
                "Ouvrez console.groq.com/keys et connectez-vous.",
                "Cliquez « Create API Key » et donnez-lui un nom.",
                "Copiez la clé (elle commence par gsk_).",
            ],
        ),
    ]
}

# Service du coffre où la clé est rangée (une seule connexion « mon IA » par membre).
VAULT_SERVICE = "llm"


def get_provider(code: str) -> Optional[Provider]:
    return PROVIDERS.get((code or "").strip().lower())


def catalogue() -> List[dict]:
    """Catalogue pour l'interface : l'européen d'abord, puis les gratuits."""
    def rang(p: Provider) -> tuple:
        return (0 if p.dans_ue else 1,
                0 if p.gratuit.startswith("Oui") else 1,
                p.nom)
    return [p.as_dict() for p in sorted(PROVIDERS.values(), key=rang)]


def verifie_cle(code: str, cle: str) -> Optional[str]:
    """Message d'erreur si la clé est manifestement mauvaise, sinon None.

    On ne valide pas la clé auprès du fournisseur ici (ce serait un appel réseau) :
    on rattrape seulement les erreurs de copier-coller les plus fréquentes, qui
    sinon se traduiraient par un « échec » incompréhensible en pleine conversation.
    """
    p = get_provider(code)
    if p is None:
        return "Fournisseur inconnu."
    cle = (cle or "").strip()
    if not cle:
        return "Clé vide."
    if " " in cle or "\n" in cle:
        return "La clé contient un espace : recopiez-la sans rien autour."
    if len(cle) < 16:
        return "Cette clé est trop courte : il manque probablement une partie."
    if p.prefixe_cle and not cle.startswith(p.prefixe_cle):
        return (f"Une clé {p.nom} commence normalement par « {p.prefixe_cle} ». "
                "Vérifiez que vous n'avez pas copié la clé d'un autre fournisseur.")
    return None
