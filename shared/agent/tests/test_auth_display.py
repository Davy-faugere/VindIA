"""Le prénom saisi à l'inscription doit être celui qu'on affiche.

Bug réellement survenu (24/08/2026) : le formulaire d'inscription demande bien prénom,
nom, adresse, mot de passe et confirmation, et le prénom part correctement dans
Supabase — mais la route /auth l'ignorait une fois le compte approuvé et retombait
toujours sur le début de l'adresse. VindIA accueillait donc « Bonjour faugredavy »,
y compris les personnes qui avaient renseigné leur prénom.

Sans prénom (comptes créés avant que le formulaire le demande), on n'affiche rien :
mieux vaut pas de nom qu'un pseudo fabriqué à partir de l'adresse.
"""

import asyncio
import os
import tempfile
import unittest

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

MEMBRE = "00000000-0000-0000-0000-00000000d15a"


def _app(tmp, *, prenom, approuve):
    os.environ["VINDIA_DATA_DIR"] = tmp
    import importlib

    import web.server as s
    importlib.reload(s)
    app = s.build_app()

    class AuthDouble:
        async def verify(self, token):
            return {"member_id": MEMBRE, "email": "faugredavy@exemple.fr",
                    "admin": False, "prenom": prenom, "nom": ""}

    s._init_services()
    s._auth = AuthDouble()
    s._approvals.request(MEMBRE, "faugredavy@exemple.fr")
    if approuve:
        s._approvals.decide(MEMBRE, True)
    return app


def _auth(app):
    async def run():
        async with TestClient(TestServer(app)) as client:
            r = await client.post("/auth", headers={"Authorization": "Bearer jeton"})
            return await r.json()
    return asyncio.run(run())


@unittest.skipUnless(_APP_DISPONIBLE, "dépendances runtime absentes — job CI sans dépendance")
class AuthDisplayTest(unittest.TestCase):
    def test_le_prenom_saisi_est_affiche(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = _auth(_app(tmp, prenom="Jeconias", approuve=True))
            self.assertEqual(d.get("display_name"), "Jeconias")

    def test_sans_prenom_on_n_invente_pas_de_pseudo(self):
        # Le cœur du bug : « Bonjour faugredavy » n'appelle personne par son nom.
        with tempfile.TemporaryDirectory() as tmp:
            d = _auth(_app(tmp, prenom="", approuve=True))
            self.assertEqual(d.get("display_name"), "")
            self.assertNotIn("faugredavy", str(d.get("display_name")))

    def test_meme_regle_avant_validation_du_compte(self):
        # Les deux chemins de /auth doivent se comporter pareil, sinon le nom change
        # au moment de l'approbation.
        with tempfile.TemporaryDirectory() as tmp:
            d = _auth(_app(tmp, prenom="Patrice", approuve=False))
            self.assertFalse(d.get("approved"))
            self.assertEqual(d.get("display_name"), "Patrice")


if __name__ == "__main__":
    unittest.main()
