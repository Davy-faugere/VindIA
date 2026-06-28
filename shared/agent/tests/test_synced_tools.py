"""Tests de l'accès au dossier synchronisé — offline, tmpdir."""

import asyncio
import tempfile
import unittest
from pathlib import Path

from shared.agent.synced_tools import SyncedListTool, SyncedReadTool, build_synced_tools


class SyncedToolsTest(unittest.TestCase):
    def _populate(self, tmp):
        base = Path(tmp)
        (base / ".stfolder").mkdir()  # marqueur Syncthing à masquer
        (base / "notes.md").write_text("# Notes\nProjet VindIA.", encoding="utf-8")
        (base / "sous").mkdir()
        (base / "sous" / "plan.txt").write_text("Étape 1.", encoding="utf-8")
        return base

    def test_list_recursive_hides_syncthing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._populate(tmp)
            out = asyncio.run(SyncedListTool(tmp).run({}))
            self.assertIn("notes.md", out)
            self.assertIn("sous/plan.txt", out)
            self.assertNotIn(".stfolder", out)

    def test_read_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._populate(tmp)
            out = asyncio.run(SyncedReadTool(tmp).run({"filename": "notes.md"}))
            self.assertIn("Projet VindIA", out)

    def test_read_subdir_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._populate(tmp)
            out = asyncio.run(SyncedReadTool(tmp).run({"filename": "sous/plan.txt"}))
            self.assertIn("Étape 1", out)

    def test_traversal_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._populate(tmp)
            out = asyncio.run(SyncedReadTool(tmp).run({"filename": "../../etc/passwd"}))
            self.assertIn("refusé", out)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._populate(tmp)
            out = asyncio.run(SyncedReadTool(tmp).run({"filename": "absent.txt"}))
            self.assertIn("introuvable", out)

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = asyncio.run(SyncedListTool(tmp).run({}))
            self.assertIn("vide", out)

    def test_build_synced_tools_names(self):
        tools = {t.spec.name for t in build_synced_tools("/tmp/x")}
        self.assertEqual(tools, {"synced_list_files", "synced_read_file"})


if __name__ == "__main__":
    unittest.main()
