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


class WriteTest(unittest.TestCase):
    def test_writes_into_creations_subfolder(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "Unique", "Unique")
            out = _run(_tools(tmp)[2], filename="note.md", content="Contenu du compte-rendu")
            self.assertIn(CREATIONS, out)
            written = s.get(ALICE, "Unique", f"{CREATIONS}/note.md").decode("utf-8")
            self.assertIn("Contenu du compte-rendu", written)

    def test_text_file_carries_ai_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "Unique", "Unique")
            _run(_tools(tmp)[2], filename="note.md", content="Texte")
            from shared.agent.officegen import AI_NOTICE

            written = s.get(ALICE, "Unique", f"{CREATIONS}/note.md").decode("utf-8")
            self.assertTrue(written.startswith(AI_NOTICE))   # transparence IA (art. 50)

    def test_office_extension_uses_binary_builder(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "Unique", "Unique")
            seen = {}

            def fake_builder(name, content, base_dir=None):
                seen.update(name=name, base_dir=base_dir)
                return b"BINAIRE", "application/x-test"

            from shared.agent.workspace_tools import FolderWriteTool

            tool = FolderWriteTool(SyncStore(tmp), ALICE, office_builder=fake_builder)
            _run(tool, filename="rapport.docx", content="Titre")
            self.assertEqual(seen["name"], "rapport.docx")
            self.assertEqual(s.get(ALICE, "Unique", f"{CREATIONS}/rapport.docx"), b"BINAIRE")

    def test_empty_content_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            SyncStore(tmp).register_workspace(ALICE, "Unique", "Unique")
            self.assertIn("vide", _run(_tools(tmp)[2], filename="x.md", content="   "))


if __name__ == "__main__":
    unittest.main()
