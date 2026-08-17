"""Tests du connecteur Notion — hors ligne, appel réseau simulé.

Ce qui compte : la conversion des blocs (c'est ce que le modèle lira), les messages
d'erreur actionnables, et le fait qu'aucun outil n'écrive dans Notion.
"""

import asyncio
import unittest

from shared.agent.connectors import catalogue, get_connecteur, vault_service, verifie_jeton
from shared.agent.notion_tools import bloc_en_texte, build_notion_tools, titre_page

PAGE = {"object": "page", "id": "abc-123", "properties": {
    "Nom": {"type": "title", "title": [{"plain_text": "Base de règles VindIA"}]}}}


def faux_appel(reponses, journal=None):
    async def _call(methode, chemin, corps=None):
        if journal is not None:
            journal.append((methode, chemin, corps))
        r = reponses.get(chemin.split("?")[0])
        if isinstance(r, Exception):
            raise r
        return r or {}
    return _call


def _run(tool, **args):
    return asyncio.run(tool.run(args))


class ConversionTest(unittest.TestCase):
    def test_titres_et_listes(self):
        cas = [
            ({"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Titre"}]}}, "\n# Titre"),
            ({"type": "heading_2", "heading_2": {"rich_text": [{"plain_text": "Sous"}]}}, "\n## Sous"),
            ({"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "a"}]}}, "- a"),
            ({"type": "numbered_list_item", "numbered_list_item": {"rich_text": [{"plain_text": "b"}]}}, "1. b"),
            ({"type": "quote", "quote": {"rich_text": [{"plain_text": "c"}]}}, "> c"),
            ({"type": "divider", "divider": {}}, "---"),
        ]
        for bloc, attendu in cas:
            with self.subTest(type=bloc["type"]):
                self.assertEqual(bloc_en_texte(bloc), attendu)

    def test_case_a_cocher_garde_son_etat(self):
        fait = {"type": "to_do", "to_do": {"rich_text": [{"plain_text": "livrer"}], "checked": True}}
        reste = {"type": "to_do", "to_do": {"rich_text": [{"plain_text": "tester"}], "checked": False}}
        self.assertEqual(bloc_en_texte(fait), "[x] livrer")
        self.assertEqual(bloc_en_texte(reste), "[ ] tester")

    def test_ligne_de_tableau(self):
        bloc = {"type": "table_row", "table_row": {"cells": [
            [{"plain_text": "Mars"}], [{"plain_text": "1200"}]]}}
        self.assertEqual(bloc_en_texte(bloc), "| Mars | 1200 |")

    def test_bloc_inconnu_ne_casse_pas(self):
        self.assertEqual(bloc_en_texte({"type": "embed", "embed": {}}), "")
        self.assertEqual(bloc_en_texte({}), "")

    def test_titre_quel_que_soit_le_nom_de_propriete(self):
        self.assertEqual(titre_page(PAGE), "Base de règles VindIA")
        self.assertEqual(titre_page({"properties": {}}), "(sans titre)")


class RechercheTest(unittest.TestCase):
    def test_liste_les_resultats_avec_identifiants(self):
        outils = build_notion_tools("ntn_x", faux_appel({"/search": {"results": [PAGE]}}))
        out = _run(outils[0], query="règles")
        self.assertIn("Base de règles VindIA", out)
        self.assertIn("abc-123", out)          # l'id sert à notion_read ensuite

    def test_aucun_resultat_rappelle_le_partage(self):
        outils = build_notion_tools("ntn_x", faux_appel({"/search": {"results": []}}))
        out = _run(outils[0], query="inconnu")
        self.assertIn("partagées", out)        # la cause la plus fréquente

    def test_erreur_de_jeton_est_actionnable(self):
        appel = faux_appel({"/search": RuntimeError("Le jeton Notion est refusé.")})
        out = _run(build_notion_tools("x", appel)[0], query="a")
        self.assertIn("jeton", out.lower())


class LectureTest(unittest.TestCase):
    def _outil(self, blocs, journal=None):
        return build_notion_tools(
            "ntn_x", faux_appel({"/blocks/abc123/children": {"results": blocs}}, journal))[1]

    def test_lit_et_structure_la_page(self):
        blocs = [
            {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Plan"}]}},
            {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"plain_text": "point"}]}},
        ]
        out = _run(self._outil(blocs), page_id="abc-123")
        self.assertIn("# Plan", out)
        self.assertIn("- point", out)

    def test_identifiant_avec_tirets_accepte(self):
        journal = []
        _run(self._outil([], journal), page_id="abc-123")
        # Notion accepte les deux formes ; on normalise pour ne pas dépendre de la saisie.
        self.assertIn("/blocks/abc123/children", journal[0][1])

    def test_page_vide(self):
        self.assertIn("vide", _run(self._outil([]), page_id="abc123"))

    def test_page_longue_est_tronquee(self):
        blocs = [{"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "A" * 300}]}}
                 for _ in range(40)]
        out = _run(self._outil(blocs), page_id="abc123")
        self.assertLess(len(out), 6300)
        self.assertIn("tronquée", out)


class LectureSeuleTest(unittest.TestCase):
    def test_aucun_outil_n_ecrit_dans_notion(self):
        journal = []
        outils = build_notion_tools("ntn_x", faux_appel({"/search": {"results": []}}, journal))
        noms = [o.spec.name for o in outils]
        self.assertEqual(noms, ["notion_search", "notion_read"])
        _run(outils[0], query="a")
        # /search est un POST côté Notion, mais aucun appel ne vise une ressource
        # modifiable (pages, blocs) en écriture.
        for methode, chemin, _ in journal:
            self.assertFalse(methode in ("PATCH", "PUT", "DELETE"), (methode, chemin))


class CatalogueTest(unittest.TestCase):
    def test_notion_est_documente(self):
        c = get_connecteur("NOTION")
        self.assertIsNotNone(c)
        self.assertTrue(c.etapes and c.piege)
        self.assertTrue(c.console_url.startswith("https://"))
        self.assertEqual(catalogue()[0]["code"], "notion")

    def test_service_du_coffre_est_prefixe(self):
        # Sans préfixe, un service de connexion pourrait écraser la clé « llm ».
        self.assertEqual(vault_service("notion"), "conn:notion")

    def test_verifie_jeton(self):
        self.assertIsNone(verifie_jeton("notion", "ntn_" + "a" * 40))
        self.assertIsNone(verifie_jeton("notion", "secret_" + "a" * 40))   # ancien format
        self.assertIn("trop court", verifie_jeton("notion", "ntn_a"))
        self.assertIn("espace", verifie_jeton("notion", "ntn_" + "a" * 20 + " b"))
        self.assertIn("commence normalement", verifie_jeton("notion", "xoxb-" + "a" * 40))
        self.assertIn("inconnu", verifie_jeton("nawak", "a" * 40))


if __name__ == "__main__":
    unittest.main()
