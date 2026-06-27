"""Tests des outils « espace de travail projet » — offline, tmpdir.

Prouve : lister/lire/écrire dans le projet actif, et que chaque outil est figé
sur (member_id, project_id) → impossible de viser l'espace d'un autre.
"""

import asyncio
import tempfile
import unittest

from shared.agent.projects import ProjectStore
from shared.agent.project_tools import build_project_tools
from shared.agent.tools import ToolRegistry

ALICE = "00000001-0001-0001-0002-000000000001"
BOB = "00000001-0001-0001-0003-000000000001"


def _store(tmp):
    return ProjectStore(tmp, clock=lambda: "2026-06-27T00:00:00+00:00")


class ProjectToolsTest(unittest.TestCase):
    def test_list_read_write_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            p = store.create_project(ALICE, "Atelier")
            store.add_document(ALICE, p.project_id, "brief.md", "Objectif : lancer en septembre.")
            tools = {t.spec.name: t for t in build_project_tools(store, ALICE, p.project_id)}

            listed = asyncio.run(tools["list_project_files"].run({}))
            self.assertIn("brief.md", listed)

            read = asyncio.run(tools["read_project_file"].run({"filename": "brief.md"}))
            self.assertIn("septembre", read)

            # write : crée un nouveau fichier dans le projet
            w = asyncio.run(tools["write_project_file"].run({"filename": "skill.md", "content": "# Mon skill\nfais X"}))
            self.assertIn("skill.md", w)
            again = store.read_document(ALICE, p.project_id, "skill.md")
            self.assertIn("Mon skill", again)

    def test_tools_are_scoped_to_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            pa = store.create_project(ALICE, "Privé Alice")
            store.add_document(ALICE, pa.project_id, "secret.md", "données Alice")
            # Outils construits pour BOB sur l'id de projet d'Alice : Bob n'a pas ce
            # projet → rien ne fuite.
            bob_tools = {t.spec.name: t for t in build_project_tools(store, BOB, pa.project_id)}
            listed = asyncio.run(bob_tools["list_project_files"].run({}))
            self.assertIn("Aucun projet actif", listed)
            read = asyncio.run(bob_tools["read_project_file"].run({"filename": "secret.md"}))
            self.assertIn("introuvable", read)

    def test_read_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            p = store.create_project(ALICE, "P")
            tools = {t.spec.name: t for t in build_project_tools(store, ALICE, p.project_id)}
            out = asyncio.run(tools["read_project_file"].run({"filename": "nope.txt"}))
            self.assertIn("introuvable", out)

    def test_write_rejects_empty_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            p = store.create_project(ALICE, "P")
            tools = {t.spec.name: t for t in build_project_tools(store, ALICE, p.project_id)}
            out = asyncio.run(tools["write_project_file"].run({"filename": "x.md", "content": "   "}))
            self.assertIn("vide", out)

    def test_registry_dispatch_via_tools(self):
        # Les outils projet passent par le ToolRegistry (comme dans la boucle LLM).
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            p = store.create_project(ALICE, "P")
            reg = ToolRegistry(build_project_tools(store, ALICE, p.project_id))
            names = {s["function"]["name"] for s in reg.specs()}
            self.assertEqual(names, {"list_project_files", "read_project_file", "write_project_file"})
            out = asyncio.run(reg.dispatch("write_project_file", '{"filename":"n.md","content":"hello"}'))
            self.assertIn("enregistré", out)


class BuildIndexTest(unittest.TestCase):
    def test_index_lists_names_not_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            p = store.create_project(ALICE, "Réf")
            store.add_document(ALICE, p.project_id, "gros.md", "X" * 50000)
            idx = store.build_index(ALICE, p.project_id)
            self.assertIn("gros.md", idx)
            self.assertIn("read_project_file", idx)
            self.assertNotIn("XXXX", idx)          # PAS le contenu
            self.assertLess(len(idx), 500)          # léger même pour un gros fichier

    def test_index_empty_project_invites_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            p = store.create_project(ALICE, "Vide")
            self.assertIn("write_project_file", store.build_index(ALICE, p.project_id))


if __name__ == "__main__":
    unittest.main()
