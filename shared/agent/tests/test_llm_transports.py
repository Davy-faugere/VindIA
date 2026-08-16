"""Tests des traducteurs multi-fournisseurs — hors ligne, aucun appel réseau.

Ce qui compte : un aller-retour d'OUTIL doit survivre à la traduction. C'est le
point fragile — si l'identifiant d'appel se perd, le modèle ne relie plus le
résultat à sa question et la conversation part en boucle.
"""

import json
import unittest

from shared.agent.llm_transports import (
    anthropic_parse,
    anthropic_payload,
    google_parse,
    google_payload,
    openai_parse,
    openai_payload,
)
from shared.agent.providers import PROVIDERS, catalogue, get_provider, verifie_cle

SPECS = [{
    "type": "function",
    "function": {
        "name": "folder_read_file",
        "description": "Lit un fichier",
        "parameters": {"type": "object", "properties": {"filename": {"type": "string"}}},
    },
}]

# Historique tel que la boucle interne le produit apres un appel d'outil.
HISTORIQUE = [
    {"role": "system", "content": "Tu es VindIA."},
    {"role": "user", "content": "Lis mon plan"},
    {"role": "assistant", "content": "", "tool_calls": [
        {"id": "call_1", "type": "function",
         "function": {"name": "folder_read_file", "arguments": '{"filename":"plan.md"}'}}]},
    {"role": "tool", "name": "folder_read_file", "tool_call_id": "call_1", "content": "le plan"},
]


