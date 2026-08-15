"""Transparence IA — AI Act art. 50 : les contenus générés doivent être identifiables.

Ces tests ne dépendent d'aucune lib Office (ils vérifient les constantes et leur
usage dans le générateur) : la CI stdlib reste 0-dépendance. La génération binaire
réelle est validée à la main lors des déploiements.
"""

import unittest

from shared.agent import officegen


class AiTransparencyTest(unittest.TestCase):
    def test_notice_is_human_readable_and_french(self):
        self.assertIn("intelligence artificielle", officegen.AI_NOTICE.lower())
        self.assertIn("vindia", officegen.AI_NOTICE.lower())

    def test_machine_readable_metadata_mentions_ai_act(self):
        self.assertIn("AI-generated", officegen.AI_META)
        self.assertIn("art. 50", officegen.AI_META)

    def test_every_office_builder_tags_its_output(self):
        # Chaque générateur doit poser la mention et/ou les métadonnées IA.
        import inspect
        for name in ("_build_docx", "_build_xlsx", "_build_pptx", "_build_pdf"):
            src = inspect.getsource(getattr(officegen, name))
            self.assertTrue(
                "AI_NOTICE" in src or "_tag_office_meta" in src or "AI_META" in src,
                f"{name} ne marque pas le contenu comme généré par IA",
            )


if __name__ == "__main__":
    unittest.main()
