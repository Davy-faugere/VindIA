import unittest

from shared.agent.ids import is_valid_id, new_id


class IdsTest(unittest.TestCase):
    def test_new_id_is_char36(self):
        i = new_id()
        self.assertEqual(len(i), 36)
        self.assertTrue(is_valid_id(i))

    def test_new_id_unique(self):
        self.assertNotEqual(new_id(), new_id())

    def test_invalid_ids_rejected(self):
        for bad in ["", "x", "1234", 1234, None, "g" * 36, new_id().replace("-", "")]:
            self.assertFalse(is_valid_id(bad))


if __name__ == "__main__":
    unittest.main()
