"""Tests des adaptateurs STT/LLM/TTS — 100 % offline, 0 dépendance.

On injecte un `transport` fake dans chaque adaptateur : aucun appel réseau,
aucune lib tierce. Le test end-to-end prouve que les adaptateurs respectent
bien les Protocol attendus par `ConversationRuntime`.
"""

import asyncio
import unittest

from shared.agent.adapters import CallableTTS, MistralLLM, VoxtralSTT
from shared.agent.runtime import ConversationRuntime
from shared.agent.session import SessionDescriptor


class MistralLLMTest(unittest.TestCase):
    def test_uses_transport_and_prepends_system_prompt(self):
        captured = {}

        async def fake(messages):
            captured["messages"] = list(messages)
            return "réponse-mock"

        llm = MistralLLM(transport=fake, system_prompt="Tu es VindIA.")
        out = asyncio.run(llm.reply("bonjour", session_id="s1"))

        self.assertEqual(out, "réponse-mock")
        self.assertEqual(
            captured["messages"],
            [
                {"role": "system", "content": "Tu es VindIA."},
                {"role": "user", "content": "bonjour"},
            ],
        )

    def test_without_system_prompt_sends_only_user_turn(self):
        captured = {}

        async def fake(messages):
            captured["messages"] = list(messages)
            return "ok"

        # system_prompt=None explicite pour désactiver le prompt par défaut.
        asyncio.run(MistralLLM(transport=fake, system_prompt=None).reply("salut", session_id="s1"))
        self.assertEqual(captured["messages"], [{"role": "user", "content": "salut"}])

    def test_default_system_prompt_is_vindia(self):
        from shared.agent.adapters import VINDIA_SYSTEM_PROMPT
        captured = {}

        async def fake(messages):
            captured["messages"] = list(messages)
            return "ok"

        asyncio.run(MistralLLM(transport=fake).reply("bonjour", session_id="s1"))
        self.assertEqual(captured["messages"][0]["role"], "system")
        self.assertEqual(captured["messages"][0]["content"], VINDIA_SYSTEM_PROMPT)
        self.assertEqual(captured["messages"][-1], {"role": "user", "content": "bonjour"})

    def test_system_prompt_instructs_file_creation(self):
        # VindIA doit savoir produire un document téléchargeable via [[FICHIER:…]].
        from shared.agent.adapters import VINDIA_SYSTEM_PROMPT
        self.assertIn("[[FICHIER:", VINDIA_SYSTEM_PROMPT)
        self.assertIn("[[/FICHIER]]", VINDIA_SYSTEM_PROMPT)

    def test_history_accumulates_across_turns(self):
        calls = []

        async def fake(messages):
            calls.append([m.copy() for m in messages])
            return f"r{len(calls)}"

        llm = MistralLLM(transport=fake, system_prompt=None)
        asyncio.run(llm.reply("tour1", session_id="s1"))
        asyncio.run(llm.reply("tour2", session_id="s1"))

        # 2e appel : [user:tour1, assistant:r1, user:tour2]
        second = calls[1]
        self.assertEqual(second[0], {"role": "user", "content": "tour1"})
        self.assertEqual(second[1], {"role": "assistant", "content": "r1"})
        self.assertEqual(second[2], {"role": "user", "content": "tour2"})

    def test_history_bounded_by_max_history(self):
        async def fake(messages):
            return "x"

        llm = MistralLLM(transport=fake, system_prompt=None, max_history=2)
        for i in range(10):
            asyncio.run(llm.reply(f"t{i}", session_id="s1"))

        # max_history=2 → au plus 4 messages d'historique (2 tours × 2)
        history = llm._history["s1"]
        self.assertLessEqual(len(history), 4)

    def test_load_memory_injected_into_system(self):
        captured = {}

        async def fake(messages):
            captured["messages"] = list(messages)
            return "ok"

        llm = MistralLLM(transport=fake, system_prompt="Base.")
        llm.load_memory("s1", "[Mémoire]\n- Davy est distributeur MLM")
        asyncio.run(llm.reply("bonjour", session_id="s1"))

        system_content = captured["messages"][0]["content"]
        self.assertIn("Base.", system_content)
        self.assertIn("[Mémoire]", system_content)

    def test_load_project_injected_and_separate_from_memory(self):
        captured = {}

        async def fake(messages):
            captured["messages"] = list(messages)
            return "ok"

        llm = MistralLLM(transport=fake, system_prompt="Base.")
        llm.load_memory("s1", "[Mémoire]\n- fait")
        llm.load_project("s1", "[Projet]\n- doc.txt")
        asyncio.run(llm.reply("salut", session_id="s1"))

        system_content = captured["messages"][0]["content"]
        self.assertIn("[Mémoire]", system_content)
        self.assertIn("[Projet]", system_content)
        # Désactiver le projet n'efface pas la mémoire.
        llm.load_project("s1", "")
        asyncio.run(llm.reply("encore", session_id="s1"))
        sc2 = captured["messages"][0]["content"]
        self.assertIn("[Mémoire]", sc2)
        self.assertNotIn("[Projet]", sc2)

    def test_unload_memory_clears_context_and_history(self):
        async def fake(messages):
            return "ok"

        llm = MistralLLM(transport=fake, system_prompt=None)
        llm.load_memory("s1", "contexte")
        asyncio.run(llm.reply("test", session_id="s1"))
        llm.unload_memory("s1")

        self.assertEqual(llm.get_history("s1"), [])
        self.assertNotIn("s1", llm._memory_context)

    def test_get_history_returns_accumulated_turns(self):
        async def fake(messages):
            return "r"

        llm = MistralLLM(transport=fake, system_prompt=None)
        asyncio.run(llm.reply("q1", session_id="s1"))
        asyncio.run(llm.reply("q2", session_id="s1"))

        h = llm.get_history("s1")
        self.assertEqual(len(h), 4)  # user, assistant, user, assistant
        self.assertEqual(h[0], {"role": "user", "content": "q1"})
        self.assertEqual(h[1], {"role": "assistant", "content": "r"})

    def test_without_transport_fails_fast(self):
        # Pas de transport injecté + ni lib ni clé en CI → erreur claire, pas un crash obscur.
        with self.assertRaises(RuntimeError):
            asyncio.run(MistralLLM().reply("x", session_id="s1"))