class OpenAiTest(unittest.TestCase):
    def test_payload_passe_tel_quel(self):
        body = openai_payload(HISTORIQUE, SPECS, "gpt-4o")
        self.assertEqual(body["model"], "gpt-4o")
        self.assertEqual(body["messages"], list(HISTORIQUE))
        self.assertEqual(body["tool_choice"], "auto")

    def test_sans_outils_pas_de_champ_tools(self):
        self.assertNotIn("tools", openai_payload(HISTORIQUE, [], "m"))

    def test_parse_appel_outil(self):
        out = openai_parse({"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "c1", "function": {"name": "web_search", "arguments": '{"q":"x"}'}}]}}]})
        self.assertEqual(out["tool_calls"][0]["name"], "web_search")
        self.assertEqual(out["content"], "")

    def test_parse_reponse_texte(self):
        out = openai_parse({"choices": [{"message": {"content": "Bonjour"}}]})
        self.assertEqual(out["content"], "Bonjour")
        self.assertEqual(out["tool_calls"], [])


class AnthropicTest(unittest.TestCase):
    def test_system_sorti_des_messages(self):
        body = anthropic_payload(HISTORIQUE, SPECS, "claude-sonnet-4-5")
        self.assertEqual(body["system"], "Tu es VindIA.")
        self.assertTrue(all(m["role"] != "system" for m in body["messages"]))

    def test_appel_outil_devient_tool_use(self):
        body = anthropic_payload(HISTORIQUE, SPECS, "m")
        assistant = [m for m in body["messages"] if m["role"] == "assistant"][0]
        bloc = [b for b in assistant["content"] if b["type"] == "tool_use"][0]
        self.assertEqual(bloc["name"], "folder_read_file")
        self.assertEqual(bloc["input"], {"filename": "plan.md"})   # objet, pas chaine

    def test_resultat_outil_rattache_au_bon_appel(self):
        body = anthropic_payload(HISTORIQUE, SPECS, "m")
        dernier = body["messages"][-1]
        self.assertEqual(dernier["role"], "user")
        self.assertEqual(dernier["content"][0]["type"], "tool_result")
        self.assertEqual(dernier["content"][0]["tool_use_id"], "call_1")

    def test_resultats_consecutifs_regroupes(self):
        hist = HISTORIQUE + [
            {"role": "tool", "name": "x", "tool_call_id": "call_2", "content": "b"}]
        body = anthropic_payload(hist, [], "m")
        self.assertEqual(len(body["messages"][-1]["content"]), 2)   # un seul message user

    def test_outils_traduits_en_input_schema(self):
        body = anthropic_payload(HISTORIQUE, SPECS, "m")
        self.assertEqual(body["tools"][0]["name"], "folder_read_file")
        self.assertIn("filename", body["tools"][0]["input_schema"]["properties"])

    def test_parse_et_retour_boucle(self):
        out = anthropic_parse({"content": [
            {"type": "text", "text": "Je regarde."},
            {"type": "tool_use", "id": "toolu_9", "name": "folder_read_file",
             "input": {"filename": "a.md"}}]})
        self.assertEqual(out["content"], "Je regarde.")
        self.assertEqual(out["tool_calls"][0]["id"], "toolu_9")
        self.assertEqual(json.loads(out["tool_calls"][0]["arguments"]), {"filename": "a.md"})
        # L'assistant renvoye doit repasser dans le traducteur sans perte.
        rebody = anthropic_payload([out["assistant"]], [], "m")
        self.assertEqual(rebody["messages"][0]["content"][1]["id"], "toolu_9")

    def test_arguments_json_invalide_ne_casse_pas(self):
        hist = [{"role": "assistant", "content": "", "tool_calls": [
            {"id": "c", "function": {"name": "f", "arguments": "pas du json"}}]}]
        body = anthropic_payload(hist, [], "m")
        self.assertEqual(body["messages"][0]["content"][0]["input"], {})


class GoogleTest(unittest.TestCase):
    def test_roles_convertis(self):
        body = google_payload(HISTORIQUE, SPECS, "gemini-2.5-flash")
        roles = [c["role"] for c in body["contents"]]
        self.assertIn("model", roles)          # « assistant » devient « model »
        self.assertNotIn("assistant", roles)
        self.assertNotIn("system", roles)
        self.assertIn("Tu es VindIA.", body["systemInstruction"]["parts"][0]["text"])

    def test_appel_et_resultat_outil(self):
        body = google_payload(HISTORIQUE, SPECS, "m")
        modele = [c for c in body["contents"] if c["role"] == "model"][0]
        self.assertEqual(modele["parts"][0]["functionCall"]["name"], "folder_read_file")
        self.assertIn("functionResponse", body["contents"][-1]["parts"][0])

    def test_parse_fabrique_un_identifiant(self):
        out = google_parse({"candidates": [{"content": {"parts": [
            {"functionCall": {"name": "web_search", "args": {"q": "x"}}}]}}]})
        # Gemini n'en fournit pas : sans identifiant, la boucle ne peut pas
        # rattacher le resultat a son appel.
        self.assertTrue(out["tool_calls"][0]["id"])
        self.assertEqual(out["tool_calls"][0]["name"], "web_search")

    def test_parse_texte(self):
        out = google_parse({"candidates": [{"content": {"parts": [{"text": "Salut"}]}}]})
        self.assertEqual(out["content"], "Salut")
        self.assertEqual(out["tool_calls"], [])

    def test_reponse_vide_ne_casse_pas(self):
        self.assertEqual(google_parse({})["content"], "")


class CatalogueTest(unittest.TestCase):
    def test_chaque_fournisseur_est_exploitable(self):
        for code, p in PROVIDERS.items():
            with self.subTest(fournisseur=code):
                self.assertTrue(p.etapes, "il faut une marche a suivre")
                self.assertTrue(p.console_url.startswith("https://"))
                self.assertIn(p.famille, ("openai", "anthropic", "google"))
                self.assertTrue(p.hebergement)          # transparence sur les donnees
                self.assertIn(p.modele_defaut, p.modeles)

    def test_europeen_en_tete(self):
        self.assertEqual(catalogue()[0]["code"], "mistral")

    def test_la_cle_n_est_jamais_dans_le_catalogue(self):
        self.assertNotIn("base_url", catalogue()[0])

    def test_verifie_cle(self):
        self.assertIsNone(verifie_cle("mistral", "a" * 40))
        self.assertIn("trop courte", verifie_cle("mistral", "abc"))
        self.assertIn("espace", verifie_cle("mistral", "aaaaaaaaaaaaaaaaaaaa bbb"))
        self.assertIn("sk-ant-", verifie_cle("anthropic", "sk-proj-" + "a" * 30))
        self.assertIn("inconnu", verifie_cle("nawak", "a" * 40))
        self.assertIn("vide", verifie_cle("mistral", "   "))

    def test_get_provider_tolere_la_casse(self):
        self.assertIsNotNone(get_provider("  MISTRAL "))


if __name__ == "__main__":
    unittest.main()
