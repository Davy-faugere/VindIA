"""Tests des compétences — hors ligne, tmpdir.

Ce qui compte : le sommaire n'expose JAMAIS le contenu (sinon le contexte explose),
une fiche personnelle prime sur la fiche livrée, et un membre ne voit pas les fiches
d'un autre.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path

from shared.agent.skill_tools import build_skill_tools
from shared.agent.skills import SkillStore, parse_skill, safe_name

ALICE = "00000001-0001-0001-0002-000000000001"
BOB = "00000001-0001-0001-0003-000000000001"

FICHE = "# Compte-rendu\n> Rédiger un compte-rendu exploitable.\n\nCorps très détaillé de la méthode.\n"


def _builtin(tmp: str) -> str:
    d = Path(tmp) / "livrees"
    d.mkdir(parents=True, exist_ok=True)
    (d / "compte-rendu.md").write_text(FICHE, encoding="utf-8")
    return str(d)


def _store(tmp: str) -> SkillStore:
    return SkillStore(_builtin(tmp), str(Path(tmp) / "perso"))


class ParseTest(unittest.TestCase):
    def test_extracts_title_and_description(self):
        s = parse_skill("compte-rendu", FICHE, "livrée")
        self.assertEqual(s.title, "Compte-rendu")
        self.assertEqual(s.description, "Rédiger un compte-rendu exploitable.")

    def test_malformed_sheet_falls_back_to_name(self):
        s = parse_skill("brute", "juste du texte sans en-tête", "livrée")
        self.assertEqual(s.title, "brute")
        self.assertEqual(s.description, "")

    def test_safe_name_slugifies(self):
        self.assertEqual(safe_name("Mes Comptes-Rendus !"), "mes-comptes-rendus")
        self.assertEqual(safe_name("../../etc/passwd"), "etc-passwd")


class StoreTest(unittest.TestCase):
    def test_lists_builtin(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = [s.name for s in _store(tmp).list_skills(ALICE)]
            self.assertEqual(names, ["compte-rendu"])

    def test_index_has_descriptions_but_not_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            idx = _store(tmp).build_index(ALICE)
            self.assertIn("compte-rendu", idx)
            self.assertIn("Rédiger un compte-rendu exploitable.", idx)
            # Le corps ne doit JAMAIS partir dans le contexte : c'est tout l'intérêt.
            self.assertNotIn("Corps très détaillé", idx)

    def test_personal_skill_overrides_builtin(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            store.save_skill(ALICE, "compte-rendu", "Ma version", "Ma façon à moi.", "Mon corps.")
            listed = store.list_skills(ALICE)
            self.assertEqual(len(listed), 1)              # remplace, ne duplique pas
            self.assertEqual(listed[0].source, "perso")
            self.assertIn("Mon corps.", store.read_skill(ALICE, "compte-rendu"))
            # Bob garde la fiche livrée.
            self.assertIn("Corps très détaillé", store.read_skill(BOB, "compte-rendu"))

    def test_members_are_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            store.save_skill(ALICE, "ma-methode", "Ma méthode", "Perso.", "Secret d'Alice.")
            self.assertNotIn("ma-methode", [s.name for s in store.list_skills(BOB)])
            self.assertEqual(store.read_skill(BOB, "ma-methode"), "")

    def test_delete_only_touches_personal(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            store.save_skill(ALICE, "compte-rendu", "Ma version", "x", "Mon corps.")
            self.assertTrue(store.delete_skill(ALICE, "compte-rendu"))
            # La fiche livrée est intacte et redevient active.
            self.assertIn("Corps très détaillé", store.read_skill(ALICE, "compte-rendu"))

    def test_content_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            store.save_skill(ALICE, "longue", "L", "d", "A" * 50000)
            self.assertLess(len(store.read_skill(ALICE, "longue")), 12500)

    def test_empty_builtin_dir_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = SkillStore(str(Path(tmp) / "absent"), str(Path(tmp) / "perso"))
            self.assertEqual(store.list_skills(ALICE), [])
            self.assertEqual(store.build_index(ALICE), "")


class ToolsTest(unittest.TestCase):
    def _tools(self, tmp, member=ALICE):
        return build_skill_tools(_store(tmp), member)

    def test_read_returns_full_sheet(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = asyncio.run(self._tools(tmp)[1].run({"name": "compte-rendu"}))
            self.assertIn("Corps très détaillé", out)

    def test_unknown_skill_lists_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = asyncio.run(self._tools(tmp)[1].run({"name": "inexistante"}))
            self.assertIn("introuvable", out)
            self.assertIn("compte-rendu", out)

    def test_save_then_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = self._tools(tmp)
            asyncio.run(tools[2].run({
                "name": "mes-cr", "title": "Mes CR", "description": "Ma façon.",
                "content": "Toujours commencer par les décisions.",
            }))
            out = asyncio.run(tools[1].run({"name": "mes-cr"}))
            self.assertIn("Toujours commencer par les décisions.", out)

    def test_anonymous_session_cannot_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = build_skill_tools(_store(tmp), None)
            self.assertEqual(len(tools), 2)   # pas d'outil d'écriture sans membre

    def test_save_refuses_empty_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = asyncio.run(self._tools(tmp)[2].run({"name": "x", "content": "  "}))
            self.assertIn("vide", out)


class ShippedSkillsTest(unittest.TestCase):
    """Les fiches réellement livrées doivent être exploitables, pas juste présentes."""

    def _shipped(self) -> SkillStore:
        return SkillStore(str(Path(__file__).resolve().parents[1] / "skills"))

    def test_every_shipped_skill_has_a_description(self):
        skills = self._shipped().list_skills()
        self.assertGreaterEqual(len(skills), 8)
        for s in skills:
            with self.subTest(skill=s.name):
                self.assertTrue(s.description, f"{s.name} n'a pas de ligne « > description »")
                self.assertTrue(s.title)

    def test_index_stays_short(self):
        # Le sommaire est injecté à CHAQUE message : il doit rester léger.
        self.assertLess(len(self._shipped().build_index()), 2000)


if __name__ == "__main__":
    unittest.main()
