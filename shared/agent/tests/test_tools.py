"""Tests des outils web — 100 % offline, 0 dépendance, 0 réseau.

Chaque outil reçoit un `transport` fake : on prouve le format de sortie, le
garde-fou SSRF, le bornage des résultats et la tolérance aux pannes du registre.
"""

import asyncio
import unittest

from shared.agent.tools import (
    ToolRegistry,
    ToolSpec,
    WebFetchTool,
    WebSearchTool,
    html_to_text,
    validate_fetch_url,
)


class HtmlToTextTest(unittest.TestCase):
    def test_strips_tags_scripts_styles(self):
        html = (
            "<html><head><style>.x{color:red}</style></head>"
            "<body><script>alert(1)</script>"
            "<h1>Titre</h1><p>Bonjour le <b>monde</b>.</p></body></html>"
        )
        out = html_to_text(html)
        self.assertIn("Titre", out)
        self.assertIn("Bonjour le monde", out)
        self.assertNotIn("alert", out)
        self.assertNotIn("color:red", out)

    def test_collapses_whitespace(self):
        out = html_to_text("<p>a</p>\n\n\n<p>b</p>")
        self.assertEqual(out, "a\nb")

    def test_broken_html_does_not_raise(self):
        self.assertIsInstance(html_to_text("<p>unclosed <b>oops"), str)

    def test_empty(self):
        self.assertEqual(html_to_text(""), "")


class ValidateFetchUrlTest(unittest.TestCase):
    def test_allows_public_https(self):
        self.assertIsNone(validate_fetch_url("https://example.com/article"))
        self.assertIsNone(validate_fetch_url("http://www.lemonde.fr/page"))

    def test_rejects_non_http_scheme(self):
        self.assertIsNotNone(validate_fetch_url("file:///etc/passwd"))
        self.assertIsNotNone(validate_fetch_url("ftp://example.com"))
        self.assertIsNotNone(validate_fetch_url("gopher://x"))

    def test_rejects_localhost_and_private_ips(self):
        for url in (
            "http://localhost/admin",
            "http://127.0.0.1:8092/",
            "http://[::1]/",
            "http://10.0.0.5/",
            "http://192.168.1.1/",
            "http://172.16.0.1/",
            "http://169.254.169.254/latest/meta-data/",  # AWS metadata
            "http://metadata.google.internal/",
        ):
            with self.subTest(url=url):
                self.assertIsNotNone(validate_fetch_url(url), url)

    def test_rejects_empty_and_hostless(self):
        self.assertIsNotNone(validate_fetch_url(""))
        self.assertIsNotNone(validate_fetch_url("https://"))


class WebSearchToolTest(unittest.TestCase):
    def test_formats_results_and_bounds_count(self):
        async def fake(query, n):
            self.assertEqual(query, "météo Paris")
            return [
                {"title": "T1", "url": "https://a", "snippet": "s1"},
                {"title": "T2", "url": "https://b", "snippet": "s2"},
                {"title": "T3", "url": "https://c", "snippet": "s3"},
            ]

        tool = WebSearchTool(transport=fake, max_results=2)
        out = asyncio.run(tool.run({"query": "météo Paris"}))
        self.assertIn("1. T1", out)
        self.assertIn("https://a", out)
        self.assertIn("2. T2", out)
        self.assertNotIn("T3", out)  # borné à max_results

    def test_empty_query_short_circuits(self):
        async def fake(query, n):  # pragma: no cover - ne doit pas être appelé
            raise AssertionError("transport ne doit pas être appelé")

        out = asyncio.run(WebSearchTool(transport=fake).run({"query": "   "}))
        self.assertIn("vide", out)

    def test_no_results_message(self):
        async def fake(query, n):
            return []

        out = asyncio.run(WebSearchTool(transport=fake).run({"query": "xyz"}))
        self.assertIn("Aucun résultat", out)


class WebFetchToolTest(unittest.TestCase):
    def test_fetches_and_truncates(self):
        async def fake(url):
            self.assertEqual(url, "https://example.com/a")
            return "x" * 5000

        out = asyncio.run(WebFetchTool(transport=fake, max_chars=100).run({"url": "https://example.com/a"}))
        self.assertTrue(out.endswith("[…]"))
        self.assertLessEqual(len(out), 110)

    def test_blocks_ssrf_before_transport(self):
        async def fake(url):  # pragma: no cover - ne doit jamais être atteint
            raise AssertionError("le transport ne doit pas être appelé sur une URL interne")

        out = asyncio.run(WebFetchTool(transport=fake).run({"url": "http://169.254.169.254/"}))
        self.assertIn("refusée", out)

    def test_empty_content_message(self):
        async def fake(url):
            return "   "

        out = asyncio.run(WebFetchTool(transport=fake).run({"url": "https://example.com"}))
        self.assertIn("aucun contenu", out)


class ToolRegistryTest(unittest.TestCase):
    def _registry(self):
        async def search(query, n):
            return [{"title": "T", "url": "https://x", "snippet": "s"}]

        return ToolRegistry([WebSearchTool(transport=search)])

    def test_specs_are_mistral_shaped(self):
        specs = self._registry().specs()
        self.assertEqual(specs[0]["type"], "function")
        self.assertEqual(specs[0]["function"]["name"], "web_search")
        self.assertIn("query", specs[0]["function"]["parameters"]["properties"])

    def test_dispatch_accepts_json_string_arguments(self):
        out = asyncio.run(self._registry().dispatch("web_search", '{"query": "test"}'))
        self.assertIn("https://x", out)

    def test_dispatch_accepts_dict_arguments(self):
        out = asyncio.run(self._registry().dispatch("web_search", {"query": "test"}))
        self.assertIn("https://x", out)

    def test_dispatch_unknown_tool(self):
        out = asyncio.run(self._registry().dispatch("nope", {}))
        self.assertIn("inconnu", out)

    def test_dispatch_bad_json_arguments(self):
        out = asyncio.run(self._registry().dispatch("web_search", "{not json"))
        self.assertIn("illisibles", out)

    def test_dispatch_swallows_tool_exception(self):
        class Boom(WebSearchTool):
            async def run(self, args):
                raise ValueError("kaboom")

        async def s(q, n):
            return []

        reg = ToolRegistry([Boom(transport=s)])
        out = asyncio.run(reg.dispatch("web_search", {"query": "x"}))
        self.assertIn("kaboom", out)

    def test_registry_truthiness(self):
        self.assertFalse(ToolRegistry())
        self.assertTrue(self._registry())


if __name__ == "__main__":
    unittest.main()
