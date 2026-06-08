# VindIA

Agent vocal temps réel, **souveraineté EU** et **compliant by design**.
Pipeline audio LiveKit ⇄ VAD/diarisation ⇄ LLM (Mistral/Voxtral, modèles substituables),
avec isolation tenant, consentement explicite, audit append-only et anti-profilage.

> Statut : **bootstrap**. Ce dépôt démarre par la fondation technique (structure,
> contrats d'E/S audio, CI publique). La couche métier complète et le schéma de base
> de données sont en cours de cadrage — voir `docs/` et les jalons de validation.

## Principes (garde-fous)

- **1 personne = 1 device = 1 identité.** Casques + half-duplex anti-larsen.
- Le `speaker_id` Voxtral est un **label de diarisation** → résolu vers un `member_id`.
- Aucun secret en clair, `.env` ignoré par git (cf. `docs/DEPLOY-VPS.md` §3).
- Self-hosted first ; modèles LLM/STT substituables ; SemVer + Conventional Commits.

## Structure

```
shared/agent/
  session.py            SessionDescriptor (tenant, member, consentement)
  router.py             dispatch des énoncés finalisés vers le runtime
  audio/
    vad.py              segmentation voix (énergie, stdlib pure, testée)
    livekit_io.py       LiveKitRoomOut / LiveKitAudioBridge + RoomSessionRegistry
  main.py               run() : câblage room → session → I/O
  tests/                tests unitaires (0 dépendance)
db/01-schema.sql        schéma MariaDB — PROPOSITION (non appliqué, à valider)
server/.env.example     gabarit de configuration (secrets hors git)
docs/                   brief, architecture, déploiement
```

## Tests

```bash
python3 -m unittest discover -s shared/agent/tests -t . -v
```

CI publique : `.github/workflows/ci.yml` (logs lisibles sans authentification).
