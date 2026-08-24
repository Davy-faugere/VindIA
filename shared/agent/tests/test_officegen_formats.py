"""Formats productibles par VindIA — binaires ET texte.

Bug réellement survenu (24/08/2026) : build_file n'acceptait que docx/xlsx/pptx/pdf et
levait « format non supporté » pour tout le reste. La consigne système demande pourtant
explicitement des .html et des .md : un « fais-moi un compte-rendu en markdown » finissait
donc en erreur 400, sans que rien ne l'explique à la personne.

Ces tests ne touchent que le chemin TEXTE : aucune dépendance externe, ils tournent
partout, y compris dans la CI « stdlib, 0 dépendance ».
"""

import unittest

from shared.agent.officegen import OFFICE_TYPES, TEXT_TYPES, build_file, formats_supportes


class FormatsTexteTest(unittest.TestCase):
    def test_markdown_est_livre_tel_quel(self):
        payload, mime = build_file("compte-rendu.md", "# Titre\n\n- point")
        self.assertEqual(payload.decode("utf-8"), "# Titre\n\n- point")
        self.assertEqual(mime, "text/markdown")

    def test_html_est_livre_tel_quel(self):
        # Le point 7 de la consigne système demande des pages .html complètes : sans ce
        # chemin, VindIA produisait un fichier que le serveur refusait de construire.
        page = "<!doctype html><html><body>Bonjour</body></html>"
        payload, mime = build_file("page.html", page)
        self.assertEqual(payload.decode("utf-8"), page)
        self.assertEqual(mime, "text/html")

    def test_csv_txt_json_et_script(self):
        for nom, mime_attendu in (
            ("donnees.csv", "text/csv"),
            ("notes.txt", "text/plain"),
            ("config.json", "application/json"),
            ("script.py", "text/x-python"),
        ):
            with self.subTest(nom=nom):
                payload, mime = build_file(nom, "contenu")
                self.assertEqual(payload, b"contenu")
                self.assertEqual(mime, mime_attendu)

    def test_extension_en_majuscules(self):
        _, mime = build_file("RAPPORT.MD", "x")
        self.assertEqual(mime, "text/markdown")

    def test_contenu_vide_reste_un_fichier_valide(self):
        payload, _ = build_file("vide.txt", "")
        self.assertEqual(payload, b"")

    def test_accents_conserves_en_utf8(self):
        payload, _ = build_file("note.md", "Procédure zone CMR — équipements")
        self.assertEqual(payload.decode("utf-8"), "Procédure zone CMR — équipements")

    def test_format_inconnu_reste_refuse(self):
        # On élargit les formats, on n'ouvre pas la porte à n'importe quoi.
        for nom in ("virus.exe", "archive.zip", "sans-extension"):
            with self.subTest(nom=nom):
                with self.assertRaises(ValueError):
                    build_file(nom, "x")


class CatalogueTest(unittest.TestCase):
    def test_les_quatre_bureautiques_sont_annonces(self):
        for ext in ("docx", "xlsx", "pptx", "pdf"):
            self.assertIn(ext, formats_supportes())

    def test_les_formats_texte_sont_annonces(self):
        for ext in ("md", "html", "csv", "txt"):
            self.assertIn(ext, formats_supportes())

    def test_aucun_recouvrement_entre_binaire_et_texte(self):
        # Un format traité des deux côtés serait ambigu : le binaire doit gagner, mais
        # mieux vaut que le cas n'existe pas.
        self.assertEqual(set(OFFICE_TYPES) & set(TEXT_TYPES), set())


if __name__ == "__main__":
    unittest.main()
