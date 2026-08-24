"""Les outils d'agenda tels que VindIA les appelle — offline, horloge figée.

Ces outils sont ce que la personne touche vraiment : elle parle, VindIA appelle. Une
date mal placée ou un traitement marqué fait à tort ne se rattrapent pas.
"""

import asyncio
import sqlite3
import unittest
from datetime import datetime

from shared.agent.agenda import Agenda
from shared.agent.agenda_tools import build_agenda_tools, dit_la_date

ALICE = "00000000-0000-0000-0000-00000000a11c"
BOB = "00000000-0000-0000-0000-00000000b0b0"
MAINTENANT = datetime(2026, 8, 24, 12, 0, 0)          # lundi 24 août, midi


def _outils(member_id=ALICE, agenda=None):
    a = agenda or Agenda(sqlite3.connect(":memory:"))
    if agenda is None:
        a.creer_tables()
    outils = {t.spec.name: t for t in build_agenda_tools(a, member_id, lambda: MAINTENANT)}
    return a, outils


def _run(outil, **args):
    return asyncio.run(outil.run(args))


class AjoutTest(unittest.TestCase):
    def test_ajout_avec_une_date_relative(self):
        a, o = _outils()
        r = _run(o["agenda_ajouter"], titre="Cardiologue", quand="demain à 14h")
        self.assertIn("mardi 25 août", r)
        self.assertIn("14 h", r)
        self.assertEqual(len(a.a_venir(ALICE, 7, MAINTENANT)), 1)

    def test_recurrence_reconnue_et_annoncee(self):
        a, o = _outils()
        r = _run(o["agenda_ajouter"], titre="Comprimé", quand="tous les matins à 8h",
                 categorie="traitement")
        self.assertIn("quotidien", r)

    def test_date_incomprise_ne_place_rien(self):
        # Le cœur du garde-fou : ne JAMAIS inventer une date.
        a, o = _outils()
        r = _run(o["agenda_ajouter"], titre="Rendez-vous", quand="bientôt")
        self.assertIn("pas compris", r)
        self.assertEqual(a.a_venir(ALICE, 60, MAINTENANT), [])

    def test_titre_vide_refuse(self):
        a, o = _outils()
        self.assertIn("Erreur", _run(o["agenda_ajouter"], titre="", quand="demain"))
        self.assertEqual(a.a_venir(ALICE, 60, MAINTENANT), [])

    def test_categorie_inconnue_ne_bloque_pas(self):
        a, o = _outils()
        r = _run(o["agenda_ajouter"], titre="Truc", quand="demain", categorie="n'importe quoi")
        self.assertIn("Enregistré", r)


class LectureTest(unittest.TestCase):
    def test_journee_vide_le_dit(self):
        _, o = _outils()
        self.assertIn("Rien de prévu", _run(o["agenda_journee"]))

    def test_journee_remplie(self):
        a, o = _outils()
        _run(o["agenda_ajouter"], titre="Kiné", quand="à 18h")
        self.assertIn("Kiné", _run(o["agenda_journee"]))

    def test_recherche_par_mot(self):
        a, o = _outils()
        _run(o["agenda_ajouter"], titre="Rendez-vous cardiologue", quand="demain à 10h")
        self.assertIn("cardiologue", _run(o["agenda_chercher"], mot="cardio"))

    def test_recherche_infructueuse(self):
        _, o = _outils()
        self.assertIn("Je ne trouve rien", _run(o["agenda_chercher"], mot="dentiste"))


class OublisTest(unittest.TestCase):
    def test_un_traitement_non_pris_remonte(self):
        a, o = _outils()
        a.ajouter(ALICE, "Comprimé du matin", MAINTENANT.replace(hour=8),
                  categorie="traitement")
        self.assertIn("Comprimé du matin", _run(o["agenda_oublis"]))

    def test_rien_a_signaler_est_rassurant(self):
        _, o = _outils()
        self.assertIn("tout est à jour", _run(o["agenda_oublis"]))

    def test_marquer_fait_par_le_titre(self):
        a, o = _outils()
        a.ajouter(ALICE, "Comprimé du matin", MAINTENANT.replace(hour=8),
                  categorie="traitement")
        r = _run(o["agenda_marquer_fait"], titre="mon comprimé")
        self.assertIn("est fait", r)
        self.assertIn("tout est à jour", _run(o["agenda_oublis"]))

    def test_marquer_fait_ce_qui_n_existe_pas(self):
        _, o = _outils()
        self.assertIn("Je ne trouve pas", _run(o["agenda_marquer_fait"], titre="la lune"))

    def test_annuler_par_le_titre(self):
        a, o = _outils()
        _run(o["agenda_ajouter"], titre="Rendez-vous dentiste", quand="demain à 10h")
        self.assertIn("Annulé", _run(o["agenda_annuler"], titre="dentiste"))
        self.assertEqual(a.a_venir(ALICE, 7, MAINTENANT), [])


