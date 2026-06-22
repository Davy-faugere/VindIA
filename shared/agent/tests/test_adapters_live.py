"""Test LIVE de l'adaptateur Mistral — OPT-IN (appel réseau réel, facturé).

Ne s'exécute QUE si VINDIA_MISTRAL_LIVE=1 ET MISTRAL_API_KEY présent. Sinon SKIP
→ la CI stdlib offline n'est jamais impactée. Nécessite `mistralai` installé
(cf. requirements.txt), donc à lancer dans le venv VindIA :

    set -a; . server/.env; set +a
    VINDIA_MISTRAL_LIVE=1 .venv/bin/python -m unittest \
        shared.agent.tests.test_adapters_live -v

Prouve que MistralLLM parle réellement à La Plateforme (pas seulement aux mocks).
STT (Voxtral) et TTS : test live différé au câblage audio (J4) — le STT exige un
échantillon vocal réel, et le TTS Voxtral n'est pas exposé par le SDK 1.x
(appel REST à `voxtral-mini-tts-*` au branchement).
"""

import asyncio
import os
import unittest

from shared.agent.adapters import MistralLLM

_LIVE = (
    os.environ.get("VINDIA_MISTRAL_LIVE") == "1"
    and bool(os.environ.get("MISTRAL_API_KEY"))
)


@unittest.skipUnless(_LIVE, "live Mistral : poser VINDIA_MISTRAL_LIVE=1 + MISTRAL_API_KEY")
class MistralLLMLiveTest(unittest.TestCase):
    def test_real_completion_returns_non_empty_text(self):
        llm = MistralLLM(
            model="mistral-small-latest",
            system_prompt="Réponds en un seul mot, sans ponctuation.",
        )
        out = asyncio.run(
            llm.reply("Quelle est la capitale de la France ?", session_id="live")
        )
        self.assertIsInstance(out, str)
        self.assertTrue(out.strip(), "réponse live vide")


if __name__ == "__main__":
    unittest.main()