class VoxtralSTTTest(unittest.TestCase):
    def test_uses_transport_with_audio_and_locale(self):
        seen = {}

        async def fake(audio, locale):
            seen["audio"] = audio
            seen["locale"] = locale
            return "transcription-mock"

        stt = VoxtralSTT(transport=fake)
        out = asyncio.run(stt.transcribe(b"PCM", "fr-FR"))

        self.assertEqual(out, "transcription-mock")
        self.assertEqual(seen, {"audio": b"PCM", "locale": "fr-FR"})

    def test_without_transport_fails_fast(self):
        with self.assertRaises(RuntimeError):
            asyncio.run(VoxtralSTT().transcribe(b"PCM", "fr-FR"))


class CallableTTSTest(unittest.TestCase):
    def test_delegates_to_transport(self):
        async def fake(text, locale):
            return b"AUDIO:" + text.encode() + b":" + locale.encode()

        out = asyncio.run(CallableTTS(fake).synthesize("salut", "fr-FR"))
        self.assertEqual(out, b"AUDIO:salut:fr-FR")


class AdaptersIntoRuntimeTest(unittest.TestCase):
    """Le vrai test d'intégration : les 3 adaptateurs branchés dans le runtime."""

    def test_full_pipeline_with_real_adapters(self):
        async def fake_stt(audio, locale):
            return f"dit en {locale}"

        async def fake_llm(messages):
            return "réponse(" + messages[-1]["content"] + ")"

        async def fake_tts(text, locale):
            return b"SPEECH:" + text.encode()

        played = []

        class RoomOut:
            async def play(self, audio):
                played.append(audio)

        events = []
        rt = ConversationRuntime(
            VoxtralSTT(transport=fake_stt),
            MistralLLM(transport=fake_llm),
            CallableTTS(fake_tts),
            audit=lambda sid, ev, payload: events.append((sid, ev)),
        )

        async def scenario():
            desc = SessionDescriptor(
                "s1", "t1", "room-a", member_id="m1", consent_granted=True
            )
            await rt.open(desc, RoomOut())
            await rt.handle("s1", b"PCM")

        asyncio.run(scenario())

        self.assertEqual(len(played), 1)
        expected = b"SPEECH:" + "réponse(dit en fr-FR)".encode()
        self.assertEqual(played[0], expected)
        self.assertIn(("s1", "transcript"), events)
        self.assertIn(("s1", "reply"), events)


