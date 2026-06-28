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
        self.assertEqual(tools, {"synced_list_files", "synced_read_file", "synced_write_file"})

    def test_write_creates_in_creations_subfolder(self):
        from shared.agent.synced_tools import SyncedWriteTool, _CREATIONS
        with tempfile.TemporaryDirectory() as tmp:
            out = asyncio.run(SyncedWriteTool(tmp).run({"filename": "cr.md", "content": "# Bilan\nok"}))
            self.assertIn("cr.md", out)
            written = Path(tmp) / _CREATIONS / "cr.md"
            self.assertTrue(written.is_file())
            self.assertIn("Bilan", written.read_text())

    def test_write_rejects_empty(self):
        from shared.agent.synced_tools import SyncedWriteTool
        with tempfile.TemporaryDirectory() as tmp:
            out = asyncio.run(SyncedWriteTool(tmp).run({"filename": "x.md", "content": "  "}))
            self.assertIn("vide", out)

    def test_write_office_uses_binary_builder(self):
        # .docx → vrai binaire via le générateur (pas le markdown brut).
        from shared.agent.synced_tools import SyncedWriteTool, _CREATIONS
        with tempfile.TemporaryDirectory() as tmp:
            calls = {}
            def fake_builder(name, content, base_dir=None):
                calls["name"] = name
                calls["base_dir"] = base_dir
                return (b"PK\x03\x04 vrai-docx", "application/…")
            tool = SyncedWriteTool(tmp, office_builder=fake_builder)
            asyncio.run(tool.run({"filename": "rapport.docx", "content": "# Titre\n- point"}))
            written = (Path(tmp) / _CREATIONS / "rapport.docx").read_bytes()
            self.assertEqual(calls["name"], "rapport.docx")
            self.assertTrue(written.startswith(b"PK"))  # binaire, pas du markdown

    def test_write_text_stays_text(self):
        from shared.agent.synced_tools import SyncedWriteTool, _CREATIONS
        with tempfile.TemporaryDirectory() as tmp:
            asyncio.run(SyncedWriteTool(tmp).run({"filename": "note.md", "content": "# Salut"}))
            self.assertEqual((Path(tmp) / _CREATIONS / "note.md").read_text(), "# Salut")


if __name__ == "__main__":
    unittest.main()
