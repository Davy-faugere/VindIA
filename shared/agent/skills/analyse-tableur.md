# Analyse d'un tableur
> Lire un Excel ou un CSV et en tirer quelque chose d'utile.

## Avant d'analyser

Regarder la structure : quelles colonnes, quelles unités, combien de lignes, quelle
période. Une colonne « Montant » sans devise ni précision HT/TTC ne s'interprète pas —
le demander plutôt que supposer.

## Vérifications qui évitent les conclusions fausses

- **Cellules vides** : une moyenne sur une colonne trouée est fausse. Compter les
  vides et le signaler.
- **Doublons** : vérifier avant de sommer.
- **Formats mélangés** : dates en texte, nombres avec espaces ou virgules, « 1 234,50 »
  lu comme du texte. C'est la première cause d'erreur de total.
- **Lignes de total déjà présentes** : les inclure dans une somme double le résultat.
- **Filtres et lignes masquées** : ce qui est affiché n'est pas toujours tout.

## Restitution

Répondre à la question posée d'abord, en une phrase avec le chiffre. Les détails
ensuite, seulement s'ils changent la lecture.

Toujours donner : le chiffre, sur quel périmètre, et sur quelle période.

Si une donnée manque pour répondre proprement, le dire au lieu de produire un
résultat qui a l'air solide.

## Livrable

Pour une synthèse : un .xlsx avec les données retraitées, ou un .docx avec un tableau
de résultats. Ne pas rendre une analyse chiffrée en texte au fil de l'eau.
