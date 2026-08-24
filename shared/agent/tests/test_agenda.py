"""L'agenda de VindIA — sur SQLite, sans réseau ni MariaDB.

Cet agenda existe pour une personne dont la mémoire flanche. Une erreur ici ne se
rattrape pas par une relance : si un traitement manqué n'apparaît pas, personne ne le
saura. D'où le nombre de cas couverts, et l'isolation testée à chaque fois.
"""

import sqlite3
import unittest
from datetime import datetime, timedelta

from shared.agent.agenda import Agenda

ALICE = "00000000-0000-0000-0000-00000000a11c"
BOB = "00000000-0000-0000-0000-00000000b0b0"
MIDI = datetime(2026, 8, 24, 12, 0, 0)


def _agenda():
    a = Agenda(sqlite3.connect(":memory:"))
    a.creer_tables()
    return a


class BaseTest(unittest.TestCase):
    def test_creer_tables_est_idempotent(self):
        a = _agenda()
        a.creer_tables()          # deux fois de suite : ne doit pas lever
        self.assertEqual(a.du_jour(ALICE, MIDI), [])

    def test_ajouter_et_relire(self):
        a = _agenda()
        a.ajouter(ALICE, "Cardiologue", MIDI, categorie="rendez-vous")
        jour = a.du_jour(ALICE, MIDI)
        self.assertEqual(len(jour), 1)
        self.assertEqual(jour[0]["titre"], "Cardiologue")

    def test_titre_vide_refuse(self):
        with self.assertRaises(ValueError):
            _agenda().ajouter(ALICE, "   ", MIDI)

    def test_categorie_inconnue_devient_autre(self):
        a = _agenda()
        a.ajouter(ALICE, "Truc", MIDI, categorie="fantaisie")
        self.assertEqual(a.du_jour(ALICE, MIDI)[0]["categorie"], "autre")

    def test_les_evenements_sont_ordonnes_par_heure(self):
        a = _agenda()
        a.ajouter(ALICE, "Après-midi", MIDI.replace(hour=16))
        a.ajouter(ALICE, "Matin", MIDI.replace(hour=8))
        self.assertEqual([e["titre"] for e in a.du_jour(ALICE, MIDI)],
                         ["Matin", "Après-midi"])


class IsolationTest(unittest.TestCase):
    """L'agenda d'une personne ne doit JAMAIS apparaître chez une autre."""

    def test_chacun_ne_voit_que_ses_evenements(self):
        a = _agenda()
        a.ajouter(ALICE, "Cardiologue", MIDI)
        a.ajouter(BOB, "Kiné", MIDI)
        self.assertEqual([e["titre"] for e in a.du_jour(ALICE, MIDI)], ["Cardiologue"])
        self.assertEqual([e["titre"] for e in a.du_jour(BOB, MIDI)], ["Kiné"])

    def test_impossible_de_marquer_fait_l_evenement_d_un_autre(self):
        a = _agenda()
        eid = a.ajouter(ALICE, "Traitement", MIDI, categorie="traitement")
        self.assertFalse(a.marquer_fait(BOB, eid, MIDI))
        self.assertIsNone(a.du_jour(ALICE, MIDI)[0]["fait_le"])

    def test_impossible_d_annuler_l_evenement_d_un_autre(self):
        a = _agenda()
        eid = a.ajouter(ALICE, "Rendez-vous", MIDI)
        self.assertFalse(a.annuler(BOB, eid))
        self.assertEqual(len(a.du_jour(ALICE, MIDI)), 1)


class FilDArianeTest(unittest.TestCase):
    def test_marquer_fait_puis_le_retrouver(self):
        a = _agenda()
        eid = a.ajouter(ALICE, "Comprimé du matin", MIDI.replace(hour=8),
                        categorie="traitement")
        self.assertTrue(a.marquer_fait(ALICE, eid, MIDI.replace(hour=8, minute=5)))
        self.assertIsNotNone(a.du_jour(ALICE, MIDI)[0]["fait_le"])

    def test_le_passe_recent_est_consultable(self):
        a = _agenda()
        a.ajouter(ALICE, "Hier", MIDI - timedelta(days=1))
        self.assertEqual([e["titre"] for e in a.passe(ALICE, 2, MIDI)], ["Hier"])

    def test_a_venir_ne_remonte_pas_le_passe(self):
        a = _agenda()
        a.ajouter(ALICE, "Hier", MIDI - timedelta(days=1))
        a.ajouter(ALICE, "Demain", MIDI + timedelta(days=1))
        self.assertEqual([e["titre"] for e in a.a_venir(ALICE, 7, MIDI)], ["Demain"])

    def test_annule_disparait_des_listes_mais_pas_de_la_base(self):
        # On n'efface pas : l'historique d'une personne ne se réécrit pas.
        a = _agenda()
        eid = a.ajouter(ALICE, "Annulé", MIDI)
        self.assertTrue(a.annuler(ALICE, eid))
        self.assertEqual(a.du_jour(ALICE, MIDI), [])

    def test_recherche_par_mot(self):
        a = _agenda()
        a.ajouter(ALICE, "Rendez-vous cardiologue", MIDI)
        a.ajouter(ALICE, "Courses", MIDI)
        self.assertEqual([e["titre"] for e in a.chercher(ALICE, "cardio")],
                         ["Rendez-vous cardiologue"])


class RetardTest(unittest.TestCase):
    """« Qu'est-ce qui a été oublié ? » — la question qui compte pour un traitement."""

    def test_un_traitement_non_pris_remonte(self):
        a = _agenda()
        a.ajouter(ALICE, "Comprimé du matin", MIDI.replace(hour=8),
                  categorie="traitement")
        retard = a.en_retard(ALICE, 30, MIDI)
        self.assertEqual([e["titre"] for e in retard], ["Comprimé du matin"])

    def test_un_traitement_pris_ne_remonte_pas(self):
        a = _agenda()
        eid = a.ajouter(ALICE, "Comprimé", MIDI.replace(hour=8), categorie="traitement")
        a.marquer_fait(ALICE, eid, MIDI.replace(hour=8, minute=10))
        self.assertEqual(a.en_retard(ALICE, 30, MIDI), [])

    def test_ce_qui_vient_de_passer_laisse_un_delai(self):
        # Prévu il y a 10 minutes : on ne harcèle pas quelqu'un qui est peut-être
        # en train de le faire.
        a = _agenda()
        a.ajouter(ALICE, "Tout juste", MIDI - timedelta(minutes=10))
        self.assertEqual(a.en_retard(ALICE, 30, MIDI), [])

    def test_on_ne_remonte_pas_les_oublis_trop_anciens(self):
        # Rappeler un comprimé d'il y a trois jours n'aide personne et inquiète.
        a = _agenda()
        a.ajouter(ALICE, "Vieux", MIDI - timedelta(days=3))
        self.assertEqual(a.en_retard(ALICE, 30, MIDI), [])

    def test_un_evenement_annule_n_est_jamais_en_retard(self):
        a = _agenda()
        eid = a.ajouter(ALICE, "Annulé", MIDI.replace(hour=8))
        a.annuler(ALICE, eid)
        self.assertEqual(a.en_retard(ALICE, 30, MIDI), [])


if __name__ == "__main__":
    unittest.main()
