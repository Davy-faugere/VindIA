# VindIA — application Windows

Application de bureau pour VindIA : une vraie fenêtre, une icône sur le bureau, et
surtout un accès aux **fichiers de votre ordinateur** — ce qu'un navigateur ne permet
pas de faire.

---

## Installation

1. Téléchargez le fichier `VindIA.Setup.x.y.z.exe` depuis la page
   [Releases](../../releases) du dépôt.
2. Double-cliquez dessus.
3. Windows affiche un avertissement bleu (voir ci-dessous) : cliquez sur
   **« Informations complémentaires »**, puis sur **« Exécuter quand même »**.
4. Choisissez le dossier d'installation, puis laissez l'assistant terminer.

L'application apparaît ensuite dans le menu Démarrer et sur le bureau.

---

## L'avertissement Windows SmartScreen

Au premier lancement, Windows affiche :

> **Windows a protégé votre ordinateur**
> Microsoft Defender SmartScreen a empêché le démarrage d'une application non reconnue.

**Ce n'est pas un virus, et ce n'est pas une erreur.**

### Pourquoi cet écran apparaît

SmartScreen vérifie deux choses : l'application est-elle **signée** par un certificat
d'éditeur, et est-elle **déjà connue** de Microsoft (installée par de nombreuses
personnes) ?

VindIA est une application privée, distribuée à quelques personnes, et son installeur
n'est pas signé par un certificat commercial — un tel certificat coûte plusieurs
centaines d'euros par an. SmartScreen ne la « connaît » donc pas, et prévient par
précaution. Exactement le même écran s'affiche pour n'importe quel logiciel récent d'un
petit éditeur.

### Comment passer l'écran

Cliquez sur **« Informations complémentaires »**, puis sur le bouton
**« Exécuter quand même »** qui apparaît alors. C'est à faire **une seule fois**, à
l'installation.

### Comment vérifier que le fichier est authentique

- Téléchargez-le uniquement depuis la page **Releases de ce dépôt**, jamais depuis un
  lien reçu par message ou par e-mail.
- L'installeur est construit automatiquement par GitHub à partir du code source public
  de ce dépôt : personne n'y ajoute quoi que ce soit manuellement.

---

## Ce que l'application apporte

| | |
|---|---|
| **Fenêtre dédiée** | VindIA dans sa propre application, plus dans un onglet perdu au milieu des autres |
| **Dossiers de travail** | Menu *Fichier → Ajouter un dossier de travail* : vous désignez les dossiers auxquels VindIA a accès |
| **Dictée vocale** | Le micro est autorisé pour l'application |
| **Démarrage direct** | Icône sur le bureau et dans le menu Démarrer |

---

## Confidentialité et sécurité

**VindIA ne voit que les dossiers que vous lui désignez.** Aucun autre emplacement de
votre ordinateur n'est lisible — ni vos documents personnels, ni votre bureau, ni quoi
que ce soit d'autre. Vous pouvez retirer un dossier à tout moment.

Techniquement : la page web affichée n'a aucun accès direct au disque. Elle passe par un
pont volontairement restreint, qui vérifie à chaque lecture ou écriture que le fichier
demandé se trouve bien dans un dossier autorisé, et refuse toute tentative de sortir de
ce dossier.

**Où vont les fichiers ?** Le moteur de VindIA (l'intelligence artificielle) fonctionne
sur le serveur, pas sur votre ordinateur. Pour qu'elle puisse lire un document, son
contenu est transmis au serveur, en liaison chiffrée. Seuls les fichiers des dossiers
que vous avez choisis sont concernés.

---

## Transparence sur l'intelligence artificielle

VindIA est un assistant fondé sur l'intelligence artificielle : vous échangez avec une
IA, pas avec une personne. Ses réponses peuvent comporter des erreurs — vérifiez les
informations importantes.

Les documents qu'elle produit portent une mention indiquant qu'ils ont été générés par
une IA, ainsi que des métadonnées correspondantes, conformément au règlement européen
sur l'intelligence artificielle (AI Act, article 50).

---

## En cas de problème

**« VindIA n'est pas joignable »** — l'application n'arrive pas à contacter le serveur.
Vérifiez votre connexion internet, puis relancez-la.

**Le micro ne fonctionne pas** — vérifiez les autorisations du micro dans les paramètres
de confidentialité de Windows, pour l'application VindIA.

**L'application ne se lance pas** — désinstallez-la depuis *Paramètres → Applications*,
puis réinstallez la dernière version depuis la page Releases.

---

## Versions

Chaque version publiée figure sur la page [Releases](../../releases), avec la date et
la liste des changements. Pour mettre à jour, téléchargez et installez simplement la
version la plus récente : elle remplace la précédente et conserve vos réglages.
