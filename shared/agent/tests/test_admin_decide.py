"""La route qui ouvre un accès depuis l'écran Administration — testée en vrai.

Bug réellement survenu (21→24/08/2026) : le bouton « Approuver » ne faisait rien
d'utile. Le serveur refusait avec un 409 « adresse jamais confirmée » alors que la
personne AVAIT confirmé chez Supabase — le drapeau local ne se posant qu'au premier
passage dans l'application. Des comptes légitimes étaient donc impossibles à valider.

Ces tests montent l'application réelle et appellent la route, plutôt que de supposer
qu'elle répond bien.
"""

import asyncio
import os
import tempfile
import unittest

# La CI « stdlib, 0 dépendance » n'installe rien : ce test monte l'application réelle,
# il a donc besoin d'aiohttp. Il s'exécute avant chaque livraison via
# ./scripts/verifier.sh (venv complet) et se saute proprement en intégration continue.
# On vérifie l'application ENTIÈRE, pas seulement aiohttp : web.server tire aussi
# livekit et edge-tts, absents d'un environnement sans dépendances.
# Les variables sont posées AVANT l'import : web.server en lit à la charge, et leur
# absence ferait sauter ces tests jusque dans le venv complet — ils ne protégeraient
# alors plus rien.
for _cle, _valeur in (
    ("SUPABASE_URL", "https://exemple.supabase.co"),
    ("SUPABASE_ANON_KEY", "anon"),
    ("LIVEKIT_URL", "wss://exemple.livekit.cloud"),
    ("LIVEKIT_API_KEY", "cle-test"),
    ("LIVEKIT_API_SECRET", "secret-test"),
):
    os.environ.setdefault(_cle, _valeur)

try:
    from aiohttp.test_utils import TestClient, TestServer
    import web.server  # noqa: F401
    _APP_DISPONIBLE = True
except Exception:  # pragma: no cover - dépend de l'environnement
    _APP_DISPONIBLE = False

ADMIN = "00000000-0000-0000-0000-0000000000ad"
CIBLE = "00000000-0000-0000-0000-00000000c1b1"


def _app(tmp, *, email_confirme_retour):
    """Application réelle, avec l'auth et le stockage remplacés par des doublures."""
    # Le test ne doit dépendre d'AUCUN fichier .env : sinon il passe sur la machine de
    # développement et casse en intégration continue, où rien n'est configuré.
    os.environ["VINDIA_DATA_DIR"] = tmp
    for cle, valeur in (
        ("SUPABASE_URL", "https://exemple.supabase.co"),
        ("SUPABASE_ANON_KEY", "anon"),
        ("LIVEKIT_URL", "wss://exemple.livekit.cloud"),
        ("LIVEKIT_API_KEY", "cle-test"),
        ("LIVEKIT_API_SECRET", "secret-test"),
    ):
        os.environ.setdefault(cle, valeur)
    import importlib

    import web.server as s
    importlib.reload(s)
    app = s.build_app()

    class AuthDouble:
        async def verify(self, token):
            return {"member_id": ADMIN, "email": "admin@exemple.fr", "admin": True,
                    "prenom": "", "nom": ""}

        async def email_confirme(self, member_id):
            return email_confirme_retour

    s._init_services()
    s._auth = AuthDouble()
    # La cible : inscrite, en attente, jamais repassée dans l'application.
    s._approvals.request(CIBLE, "cible@exemple.fr")
    return app, s


def _decide(app):
    async def run():
        async with TestClient(TestServer(app)) as client:
            r = await client.post("/admin/decide",
                                  json={"member_id": CIBLE, "approve": True},
                                  headers={"Authorization": "Bearer jeton-admin"})
            return r.status, await r.json()
    return asyncio.run(run())


@unittest.skipUnless(_APP_DISPONIBLE, "dépendances runtime absentes — job CI sans dépendance")
class AdminDecideTest(unittest.TestCase):
    def test_ouvre_l_acces_quand_supabase_confirme_l_adresse(self):
        with tempfile.TemporaryDirectory() as tmp:
            app, s = _app(tmp, email_confirme_retour=True)
            status, body = _decide(app)
            self.assertEqual(status, 200, body)
            self.assertTrue(body.get("ok"), body)
            self.assertEqual(body.get("decision"), "approved")

    def test_ouvre_l_acces_quand_la_verification_est_indisponible(self):
        # Sans clé de service on ne SAIT pas. Refuser ici condamnait des comptes
        # légitimes : on ouvre, mais on prévient l'administrateur.
        with tempfile.TemporaryDirectory() as tmp:
            app, s = _app(tmp, email_confirme_retour=None)
            status, body = _decide(app)
            self.assertEqual(status, 200, body)
            self.assertTrue(body.get("ok"), body)
            self.assertIn("non vérifiée", body.get("avertissement", ""))

    def test_refuse_quand_supabase_dit_adresse_non_confirmee(self):
        # Preuve négative : là, le garde-fou doit tenir.
        with tempfile.TemporaryDirectory() as tmp:
            app, s = _app(tmp, email_confirme_retour=False)
            status, body = _decide(app)
            self.assertEqual(status, 409, body)
            self.assertTrue(body.get("adresse_non_confirmee"))


if __name__ == "__main__":
    unittest.main()
