# VindIA — Dossier R&D

Espace de **recherche & développement** de l'agent vocal conversationnel souverain VindIA.
Travail R&D sérieux, **traçable et sourcé** (politique « 0 hallucination » : toute affirmation
technique ou réglementaire renvoie à une source primaire ; les incertitudes sont marquées
`[INCERTAIN]` ou `[NON TROUVÉ]`).

## Objet

Davy souhaite « un agent avec qui [il] échange en parlant et qui [lui] répond avec la voix »,
construit **pas à pas**, **testé ensemble**, avec **notifications** d'avancement, un **catalogue de
compétences/skills** fiable, un report **Notion**, un **dossier d'avancement** et un **cahier des
charges**. Cet agent **est VindIA** (déjà amorcé dans ce dépôt : pipeline LiveKit ⇄ VAD ⇄ STT
Voxtral → LLM Mistral → TTS, souveraineté EU, audit).

## Plan du dossier

| Fichier | Rôle |
|---|---|
| [`00-CAHIER-DES-CHARGES.md`](./00-CAHIER-DES-CHARGES.md) | Spécifications : vision, périmètre, exigences fonctionnelles/non-fonctionnelles, contraintes de souveraineté, architecture cible, jalons, critères d'acceptation, budget de latence. |
| [`01-DOSSIER-AVANCEMENT.md`](./01-DOSSIER-AVANCEMENT.md) | Journal d'avancement daté + état du moment + prochaines actions. |
| [`02-REGISTRE-BLOCAGES.md`](./02-REGISTRE-BLOCAGES.md) | Registre des blocages (sévérité, responsable, statut) — pierre angulaire du « préparer + lever les blocages ». |
| [`03-VEILLE-SOURCEE.md`](./03-VEILLE-SOURCEE.md) | Veille R&D sourcée : stack technique, latence/turn-taking, échec/robustesse, conformité EU, skills/MCP. |
| [`04-ARCHITECTURE-ALGORIGRAMME.md`](./04-ARCHITECTURE-ALGORIGRAMME.md) | Modèle complet : schémas d'architecture + algorigrammes (Mermaid), machine à états du tour de parole, flux de conformité. |
| [`05-CATALOGUE-SKILLS.md`](./05-CATALOGUE-SKILLS.md) | Modèle de compétences/skills réutilisables (tool-calling, MCP, SKILL.md), garde-fous et évaluation. |

## Méthode de travail (chaque session)

1. **Récupérer un maximum d'informations** sur un ou plusieurs blocages ouverts (recherche sourcée).
2. **Mettre à jour** le registre des blocages + le dossier d'avancement.
3. **Notifier** Davy (push app Claude Code + jalon/rappel Google Calendar).
4. **Reporter** la synthèse dans Notion (page « VindIA — R&D », sous *Atelier Produits*).

## Conventions

- SemVer + Conventional Commits (hérité du dépôt).
- 0 dépendance pour les tests unitaires / CI (hérité du dépôt).
- Souveraineté EU *first* ; modèles STT/LLM/TTS substituables.
