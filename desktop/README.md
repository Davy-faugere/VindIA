# VindIA — application de bureau (Windows)

Application native qui affiche VindIA dans une vraie fenêtre et, surtout, fait le pont
avec les **fichiers locaux du poste** — ce qu'un navigateur seul ne permet pas.

## Installation

Télécharger l'installeur `.exe` depuis les [Releases](../../releases) du dépôt, puis le
lancer. Windows peut afficher un avertissement SmartScreen (installeur non signé par un
certificat commercial) : « Informations complémentaires » → « Exécuter quand même ».

## Ce que l'application apporte

- Fenêtre dédiée, icône bureau et menu Démarrer
- **Dossiers de travail** : l'utilisateur choisit les dossiers auxquels VindIA a accès
  (menu *Fichier → Ajouter un dossier de travail*). Aucun autre dossier n'est lisible.
- Micro autorisé pour la dictée vocale

## Architecture

Le moteur de VindIA (LLM) tourne sur le serveur. Pour qu'il lise un fichier du poste,
son contenu doit remonter au serveur : l'application assure ce transfert de manière
intégrée. C'est ce qui remplace Syncthing — une seule application, aucune configuration.

Sécurité : la page n'a jamais accès à Node ni au disque (`contextIsolation`). Elle ne
peut appeler que les fonctions exposées par `preload.js`, et uniquement sur les dossiers
explicitement autorisés par l'utilisateur (vérifié côté processus principal, avec
protection contre la traversée de répertoire).

## Développement

```bash
cd desktop
npm install
npm start          # lance l'application en local
```

La fabrication de l'installeur Windows se fait via GitHub Actions
(`.github/workflows/desktop-build.yml`), le serveur de développement étant sous Linux.
