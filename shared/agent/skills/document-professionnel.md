# Document professionnel
> Produire un Word, PDF, tableur ou diaporama propre du premier coup.

Le document doit être livrable tel quel. Si l'utilisateur doit reprendre la mise en
forme, le travail n'est pas fait.

## Avant d'écrire

Répondre à trois questions, sinon le document sera générique :
- Qui va le lire ? (un client, un chef de projet, un technicien, soi-même)
- Que doit-il faire après l'avoir lu ?
- Quel niveau de détail il supporte ?

## Conventions de génération

- Titres avec `#`, sous-titres avec `##`. Ils sont colorés automatiquement à la charte.
- Gras avec `**texte**` pour les termes qui doivent ressortir à la lecture rapide.
- Tableau markdown dès qu'il y a comparaison, planning, liste avec attributs :
  une ligne `| col | col |` suivie de `|---|---|`. Un tableau vaut dix paragraphes.
- Tableur `.xlsx` : format CSV, première ligne = en-têtes, une donnée par cellule
  (jamais « 3 jours (à confirmer) » dans une colonne de durée).
- Diaporama `.pptx` : diapositives séparées par `---`, première ligne = titre, puis
  puces. Six puces maximum par diapositive, une idée par puce.

## Qualité

- Pas de section vide ni de « à compléter » : soit l'information existe, soit la
  section n'existe pas.
- Pas de superlatifs, pas d'auto-promotion. Les faits, les chiffres, les dates.
- Nombres cohérents dans tout le document ; si une donnée est estimée, l'écrire.
- Nom de fichier explicite et daté quand c'est un livrable récurrent :
  `compte-rendu-2026-03-14.docx`, pas `document.docx`.

## Ce qu'il ne faut jamais faire

Répondre « voici le texte, copie-le dans Word ». Le fichier se génère directement.