class IsolationTest(unittest.TestCase):
    """Les outils sont figés sur une personne : le modèle ne fournit aucun identifiant."""

    def test_chacun_ne_voit_que_son_agenda(self):
        base = Agenda(sqlite3.connect(":memory:"))
        base.creer_tables()
        _, oa = _outils(ALICE, base)
        _, ob = _outils(BOB, base)
        _run(oa["agenda_ajouter"], titre="Cardiologue", quand="demain à 10h")
        self.assertIn("Cardiologue", _run(oa["agenda_a_venir"]))
        self.assertIn("Rien de prévu", _run(ob["agenda_a_venir"]))

    def test_impossible_de_marquer_fait_chez_un_autre(self):
        base = Agenda(sqlite3.connect(":memory:"))
        base.creer_tables()
        base.ajouter(ALICE, "Comprimé", MAINTENANT.replace(hour=8), categorie="traitement")
        _, ob = _outils(BOB, base)
        self.assertIn("Je ne trouve pas", _run(ob["agenda_marquer_fait"], titre="Comprimé"))
        self.assertIsNone(base.du_jour(ALICE, MAINTENANT)[0]["fait_le"])


class FormulationTest(unittest.TestCase):
    """Les réponses sont lues à voix haute : elles doivent se dire, pas se lire."""

    def test_date_dite_en_toutes_lettres(self):
        self.assertEqual(dit_la_date(datetime(2026, 8, 25, 14, 30)),
                         "mardi 25 août à 14 h 30")

    def test_heure_ronde_sans_minutes(self):
        self.assertEqual(dit_la_date(datetime(2026, 8, 25, 14, 0)),
                         "mardi 25 août à 14 h")



class RechercheOraleTest(unittest.TestCase):
    """À l'oral, personne ne répète le titre exact.

    Constaté en essai réel sur MariaDB : « mon comprimé » ne retrouvait pas
    « Comprimé du matin », parce que la recherche portait sur la phrase entière. Sur un
    agenda d'aide à la mémoire, répondre « je ne trouve rien » alors que l'événement
    existe est exactement la réponse à ne pas donner.
    """

    def test_phrase_complete_retrouve_l_evenement(self):
        a, o = _outils()
        _run(o["agenda_ajouter"], titre="Rendez-vous cardiologue", quand="demain à 10h")
        r = _run(o["agenda_chercher"], mot="mon rendez-vous chez le cardiologue")
        self.assertIn("cardiologue", r)

    def test_marquer_fait_avec_une_phrase(self):
        a, o = _outils()
        a.ajouter(ALICE, "Comprimé du matin", MAINTENANT.replace(hour=8),
                  categorie="traitement")
        self.assertIn("est fait",
                      _run(o["agenda_marquer_fait"], titre="j'ai pris mon comprimé"))

    def test_annuler_avec_une_phrase(self):
        a, o = _outils()
        _run(o["agenda_ajouter"], titre="Rendez-vous dentiste", quand="demain à 10h")
        self.assertIn("Annulé", _run(o["agenda_annuler"], titre="mon rendez-vous dentiste"))

    def test_les_mots_vides_seuls_ne_ramenent_rien(self):
        # « le », « mon », « des » ne désignent rien : ne pas ramener tout l'agenda.
        a, o = _outils()
        _run(o["agenda_ajouter"], titre="Cardiologue", quand="demain à 10h")
        self.assertIn("Je ne trouve rien", _run(o["agenda_chercher"], mot="le mon des"))

if __name__ == "__main__":
    unittest.main()
