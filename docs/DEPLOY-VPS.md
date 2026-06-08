# Déploiement VPS — VindIA

## §1 Pré-requis
- Python 3.11, Docker + docker compose (pour MariaDB, **après validation**).
- Accès LiveKit (URL + API key/secret).

## §2 Récupération
```bash
git clone git@github.com:Davy-faugere/VindIA.git
cd VindIA
python3 -m unittest discover -s shared/agent/tests -t . -v
```

## §3 Secrets (NE JAMAIS committer)
La clé Mistral existe déjà sur le VPS. Renseigner `server/.env` à partir du gabarit,
sans jamais l'afficher en clair ni la committer (`.env` est dans `.gitignore`).

```bash
cp server/.env.example server/.env
# éditer server/.env et renseigner MISTRAL_API_KEY + LIVEKIT_* + DB_DSN
chmod 600 server/.env
```

Vérifier qu'aucun secret n'est suivi par git avant tout push :
```bash
git check-ignore server/.env      # doit afficher server/.env
git ls-files | grep -E '\.env$'   # doit être vide
```

## §4 Base de données — BLOQUÉ tant que non validé
`db/01-schema.sql` est une **proposition**. La création réelle
(`docker compose up -d mariadb` + application du schéma) ne se fait **qu'après accord
explicite de Davy**, et après arbitrage de l'encodage des ID (CHAR(36) recommandé).
