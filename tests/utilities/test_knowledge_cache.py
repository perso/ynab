import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ynab.utilities.knowledge_cache import load_server_knowledge, save_server_knowledge


class TestKnowledgeCache(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = TemporaryDirectory()
        self.cache_path = Path(self._tmpdir.name) / "server_knowledge.json"

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_load_returns_none_when_file_missing(self):
        result = load_server_knowledge("b1", "a1", self.cache_path)
        self.assertIsNone(result)

    def test_save_and_load_round_trip(self):
        save_server_knowledge("b1", "a1", 42, self.cache_path)
        result = load_server_knowledge("b1", "a1", self.cache_path)
        self.assertEqual(42, result)

    def test_separate_keys_do_not_collide(self):
        save_server_knowledge("b1", "a1", 10, self.cache_path)
        save_server_knowledge("b1", "a2", 20, self.cache_path)
        self.assertEqual(10, load_server_knowledge("b1", "a1", self.cache_path))
        self.assertEqual(20, load_server_knowledge("b1", "a2", self.cache_path))

    def test_save_overwrites_existing_value(self):
        save_server_knowledge("b1", "a1", 1, self.cache_path)
        save_server_knowledge("b1", "a1", 999, self.cache_path)
        self.assertEqual(999, load_server_knowledge("b1", "a1", self.cache_path))

    def test_save_creates_parent_directories(self):
        nested_path = Path(self._tmpdir.name) / "nested" / "dir" / "cache.json"
        save_server_knowledge("b1", "a1", 5, nested_path)
        self.assertTrue(nested_path.exists())

    def test_load_returns_none_for_unknown_key(self):
        save_server_knowledge("b1", "a1", 7, self.cache_path)
        result = load_server_knowledge("b2", "a2", self.cache_path)
        self.assertIsNone(result)

    def test_load_returns_none_for_corrupt_cache(self):
        self.cache_path.write_text("not valid json")
        result = load_server_knowledge("b1", "a1", self.cache_path)
        self.assertIsNone(result)

    def test_save_preserves_other_keys_when_updating(self):
        save_server_knowledge("b1", "a1", 10, self.cache_path)
        save_server_knowledge("b1", "a2", 20, self.cache_path)
        save_server_knowledge("b1", "a1", 99, self.cache_path)
        # a2 must be untouched
        self.assertEqual(20, load_server_knowledge("b1", "a2", self.cache_path))

    def test_cache_file_is_valid_json(self):
        save_server_knowledge("b1", "a1", 42, self.cache_path)
        data = json.loads(self.cache_path.read_text())
        self.assertIsInstance(data, dict)
