"""Formats productibles par VindIA — binaires ET texte.

Bug réellement survenu (24/08/2026) : build_file n'acceptait que docx/xlsx/pptx/pdf et
levait « format non supporté » pour tout le reste. La consigne système demande pourtant
explicitement des .html et des .md : un « fais-moi un compte-rendu en markdown » finissait
donc en erreur 400, sans que rien ne l'explique à la personne.

Couvre les formats TEXTE et les formats OpenDocument (.odt / .ods) : aucune dépendance
externe, ces tests tournent partout, y compris dans la CI « stdlib, 0 dépendance ».
"""

import io
import unittest
import xml.etree.ElementTree as ET
import zipfile

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



class OpenDocumentTest(unittest.TestCase):
    """.odt et .ods — construits, pas recopiés en markdown.

    Bug réellement survenu (24/08/2026) : ces deux formats n'étaient pas gérés. La page
    basculait alors sur du texte brut et l'utilisateur recevait son markdown non
    converti — « # Titre » et « **gras** » en clair dans un fichier nommé .odt.

    Aucune dépendance : un ODF est une archive ZIP de XML, donc ces tests tournent
    partout, y compris dans la CI « stdlib, 0 dépendance ».
    """

    CONTENU = (
        "# Rapport\n\nUn **paragraphe** construit.\n\n"
        "## Points\n\n- premier\n- second\n\n"
        "| Poste | Etat |\n|---|---|\n| A | Conforme |\n"
    )

    def _content_xml(self, nom, contenu):
        payload, mime = build_file(nom, contenu)
        z = zipfile.ZipFile(io.BytesIO(payload))
        return payload, mime, z, z.read("content.xml").decode("utf-8")

    def test_odt_produit_une_archive_odf_conforme(self):
        payload, mime, z, _ = self._content_xml("doc.odt", self.CONTENU)
        self.assertEqual(mime, "application/vnd.oasis.opendocument.text")
        # « mimetype » doit être la PREMIERE entrée et rester non compressée, sinon
        # les outils n'identifient pas le fichier et refusent de l'ouvrir.
        premiere = z.infolist()[0]
        self.assertEqual(premiere.filename, "mimetype")
        self.assertEqual(premiere.compress_type, zipfile.ZIP_STORED)
        self.assertEqual(z.read("mimetype").decode(), mime)
        for entree in ("content.xml", "meta.xml", "META-INF/manifest.xml"):
            self.assertIn(entree, z.namelist())

    def test_odt_construit_titres_listes_tableaux_et_gras(self):
        _, _, _, xml = self._content_xml("doc.odt", self.CONTENU)
        self.assertIn("<text:h", xml)                      # vrai titre
        self.assertIn("<text:list", xml)                   # vraie liste
        self.assertIn("<table:table", xml)                 # vrai tableau
        self.assertIn('text:style-name="GRAS"', xml)       # vrai gras

    def test_odt_ne_laisse_aucun_markdown_en_clair(self):
        # Le cœur du bug : c'est exactement ce que l'utilisateur voyait.
        _, _, _, xml = self._content_xml("doc.odt", self.CONTENU)
        self.assertNotIn("# Rapport", xml)
        self.assertNotIn("**", xml)
        self.assertNotIn("|---|", xml)

    def test_ods_type_les_nombres(self):
        # Sans typage, une colonne de chiffres ne se trie ni ne se calcule.
        _, mime, _, xml = self._content_xml("t.ods", "Produit;Quantite\nVis;120\nEcrou;45")
        self.assertEqual(mime, "application/vnd.oasis.opendocument.spreadsheet")
        self.assertIn('office:value-type="float"', xml)
        self.assertIn('office:value="120.0"', xml)
        self.assertIn("Vis", xml)

    def test_ods_accepte_un_tableau_markdown(self):
        _, _, _, xml = self._content_xml("t.ods", "| Poste | Prix |\n|---|---|\n| Vis | 12 |")
        self.assertIn("Poste", xml)
        self.assertIn('office:value="12.0"', xml)
        self.assertNotIn("|---|", xml)

    def test_caracteres_xml_dangereux_ne_cassent_pas_le_fichier(self):
        # Un « & » ou un « < » non échappé rend l'archive illisible.
        for nom in ("doc.odt", "t.ods"):
            with self.subTest(nom=nom):
                _, _, z, _ = self._content_xml(nom, "# R&D <urgent>\n\nSeuil < 5 & marge > 2 %")
                for entree in ("content.xml", "meta.xml", "META-INF/manifest.xml"):
                    ET.fromstring(z.read(entree))   # lève si le XML est mal formé

    def test_contenu_vide_reste_un_document_ouvrable(self):
        for nom in ("vide.odt", "vide.ods"):
            with self.subTest(nom=nom):
                _, _, z, xml = self._content_xml(nom, "")
                ET.fromstring(xml.encode("utf-8"))
                self.assertIn("mimetype", z.namelist())

    def test_transparence_ia_dans_les_metadonnees(self):
        # AI Act art. 50 : la mention voyage dans meta.xml, pas en travers du texte.
        payload, _ = build_file("doc.odt", "# T")
        meta = zipfile.ZipFile(io.BytesIO(payload)).read("meta.xml").decode("utf-8")
        self.assertIn("VindIA", meta)

if __name__ == "__main__":
    unittest.main()
