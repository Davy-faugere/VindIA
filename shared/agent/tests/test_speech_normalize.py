import unittest

from shared.agent.speech_normalize import normalize_for_speech


class SpeechNormalizeTest(unittest.TestCase):
    # --- markdown : marqueurs retirés, contenu conservé ---
    def test_strips_bold_and_italic_markers(self):
        self.assertEqual(normalize_for_speech("Cliquez **ici** et _là_"), "Cliquez ici et là")

    def test_strips_headings(self):
        self.assertEqual(normalize_for_speech("## Titre important"), "Titre important")

    def test_strips_inline_code_backticks(self):
        self.assertEqual(normalize_for_speech("lance `restart` vite"), "lance restart vite")

    def test_strips_bullets_and_ordered_lists(self):
        out = normalize_for_speech("- un\n- deux")
        self.assertEqual(out, "un deux")
        self.assertEqual(normalize_for_speech("1. premier"), "premier")

    def test_strips_horizontal_rule(self):
        self.assertEqual(normalize_for_speech("avant\n---\naprès"), "avant après")

    # --- liens : plus jamais lus lettre par lettre ---
    def test_bare_url_becomes_le_lien(self):
        self.assertEqual(
            normalize_for_speech("Voir https://faugere-davy.fr/contact maintenant"),
            "Voir le lien maintenant",
        )

    def test_www_url_becomes_le_lien(self):
        self.assertEqual(normalize_for_speech("va sur www.exemple.fr"), "va sur le lien")

    def test_markdown_link_keeps_label_drops_url(self):
        self.assertEqual(
            normalize_for_speech("Prends [rendez-vous](https://calendly.com/faugere-davy)"),
            "Prends rendez-vous",
        )

    def test_email_becomes_spoken_form(self):
        self.assertEqual(
            normalize_for_speech("écris à faugredavy@gmail.com stp"),
            "écris à l'adresse e-mail stp",
        )

    # --- symboles -> mots français ---
    def test_currency_euro(self):
        self.assertEqual(normalize_for_speech("ça coûte 100€"), "ça coûte 100 euros")

    def test_percent(self):
        self.assertEqual(normalize_for_speech("remise de 20%"), "remise de 20 pour cent")

    def test_ampersand_and_numero(self):
        self.assertEqual(normalize_for_speech("Dupont & fils"), "Dupont et fils")
        self.assertIn("numéro", normalize_for_speech("dossier n°42"))

    # --- mots anglais : conservés tels quels (décision Davy) ---
    def test_english_words_are_preserved(self):
        out = normalize_for_speech("On a un meeting et une deadline")
        self.assertIn("meeting", out)
        self.assertIn("deadline", out)

    # --- robustesse ---
    def test_empty_returns_empty(self):
        self.assertEqual(normalize_for_speech(""), "")
        self.assertEqual(normalize_for_speech("   "), "")

    def test_plain_french_sentence_is_untouched(self):
        phrase = "Bonjour, comment allez-vous aujourd'hui ?"
        self.assertEqual(normalize_for_speech(phrase), phrase)

    def test_realistic_mixed_reply(self):
        raw = "**Parfait !** Réservez ici : https://x.fr — tarif 50€ (soit 100%)."
        out = normalize_for_speech(raw)
        self.assertNotIn("**", out)
        self.assertNotIn("https", out)
        self.assertIn("le lien", out)
        self.assertIn("50 euros", out)
        self.assertIn("100 pour cent", out)


if __name__ == "__main__":
    unittest.main()
