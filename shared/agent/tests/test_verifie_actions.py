"""Le contrôle qui empêche VindIA d'affirmer une action qu'elle n'a pas faite.

Cas réels de la journée du 24/08/2026 : « j'ai créé le document, tu le trouveras dans
ton dossier » — aucun fichier nulle part. C'est ce qui a fait perdre confiance à
l'utilisateur, plus encore que les bugs eux-mêmes.

Stdlib pure : ces tests tournent dans la CI.
"""

import unittest

from shared.agent.verifie_actions import (
    affirme_une_livraison,
    controle,
    preuve_de_livraison,
)

ECRIT = ["synced_write_file"]
LU = ["folder_list_files", "web_search"]


class PreuveTest(unittest.TestCase):
    def test_outil_d_ecriture_appele_vaut_preuve(self):
        self.assertTrue(preuve_de_livraison(ECRIT, "voilà"))

    def test_marqueur_fichier_vaut_preuve(self):
        self.assertTrue(preuve_de_livraison([], "[[FICHIER:note.odt]]contenu[[/FICHIER]]"))

    def test_lire_ou_chercher_ne_vaut_pas_preuve(self):
        self.assertFalse(preuve_de_livraison(LU, "voilà"))

    def test_aucun_outil_ne_vaut_pas_preuve(self):
        self.assertFalse(preuve_de_livraison([], "voilà"))


class DetectionTest(unittest.TestCase):
    def test_repere_les_affirmations_courantes(self):
        for phrase in (
            "J'ai créé le document dans ton dossier.",
            "J'ai bien enregistré le fichier.",
            "Le compte-rendu a été généré.",
            "Tu le trouveras dans ton dossier synchronisé.",
            "J'ai déposé la présentation sur ton ordinateur.",
            "Le classeur est disponible.",
            "J'ai rédigé le rapport et je l'ai enregistré.",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(affirme_une_livraison(phrase), phrase)

    def test_le_futur_et_le_conditionnel_n_affirment_rien(self):
        # Proposer n'est pas mentir : ces phrases doivent passer intactes.
        for phrase in (
            "Je vais créer le document si tu veux.",
            "Je peux te préparer un compte-rendu.",
            "Veux-tu que je génère un fichier ?",
            "Le document sera créé dès que tu confirmes le format.",
        ):
            with self.subTest(phrase=phrase):
                self.assertFalse(affirme_une_livraison(phrase), phrase)

    def test_une_reponse_ordinaire_n_est_pas_touchee(self):
        self.assertFalse(affirme_une_livraison("La météo est bonne aujourd'hui."))


class ControleTest(unittest.TestCase):
    def test_mensonge_retire_quand_aucun_fichier_n_existe(self):
        texte = "J'ai créé le document et je l'ai déposé dans ton dossier."
        sortie, corrige = controle(texte, [])
        self.assertTrue(corrige)
        self.assertNotIn("créé le document", sortie)
        self.assertIn("Je n'ai pas créé de fichier", sortie)

    def test_verite_laissee_intacte_quand_l_outil_a_ecrit(self):
        texte = "J'ai créé le document dans ton dossier."
        sortie, corrige = controle(texte, ECRIT)
        self.assertFalse(corrige)
        self.assertEqual(sortie, texte)

    def test_marqueur_present_donc_reponse_intacte(self):
        texte = "Voici ton document. [[FICHIER:note.odt]]# Titre[[/FICHIER]]"
        sortie, corrige = controle(texte, [])
        self.assertFalse(corrige)
        self.assertEqual(sortie, texte)

    def test_le_contenu_utile_est_conserve(self):
        # On retire la phrase fausse, pas toute la réponse : le reste a de la valeur.
        texte = ("Voici le plan en trois parties. J'ai enregistré le fichier "
                 "dans ton dossier. Dis-moi si tu veux le modifier.")
        sortie, corrige = controle(texte, [])
        self.assertTrue(corrige)
        self.assertIn("plan en trois parties", sortie)
        self.assertIn("Dis-moi si tu veux", sortie)
        self.assertNotIn("enregistré le fichier", sortie)

    def test_reponse_sans_rapport_intacte(self):
        texte = "Il fera beau demain à Bordeaux."
        self.assertEqual(controle(texte, []), (texte, False))

    def test_texte_vide(self):
        self.assertEqual(controle("", []), ("", False))


if __name__ == "__main__":
    unittest.main()
