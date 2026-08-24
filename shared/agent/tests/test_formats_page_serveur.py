"""La page et le serveur doivent s'accorder sur les formats.

Bug réellement survenu (24/08/2026) : le serveur savait construire des .odt et des .ods,
mais la page gardait sa PROPRE liste fermée — ['docx','xlsx','pptx','pdf']. Un .odt
demandé n'était donc jamais envoyé au serveur : la page fabriquait un fichier texte
contenant le markdown brut, sous un nom de fichier bureautique. LibreOffice ouvrait le
classeur dans Writer, avec « # Titre » et « **gras** » en clair.

Deux listes de formats, deux autorités, et rien pour signaler leur divergence. La page
raisonne désormais sur les formats TEXTE (liste ouverte : tout le reste part au serveur).
Ces tests verrouillent l'invariant, sans lancer de navigateur : ils lisent le fichier.
"""

import pathlib
import re
import unittest

from shared.agent.officegen import TEXT_TYPES, formats_supportes

PAGE = pathlib.Path(__file__).resolve().parents[3] / "web" / "index.html"


def _liste_texte_de_la_page():
    """Extensions que la page livre elle-même, sans passer par le serveur."""
    source = PAGE.read_text(encoding="utf-8")
    bloc = re.search(r"const TEXTE = \{(.*?)\};", source, re.S)
    if not bloc:
        raise AssertionError("la page ne déclare plus de liste TEXTE — invariant à revoir")
    return set(re.findall(r"(\w+):\s*'", bloc.group(1)))


@unittest.skipUnless(PAGE.is_file(), "web/index.html introuvable")
class FormatsPageServeurTest(unittest.TestCase):
    def test_aucun_format_construit_n_est_traite_comme_du_texte(self):
        # Le cœur du bug : .odt était absent des deux côtés du serveur, donc traité
        # comme du texte brut. Un format que le serveur CONSTRUIT ne doit jamais être
        # livré tel quel par la page.
        construits = set(formats_supportes()) - set(TEXT_TYPES)
        collision = construits & _liste_texte_de_la_page()
        self.assertEqual(
            collision, set(),
            f"la page livrerait en texte brut des formats que le serveur construit : {sorted(collision)}",
        )

    def test_la_page_ne_referme_pas_la_liste_des_binaires(self):
        # Une liste fermée de formats bureautiques côté page est exactement ce qui a
        # causé le bug : elle se désynchronise du serveur en silence.
        source = PAGE.read_text(encoding="utf-8")
        self.assertNotIn(
            "const OFFICE =", source,
            "la page redéclare une liste fermée de formats bureautiques — "
            "elle doit raisonner sur les formats TEXTE et envoyer le reste au serveur",
        )

    def test_odt_et_ods_partent_bien_au_serveur(self):
        # Vérification directe du cas signalé, pour qu'un futur remaniement ne le
        # réintroduise pas par un autre chemin.
        page = _liste_texte_de_la_page()
        for ext in ("odt", "ods", "docx", "xlsx", "pptx", "pdf"):
            with self.subTest(ext=ext):
                self.assertNotIn(ext, page)
                self.assertIn(ext, formats_supportes())


if __name__ == "__main__":
    unittest.main()
