import tempfile
import unittest
from pathlib import Path

from rag_generator.store import ConfigurationStore


class StoreTests(unittest.TestCase):
    def test_configuration_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigurationStore(Path(directory) / "configs.db")
            identifier = store.save("demo", {"project_name": "demo"})
            self.assertEqual(store.get(identifier)["selection"]["project_name"], "demo")
            self.assertEqual(len(store.list()), 1)
            self.assertTrue(store.delete(identifier))
            self.assertIsNone(store.get(identifier))