class MistralLLMToolUseTest(unittest.TestCase):
    """Boucle function-calling : le LLM appelle un outil puis répond en clair."""

    def test_tool_call_then_final_answer(self):
        from shared.agent.tools import ToolRegistry, WebSearchTool

        searched = {}

        async def fake_search(query, n):
            searched["query"] = query
            return [{"title": "Résultat", "url": "https://x", "snippet": "info"}]

        tools = ToolRegistry([WebSearchTool(transport=fake_search)])

        # Transport tool-aware scripté : 1er appel → demande l'outil ; 2e → réponse.
        calls = {"n": 0}

        async def fake_tool_transport(messages, specs):
            calls["n"] += 1
            if calls["n"] == 1:
                self.assertTrue(specs)  # les specs sont bien transmises
                return {
                    "content": None,
                    "tool_calls": [
                        {"id": "c1", "name": "web_search", "arguments": '{"query": "actu"}'}
                    ],
                    "assistant": {"role": "assistant", "content": ""},
                }
            # 2e tour : le message tool est présent dans l'historique de travail.
            roles = [m["role"] for m in messages]
            self.assertIn("tool", roles)
            return {"content": "Voici l'info trouvée.", "tool_calls": []}

        llm = MistralLLM(tools=tools, tool_transport=fake_tool_transport)
        out = asyncio.run(llm.reply("quoi de neuf ?", session_id="s1"))

        self.assertEqual(out, "Voici l'info trouvée.")
        self.assertEqual(searched["query"], "actu")
        self.assertEqual(calls["n"], 2)
        # L'historique long-terme ne contient QUE le tour user + réponse finale.
        history = llm.get_history("s1")
        self.assertEqual(history, [
            {"role": "user", "content": "quoi de neuf ?"},
            {"role": "assistant", "content": "Voici l'info trouvée."},
        ])

    def test_no_tool_call_returns_directly(self):
        from shared.agent.tools import ToolRegistry, WebSearchTool

        async def fake_search(query, n):  # pragma: no cover - pas appelé ici
            return []

        async def fake_tool_transport(messages, specs):
            return {"content": "Réponse directe.", "tool_calls": []}

        llm = MistralLLM(
            tools=ToolRegistry([WebSearchTool(transport=fake_search)]),
            tool_transport=fake_tool_transport,
        )
        out = asyncio.run(llm.reply("bonjour", session_id="s1"))
        self.assertEqual(out, "Réponse directe.")

    def test_hop_limit_forces_final_answer(self):
        from shared.agent.tools import ToolRegistry, WebSearchTool

        async def fake_search(query, n):
            return [{"title": "t", "url": "https://x", "snippet": "s"}]

        # Transport qui demande TOUJOURS l'outil → on doit s'arrêter au garde-fou.
        async def loopy(messages, specs):
            if specs:  # tant qu'on lui propose des outils, il en redemande
                return {
                    "content": None,
                    "tool_calls": [
                        {"id": "c", "name": "web_search", "arguments": '{"query": "x"}'}
                    ],
                    "assistant": {"role": "assistant", "content": ""},
                }
            return {"content": "Réponse forcée.", "tool_calls": []}

        llm = MistralLLM(
            tools=ToolRegistry([WebSearchTool(transport=fake_search)]),
            tool_transport=loopy,
            max_tool_hops=2,
        )
        out = asyncio.run(llm.reply("cherche", session_id="s1"))
        self.assertEqual(out, "Réponse forcée.")


if __name__ == "__main__":
    unittest.main()
