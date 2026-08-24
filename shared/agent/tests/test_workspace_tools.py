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


class EcritureRetireeTest(unittest.TestCase):
    """L'écriture dans les dossiers a été retirée le 24/08/2026.

    Elle déposait le fichier sous `vindia-data/workspaces/…`, que rien ne synchronise :
    le fichier existait sur le serveur mais n'atteignait jamais l'ordinateur. VindIA
    annonçait donc un document introuvable pour son destinataire — cinq livrables ont
    été perdus ainsi entre le 16 et le 23/08/2026.

    Ce test verrouille la décision : si quelqu'un remet un outil d'écriture ici sans
    régler la synchronisation, il rouvre exactement le même piège.
    """

    def test_seuls_les_outils_de_consultation_sont_fournis(self):
        with tempfile.TemporaryDirectory() as tmp:
            noms = [t.spec.name for t in _tools(tmp)]
            self.assertEqual(noms, ["folder_list_files", "folder_read_file"])

    def test_aucun_outil_d_ecriture_sur_les_dossiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            for outil in _tools(tmp):
                self.assertNotIn("write", outil.spec.name)


if __name__ == "__main__":
    unittest.main()
