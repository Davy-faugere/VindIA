"""Tests des projets persistants — 100 % offline, tmpdir, 0 dépendance tierce.

Priorité : prouver l'ISOLATION par membre (anti path-traversal, cloisonnement)
et l'ingestion texte. Les formats binaires (docx/xlsx/pptx/pdf) ne sont pas testés
ici (libs tierces) — seul le routage par extension et le texte pur le sont.
"""

import tempfile
import unittest
from pathlib import Path

from shared.agent.projects import (
    ExtractionError,
    ProjectStore,
    extract_text,
    safe_filename,
    slugify,
)

# Deux membres distincts (UUID CHAR(36)) pour les tests de cloisonnement.
ALICE = "00000001-0001-0001-0002-000000000001"
BOB = "00000001-0001-0001-0003-000000000001"


def _store(tmp):
    # Horloge fixe → métadonnées déterministes.
    return ProjectStore(tmp, clock=lambda: "2026-06-27T00:00:00+00:00")


class SanitizeTest(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Mon Projet MLM !"), "mon-projet-mlm")
        self.assertEqual(slugify(""), "projet")
        self.assertEqual(slugify("////"), "projet")

    def test_safe_filename_strips_paths(self):
        self.assertEqual(safe_filename("../../etc/passwd"), "passwd")
        self.assertEqual(safe_filename("/abs/note.txt"), "note.txt")
        self.assertEqual(safe_filename("a b/c?d.txt"), "c_d.txt")  # basename assaini
        self.assertTrue(safe_filename(""))  # jamais vide


class IsolationTest(unittest.TestCase):
    def test_invalid_member_id_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            for bad in ("../evil", "a/b", "..", "x" * 40, "no_underscore!"):
                with self.subTest(bad=bad):
                    with self.assertRaises(ValueError):
                        store.create_project(bad, "p")

    def test_members_are_partitioned(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            pa = store.create_project(ALICE, "Secret Alice")
            store.add_document(ALICE, pa.project_id, "a.txt", "données alice")
            # Bob ne voit RIEN d'Alice.
            self.assertEqual(store.list_projects(BOB), [])
            self.assertIsNone(store.get_project(BOB, pa.project_id))
            self.assertEqual(store.read_document(BOB, pa.project_id, "a.txt"), "")

    def test_files_land_under_member_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            p = store.create_project(ALICE, "P")
            store.add_document(ALICE, p.project_id, "../escape.txt", "x")
            # Le fichier est confiné sous <tmp>/<ALICE>/, nom assaini.
            member_root = Path(tmp) / ALICE
            written = list(member_root.rglob("*.txt"))
            self.assertEqual(len(written), 1)
            self.assertTrue(str(written[0]).startswith(str(member_root)))
            self.assertIn("escape.txt", written[0].name)


class ProjectCrudTest(unittest.TestCase):
    def test_create_list_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            p = store.create_project(ALICE, "Lancement MLM")
            self.assertEqual(p.project_id, "lancement-mlm")
            self.assertEqual(p.name, "Lancement MLM")
            got = store.list_projects(ALICE)
            self.assertEqual(len(got), 1)
            self.assertEqual(got[0].project_id, "lancement-mlm")

    def test_name_collision_suffixes(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            a = store.create_project(ALICE, "Projet")
            b = store.create_project(ALICE, "Projet")
            self.assertEqual(a.project_id, "projet")
            self.assertEqual(b.project_id, "projet-2")

    def test_add_document_updates_meta_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            p = store.create_project(ALICE, "P")
            store.add_document(ALICE, p.project_id, "notes.txt", "bonjour")
            # Relecture depuis le disque (nouveau store) → persistance prouvée.
            reloaded = _store(tmp).get_project(ALICE, p.project_id)
            self.assertEqual(len(reloaded.documents), 1)
            self.assertEqual(reloaded.documents[0].filename, "notes.txt")
            self.assertEqual(reloaded.documents[0].chars, len("bonjour"))

    def test_reupload_same_name_replaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            p = store.create_project(ALICE, "P")
            store.add_document(ALICE, p.project_id, "n.txt", "v1")
            store.add_document(ALICE, p.project_id, "n.txt", "v2 plus long")
            proj = store.get_project(ALICE, p.project_id)
            self.assertEqual(len(proj.documents), 1)
            self.assertEqual(store.read_document(ALICE, p.project_id, "n.txt"), "v2 plus long")

    def test_add_document_unknown_project_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                _store(tmp).add_document(ALICE, "nope", "f.txt", "x")

    def test_build_context_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            p = store.create_project(ALICE, "Gros")
            store.add_document(ALICE, p.project_id, "big.txt", "A" * 50000)
            ctx = store.build_context(ALICE, p.project_id)
            self.assertIn("Gros", ctx)
            self.assertIn("big.txt", ctx)
            self.assertLess(len(ctx), store.CONTEXT_BUDGET + 500)
            self.assertIn("[…]", ctx)  # tronqué

    def test_build_context_empty_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(tmp)
            p = store.create_project(ALICE, "Vide")
            self.assertEqual(store.build_context(ALICE, p.project_id), "")


class ExtractTextTest(unittest.TestCase):
    def test_plain_text_and_csv(self):
        self.assertEqual(extract_text("a.txt", b"  hello  "), "hello")
        self.assertEqual(extract_text("d.csv", "x,y\n1,2".encode()), "x,y\n1,2")

    def test_html_extraction(self):
        out = extract_text("p.html", b"<p>Salut <b>toi</b></p><script>x()</script>")
        self.assertIn("Salut toi", out)
        self.assertNotIn("x()", out)

    def test_unsupported_extension_raises(self):
        with self.assertRaises(ExtractionError):
            extract_text("image.png", b"\x89PNG")

    def test_utf8_tolerant(self):
        # Octets invalides ne lèvent pas (decode errors=replace).
        self.assertIsInstance(extract_text("x.txt", b"\xff\xfe abc"), str)


if __name__ == "__main__":
    unittest.main()
