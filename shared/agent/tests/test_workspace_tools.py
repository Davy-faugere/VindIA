"""Tests des outils « dossiers de l'ordinateur » — hors ligne, tmpdir.

Ce qui compte ici : un membre ne voit jamais le dossier d'un autre, et un projet
qui rattache des dossiers RESTREINT réellement la vue (sinon « associer un dossier
au projet » ne servirait à rien).
"""

import asyncio
import tempfile
import unittest

from shared.agent.sync_store import CREATIONS, SyncStore
from shared.agent.workspace_tools import build_workspace_tools

ALICE = "00000001-0001-0001-0002-000000000001"
BOB = "00000001-0001-0001-0003-000000000001"


def _run(tool, **args):
    return asyncio.run(tool.run(args))


def _tools(tmp, member=ALICE, allowed=None):
    return build_workspace_tools(SyncStore(tmp), member, allowed)


class ListAndReadTest(unittest.TestCase):
    def test_lists_folders_when_several_and_none_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "Projet Alpha", "Projet Alpha")
            s.register_workspace(ALICE, "Photos", "Photos")
            out = _run(_tools(tmp)[0])
            self.assertIn("Projet Alpha", out)
            self.assertIn("Photos", out)

    def test_single_folder_needs_no_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "Unique", "Unique")
            s.put(ALICE, "Unique", "note.md", b"bonjour")
            self.assertIn("note.md", _run(_tools(tmp)[0]))
            self.assertEqual(_run(_tools(tmp)[1], filename="note.md"), "bonjour")

    def test_reads_file_in_named_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "Projet Alpha", "Projet Alpha")
            s.register_workspace(ALICE, "Autre", "Autre")
            s.put(ALICE, "Projet Alpha", "sous/plan.md", b"le plan")
            out = _run(_tools(tmp)[1], folder="Projet Alpha", filename="sous/plan.md")
            self.assertEqual(out, "le plan")

    def test_unknown_folder_is_refused_with_help(self):
        with tempfile.TemporaryDirectory() as tmp:
            SyncStore(tmp).register_workspace(ALICE, "Projet Alpha", "Projet Alpha")
            out = _run(_tools(tmp)[1], folder="Comptabilité", filename="x.md")
            self.assertIn("introuvable", out)
            self.assertIn("Projet Alpha", out)      # dit ce qui est disponible

    def test_no_folder_at_all_explains_what_to_do(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = _run(_tools(tmp)[0])
            self.assertIn("application VindIA", out)


class IsolationTest(unittest.TestCase):
    def test_other_member_folder_is_invisible(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "Prive", "Prive")
            s.put(ALICE, "Prive", "secret.md", b"donnees alice")
            # Bob demande explicitement le dossier d'Alice, par son nom exact.
            out = _run(_tools(tmp, member=BOB)[1], folder="Prive", filename="secret.md")
            self.assertNotIn("donnees alice", out)
            self.assertIn("Aucun dossier", out)

    def test_project_scope_hides_unlinked_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "Projet Alpha", "Projet Alpha")
            s.register_workspace(ALICE, "Comptabilite", "Comptabilite")
            s.put(ALICE, "Comptabilite", "bilan.md", b"chiffres")
            # Projet actif rattaché au seul « Projet Alpha » : la compta sort du champ.
            read = _tools(tmp, allowed=["projet-alpha"])[1]
            out = _run(read, folder="Comptabilite", filename="bilan.md")
            self.assertNotIn("chiffres", out)
            self.assertIn("introuvable", out)


class EcritureTest(unittest.TestCase):
    """L'écriture est LE chemin vers l'ordinateur de la personne.

    Retirée par erreur le 24/08/2026 : le constat de départ était juste (des fichiers
    restaient sur le serveur) mais la conclusion fausse. Ce n'était pas un cul-de-sac,
    c'était le chemin que l'application de bureau descend ensuite sur le disque de la
    personne — sans Syncthing ni service tiers. Rétablie le jour même.

    Ces tests verrouillent sa présence : la retirer casse la livraison des documents.
    """

    def test_l_outil_d_ecriture_est_bien_fourni(self):
        with tempfile.TemporaryDirectory() as tmp:
            noms = [t.spec.name for t in _tools(tmp)]
            self.assertIn("folder_write_file", noms)

    def test_ecrit_dans_le_sous_dossier_des_creations(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "Unique", "Unique")
            out = _run(_tools(tmp)[2], filename="note.md", content="Contenu du compte-rendu")
            self.assertIn(CREATIONS, out)
            written = s.get(ALICE, "Unique", f"{CREATIONS}/note.md").decode("utf-8")
            self.assertIn("Contenu du compte-rendu", written)

    def test_fichier_texte_porte_la_mention_ia(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "Unique", "Unique")
            _run(_tools(tmp)[2], filename="note.md", content="Texte")
            from shared.agent.officegen import AI_NOTICE

            written = s.get(ALICE, "Unique", f"{CREATIONS}/note.md").decode("utf-8")
            self.assertTrue(written.startswith(AI_NOTICE))   # transparence IA (art. 50)

    def test_les_formats_bureautiques_sont_construits(self):
        # Y COMPRIS .odt et .ods : une liste figée ici les avait laissés passer en
        # markdown brut sous un nom de fichier bureautique.
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "Unique", "Unique")
            for nom, entete in (("r.docx", b"PK"), ("r.pdf", b"%PDF"), ("r.odt", b"PK")):
                with self.subTest(nom=nom):
                    _run(_tools(tmp)[2], filename=nom, content="# Titre\n\nDu texte.")
                    data = s.get(ALICE, "Unique", f"{CREATIONS}/{nom}")
                    self.assertTrue(data.startswith(entete), nom)

    def test_contenu_vide_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            SyncStore(tmp).register_workspace(ALICE, "Unique", "Unique")
            self.assertIn("vide", _run(_tools(tmp)[2], filename="x.md", content="   "))


if __name__ == "__main__":
    unittest.main()
