"""Tests de la validation humaine des comptes — offline, tmpdir."""

import tempfile
import unittest

from shared.agent.approvals import ApprovalStore, PENDING, APPROVED, REFUSED

ALICE = "00000001-0001-0001-0002-000000000001"
BOB = "00000001-0001-0001-0003-000000000001"


def _store(tmp):
    return ApprovalStore(tmp, clock=lambda: "2026-06-28T00:00:00+00:00")


class ApprovalTest(unittest.TestCase):
    def test_first_request_is_pending_and_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = _store(tmp)
            status, is_new = s.request(ALICE, "alice@x.com")
            self.assertEqual(status, PENDING)
            self.assertTrue(is_new)

    def test_second_request_not_new_keeps_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = _store(tmp)
            s.request(ALICE, "alice@x.com")
            status, is_new = s.request(ALICE, "alice@x.com")
            self.assertEqual(status, PENDING)
            self.assertFalse(is_new)  # pas de re-notification

    def test_approve_then_request_returns_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = _store(tmp)
            s.request(ALICE, "a@x.com")
            self.assertTrue(s.decide(ALICE, True))
            self.assertEqual(s.status(ALICE), APPROVED)
            status, is_new = s.request(ALICE, "a@x.com")
            self.assertEqual(status, APPROVED)
            self.assertFalse(is_new)

    def test_refuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = _store(tmp)
            s.request(ALICE, "a@x.com")
            s.decide(ALICE, False)
            self.assertEqual(s.status(ALICE), REFUSED)

    def test_decide_unknown_member_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            # UUID valide mais jamais enregistré → decide ne fait rien.
            self.assertFalse(_store(tmp).decide("00000000-0000-0000-0000-000000000999", True))

    def test_status_unknown_for_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(_store(tmp).status(ALICE), "unknown")

    def test_list_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = _store(tmp)
            s.request(ALICE, "a@x.com")
            s.request(BOB, "b@x.com")
            s.decide(BOB, True)
            pend = s.list_by_status(PENDING)
            self.assertEqual([r["member_id"] for r in pend], [ALICE])
            self.assertEqual(len(s.list_by_status(APPROVED)), 1)

    def test_invalid_member_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                _store(tmp).request("../evil", "x")


if __name__ == "__main__":
    unittest.main()


class AdresseConfirmeeTest(unittest.TestCase):
    """Garde-fou : on n'ouvre pas un accès à une adresse jamais prouvée."""

    MID = "11111111-2222-3333-4444-555555555555"

    def _store(self, tmp):
        return ApprovalStore(tmp, clock=lambda: "2026-08-21T10:00:00")

    def test_inscription_part_non_confirmee(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self._store(tmp)
            a.request(self.MID, "inconnu@exemple.fr")
            self.assertFalse(a.adresse_confirmee(self.MID))

    def test_connexion_prouve_l_adresse(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self._store(tmp)
            a.request(self.MID, "vrai@exemple.fr")
            self.assertTrue(a.marquer_adresse_confirmee(self.MID))
            self.assertTrue(a.adresse_confirmee(self.MID))

    def test_marquage_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self._store(tmp)
            a.request(self.MID, "x@exemple.fr")
            a.marquer_adresse_confirmee(self.MID)
            self.assertFalse(a.marquer_adresse_confirmee(self.MID))   # déjà fait

    def test_membre_inconnu_n_est_pas_confirme(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self._store(tmp)
            # Un dossier absent ne doit pas être pris pour un compte vérifié.
            self.assertFalse(a.adresse_confirmee(self.MID))
            self.assertFalse(a.marquer_adresse_confirmee(self.MID))

    def test_le_drapeau_survit_a_la_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = self._store(tmp)
            a.request(self.MID, "x@exemple.fr")
            a.marquer_adresse_confirmee(self.MID)
            a.decide(self.MID, True)
            self.assertTrue(a.adresse_confirmee(self.MID))
