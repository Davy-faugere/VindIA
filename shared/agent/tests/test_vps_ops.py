"""Tests du connecteur VPS — offline, transport mocké, 0 réseau.

Prouve : les 2 outils lecture seule formatent bien la réponse, et que SEULS la
santé et l'état de service sont exposés (aucun outil d'action).
"""

import asyncio
import unittest

from shared.agent.tools import ToolRegistry
from shared.agent.vps_ops import VpsHealthTool, VpsServiceStatusTool


class VpsToolsTest(unittest.TestCase):
    def test_health_summarized(self):
        async def fake(path, params):
            self.assertEqual(path, "/ops/health")
            return {"status": "ok", "allowed_services": ["nginx", "n8n"]}

        out = asyncio.run(VpsHealthTool(fake).run({}))
        self.assertIn("ok", out)
        self.assertIn("nginx", out)

    def test_service_status_passes_param(self):
        captured = {}

        async def fake(path, params):
            captured.update(path=path, params=params)
            return {"service": "nginx", "active": "active", "since": "6 days"}

        out = asyncio.run(VpsServiceStatusTool(fake).run({"service": "nginx"}))
        self.assertEqual(captured["path"], "/ops/systemctl-status")
        self.assertEqual(captured["params"], {"service": "nginx"})
        self.assertIn("active", out)

    def test_service_status_empty(self):
        async def fake(path, params):  # pragma: no cover - pas appelé
            raise AssertionError("ne doit pas être appelé")

        out = asyncio.run(VpsServiceStatusTool(fake).run({"service": "  "}))
        self.assertIn("manquant", out)

    def test_service_status_swallows_api_error(self):
        async def fake(path, params):
            raise RuntimeError("403 service non autorisé")

        out = asyncio.run(VpsServiceStatusTool(fake).run({"service": "wazuh-manager"}))
        self.assertIn("Impossible", out)

    def test_only_readonly_tools_exposed(self):
        async def fake(path, params):
            return {}

        reg = ToolRegistry([VpsHealthTool(fake), VpsServiceStatusTool(fake)])
        names = {s["function"]["name"] for s in reg.specs()}
        self.assertEqual(names, {"vps_health", "vps_service_status"})
        # Aucun outil d'action (restart/reload/file-read) n'existe.
        self.assertFalse({"vps_restart", "vps_reload", "vps_file_read"} & names)


if __name__ == "__main__":
    unittest.main()
