import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mts.config import AppConfig, load_config
from mts.constants import DEFAULT_PARAM_GRABBED, DEFAULT_PARAM_STRETCH


class ConfigTestCase(unittest.TestCase):
    """Redirects CONFIG_FILE to a scratch dir so tests never touch the real config.json."""

    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.config_path = Path(self.tmp_dir.name) / "config.json"
        patcher = patch("mts.config.CONFIG_FILE", str(self.config_path))
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_config(self, data):
        self.config_path.write_text(json.dumps(data))


class LoadConfigTests(ConfigTestCase):
    def test_missing_file_returns_defaults_with_no_error(self):
        cfg, error = load_config()
        self.assertIsNone(error)
        self.assertEqual(cfg, AppConfig())
        self.assertFalse(cfg.is_complete)

    def test_valid_file_loads_all_fields(self):
        self.write_config({
            "api_key": "key123",
            "shocker_ids": ["a", "b"],
            "shocker_mode": "Random",
            "param_grabbed": "/custom/grab",
            "param_stretch": "/custom/stretch",
        })
        cfg, error = load_config()
        self.assertIsNone(error)
        self.assertEqual(cfg.api_key, "key123")
        self.assertEqual(cfg.shocker_ids, ["a", "b"])
        self.assertEqual(cfg.shocker_mode, "Random")
        self.assertEqual(cfg.param_grabbed, "/custom/grab")
        self.assertEqual(cfg.param_stretch, "/custom/stretch")
        self.assertTrue(cfg.is_complete)

    def test_corrupt_file_reports_parse_error(self):
        self.config_path.write_text("{not valid json")
        cfg, error = load_config()
        self.assertEqual(error, "parse_error")
        self.assertEqual(cfg, AppConfig())

    def test_blank_osc_params_fall_back_to_defaults(self):
        self.write_config({"api_key": "k", "shocker_ids": ["a"], "param_grabbed": "", "param_stretch": ""})
        cfg, _ = load_config()
        self.assertEqual(cfg.param_grabbed, DEFAULT_PARAM_GRABBED)
        self.assertEqual(cfg.param_stretch, DEFAULT_PARAM_STRETCH)

    def test_single_shocker_id_forces_all_mode(self):
        self.write_config({"api_key": "key", "shocker_ids": ["only-one"], "shocker_mode": "Random"})
        cfg, _ = load_config()
        self.assertEqual(cfg.shocker_mode, "All")

    def test_multiple_shocker_ids_keep_requested_mode(self):
        self.write_config({"api_key": "key", "shocker_ids": ["a", "b"], "shocker_mode": "Random"})
        cfg, _ = load_config()
        self.assertEqual(cfg.shocker_mode, "Random")

    def test_legacy_shocker_id_is_migrated_and_persisted(self):
        self.write_config({"api_key": "key", "shocker_ids": [], "shocker_id": "legacy-id"})
        cfg, _ = load_config()
        self.assertIn("legacy-id", cfg.shocker_ids)
        on_disk = json.loads(self.config_path.read_text())
        self.assertIn("legacy-id", on_disk["shocker_ids"])

    def test_legacy_shocker_id_not_duplicated_if_already_present(self):
        self.write_config({"api_key": "key", "shocker_ids": ["legacy-id"], "shocker_id": "legacy-id"})
        cfg, _ = load_config()
        self.assertEqual(cfg.shocker_ids.count("legacy-id"), 1)


class SaveConfigTests(ConfigTestCase):
    def test_save_writes_all_fields_as_json(self):
        cfg = AppConfig(api_key="abc", shocker_ids=["x", "y"], shocker_mode="All")
        cfg.save()
        on_disk = json.loads(self.config_path.read_text())
        self.assertEqual(on_disk["api_key"], "abc")
        self.assertEqual(on_disk["shocker_ids"], ["x", "y"])
        self.assertEqual(on_disk["shocker_mode"], "All")

    def test_round_trip_through_save_and_load(self):
        AppConfig(api_key="k", shocker_ids=["a", "b"], shocker_mode="Random").save()
        cfg, error = load_config()
        self.assertIsNone(error)
        self.assertEqual(cfg.api_key, "k")
        self.assertEqual(cfg.shocker_ids, ["a", "b"])


if __name__ == "__main__":
    unittest.main()
