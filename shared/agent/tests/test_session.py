import unittest

from shared.agent.session import SessionDescriptor


class SessionDescriptorTest(unittest.TestCase):
    def test_cannot_process_without_consent(self):
        d = SessionDescriptor("s1", "t1", "room", member_id="m1", consent_granted=False)
        self.assertFalse(d.can_process())

    def test_cannot_process_without_member(self):
        d = SessionDescriptor("s1", "t1", "room", member_id=None, consent_granted=True)
        self.assertFalse(d.can_process())

    def test_can_process_with_consent_and_member(self):
        d = SessionDescriptor("s1", "t1", "room", member_id="m1", consent_granted=True)
        self.assertTrue(d.can_process())

    def test_with_member_preserves_other_fields(self):
        d = SessionDescriptor("s1", "t1", "room", consent_granted=True, locale="en-US")
        d2 = d.with_member("m9")
        self.assertEqual(d2.member_id, "m9")
        self.assertEqual(d2.locale, "en-US")
        self.assertTrue(d2.consent_granted)
        self.assertIsNone(d.member_id)  # immutabilité de l'original


if __name__ == "__main__":
    unittest.main()
