"""Tests de l'espace de travail synchronisé — hors ligne, tmpdir.

Priorité : l'isolation entre membres et le refus des chemins douteux, puis la
comparaison par empreinte (c'est elle qui évite de tout retransférer).
"""

import tempfile
import unittest

from shared.agent.sync_store import SyncStore, safe_rel, sha256, slug_workspace

ALICE = "00000001-0001-0001-0002-000000000001"
BOB = "00000001-0001-0001-0003-000000000001"


class SafeRelTest(unittest.TestCase):
    def test_accepts_subfolders(self):
        self.assertEqual(safe_rel("docs/plan.md"), "docs/plan.md")
        # Séparateurs Windows sur un chemin RELATIF : convertis, acceptés.
        self.assertEqual(safe_rel("docs\\sous\\plan.md"), "docs/sous/plan.md")

    def test_rejects_traversal_hidden_and_absolute(self):
        bad_paths = (
            "../secret", "docs/../../etc/passwd", ".ssh/id_rsa", "", "   ",
            "/etc/passwd",            # absolu Unix
            "\\docs\\plan.md",        # absolu Windows (racine du lecteur courant)
            "C:\\Windows\\x.txt",     # absolu Windows avec lettre de lecteur
        )
        for bad in bad_paths:
            with self.subTest(bad=bad):
                self.assertIsNone(safe_rel(bad))


class WorkspaceTest(unittest.TestCase):
    def test_register_and_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            ws = s.register_workspace(ALICE, "Vindia-dossier projet", "Vindia-dossier projet")
            self.assertEqual(ws, slug_workspace("Vindia-dossier projet"))
            listed = s.list_workspaces(ALICE)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["label"], "Vindia-dossier projet")

    def test_members_are_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "projet", "projet")
            s.put(ALICE, "projet", "secret.md", b"donnees alice")
            self.assertEqual(s.list_workspaces(BOB), [])
            self.assertIsNone(s.get(BOB, "projet", "secret.md"))

    def test_put_get_roundtrip_with_subfolder(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "p", "p")
            self.assertTrue(s.put(ALICE, "p", "sous/dossier/note.md", b"contenu"))
            self.assertEqual(s.get(ALICE, "p", "sous/dossier/note.md"), b"contenu")

    def test_put_refuses_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "p", "p")
            self.assertFalse(s.put(ALICE, "p", "../../evil.md", b"x"))

    def test_index_detects_change_by_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "p", "p")
            s.put(ALICE, "p", "a.md", b"version un")
            first = s.index(ALICE, "p")["a.md"]["hash"]
            s.put(ALICE, "p", "a.md", b"version DEUX")   # même longueur, contenu différent
            second = s.index(ALICE, "p")["a.md"]["hash"]
            self.assertNotEqual(first, second)
            self.assertEqual(second, sha256(b"version DEUX"))

    def test_index_ignores_hidden_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "p", "p")       # crée .vindia-workspace.json
            s.put(ALICE, "p", "visible.md", b"x")
            self.assertEqual(list(s.index(ALICE, "p")), ["visible.md"])

    def test_delete_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = SyncStore(tmp)
            s.register_workspace(ALICE, "p", "p")
            s.put(ALICE, "p", "a.md", b"x")
            self.assertTrue(s.delete_workspace(ALICE, "p"))
            self.assertEqual(s.list_workspaces(ALICE), [])

    def test_invalid_member_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                SyncStore(tmp).register_workspace("../evil", "p", "p")


if __name__ == "__main__":
    unittest.main()
