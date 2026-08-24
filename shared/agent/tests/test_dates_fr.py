"""Comprendre une date dite à voix haute — sans réseau, sans modèle.

Une date mal comprise sur un agenda d'aide à la mémoire, c'est un rendez-vous manqué
ou un traitement décalé. Ces tests fixent une horloge et vérifient chaque tournure.
"""

import unittest
from datetime import datetime

from shared.agent.dates_fr import analyse, detecte_recurrence

# Lundi 24 août 2026, 12 h 00.
MAINTENANT = datetime(2026, 8, 24, 12, 0, 0)


class RelatifTest(unittest.TestCase):
    def test_demain(self):
        d = analyse("demain à 14h", MAINTENANT)
        self.assertEqual((d.day, d.hour, d.minute), (25, 14, 0))

    def test_apres_demain(self):
        self.assertEqual(analyse("après-demain", MAINTENANT).day, 26)

    def test_dans_trois_jours_en_lettres(self):
        self.assertEqual(analyse("dans trois jours", MAINTENANT).day, 27)

    def test_dans_deux_semaines(self):
        self.assertEqual(analyse("dans 2 semaines", MAINTENANT).day, 7)

    def test_dans_une_heure(self):
        d = analyse("dans une heure", MAINTENANT)
        self.assertEqual((d.day, d.hour), (24, 13))

    def test_dans_trente_minutes(self):
        self.assertEqual(analyse("dans 30 minutes", MAINTENANT).hour, 12)
        self.assertEqual(analyse("dans 30 minutes", MAINTENANT).minute, 30)


class JourDeSemaineTest(unittest.TestCase):
    def test_mercredi_prend_le_prochain(self):
        # Lundi + mercredi = surlendemain.
        self.assertEqual(analyse("mercredi", MAINTENANT).day, 26)

    def test_le_jour_meme_renvoie_la_semaine_suivante(self):
        # Dire « lundi » un lundi désigne le lundi suivant, pas aujourd'hui.
        self.assertEqual(analyse("lundi", MAINTENANT).day, 31)

    def test_avec_un_moment_de_journee(self):
        d = analyse("mardi matin", MAINTENANT)
        self.assertEqual((d.day, d.hour), (25, 8))


class HeureTest(unittest.TestCase):
    def test_formes_d_heure(self):
        for texte, attendu in (("demain 14h", 14), ("demain à 14 h 30", 14),
                               ("demain à 9 heures", 9), ("demain 8h00", 8)):
            with self.subTest(texte=texte):
                self.assertEqual(analyse(texte, MAINTENANT).hour, attendu)

    def test_les_minutes_sont_lues(self):
        self.assertEqual(analyse("demain à 14 h 30", MAINTENANT).minute, 30)

    def test_moments_de_la_journee(self):
        for texte, h in (("demain matin", 8), ("demain midi", 12),
                         ("demain après-midi", 14), ("demain soir", 19)):
            with self.subTest(texte=texte):
                self.assertEqual(analyse(texte, MAINTENANT).hour, h)

    def test_heure_seule_deja_passee_bascule_a_demain(self):
        # Il est midi ; « à 9h » ne peut pas être ce matin.
        d = analyse("à 9h", MAINTENANT)
        self.assertEqual((d.day, d.hour), (25, 9))

    def test_heure_seule_encore_a_venir_reste_aujourd_hui(self):
        d = analyse("à 18h", MAINTENANT)
        self.assertEqual((d.day, d.hour), (24, 18))


class DateExpliciteTest(unittest.TestCase):
    def test_jour_et_mois_en_lettres(self):
        d = analyse("le 3 septembre à 10h", MAINTENANT)
        self.assertEqual((d.day, d.month, d.hour), (3, 9, 10))

    def test_mois_deja_passe_bascule_a_l_annee_suivante(self):
        # Dire « 3 janvier » en août désigne janvier prochain.
        self.assertEqual(analyse("le 3 janvier", MAINTENANT).year, 2027)

    def test_format_chiffre(self):
        d = analyse("le 03/09 à 14h", MAINTENANT)
        self.assertEqual((d.day, d.month, d.hour), (3, 9, 14))

    def test_date_impossible_rend_none(self):
        self.assertIsNone(analyse("le 32/13", MAINTENANT))


class NonComprisTest(unittest.TestCase):
    """Ne PAS deviner : None doit conduire à demander une précision."""

    def test_phrase_sans_date(self):
        self.assertIsNone(analyse("rappelle-moi de prendre mon traitement", MAINTENANT))

    def test_texte_vide(self):
        self.assertIsNone(analyse("", MAINTENANT))

    def test_bientot_n_est_pas_une_date(self):
        self.assertIsNone(analyse("bientôt", MAINTENANT))


class RecurrenceTest(unittest.TestCase):
    def test_quotidien(self):
        for texte in ("tous les matins à 8h", "chaque jour", "tous les jours"):
            with self.subTest(texte=texte):
                self.assertEqual(detecte_recurrence(texte), "quotidien")

    def test_hebdomadaire(self):
        self.assertEqual(detecte_recurrence("tous les lundis"), "hebdomadaire")
        self.assertEqual(detecte_recurrence("chaque semaine"), "hebdomadaire")

    def test_mensuel(self):
        self.assertEqual(detecte_recurrence("tous les mois"), "mensuel")

    def test_ponctuel(self):
        self.assertEqual(detecte_recurrence("demain à 14h"), "aucune")


if __name__ == "__main__":
    unittest.main()
