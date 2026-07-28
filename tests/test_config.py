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
            "provider": "openshock",
            "openshock_api_key": "key123",
            "openshock_shocker_ids": ["a", "b"],
            "openshock_shocker_mode": "Random",
            "param_grabbed": "/custom/grab",
            "param_stretch": "/custom/stretch",
        })
        cfg, error = load_config()
        self.assertIsNone(error)
        self.assertEqual(cfg.openshock_api_key, "key123")
        self.assertEqual(cfg.openshock_shocker_ids, ["a", "b"])
        self.assertEqual(cfg.openshock_shocker_mode, "Random")
        self.assertEqual(cfg.param_grabbed, "/custom/grab")
        self.assertEqual(cfg.param_stretch, "/custom/stretch")
        self.assertTrue(cfg.is_complete)

    def test_corrupt_file_reports_parse_error(self):
        self.config_path.write_text("{not valid json")
        cfg, error = load_config()
        self.assertEqual(error, "parse_error")
        self.assertEqual(cfg, AppConfig())

    def test_blank_osc_params_fall_back_to_defaults(self):
        self.write_config({
            "provider": "openshock", "openshock_api_key": "k", "openshock_shocker_ids": ["a"],
            "param_grabbed": "", "param_stretch": "",
        })
        cfg, _ = load_config()
        self.assertEqual(cfg.param_grabbed, DEFAULT_PARAM_GRABBED)
        self.assertEqual(cfg.param_stretch, DEFAULT_PARAM_STRETCH)

    def test_single_shocker_id_forces_all_mode(self):
        self.write_config({
            "provider": "openshock", "openshock_api_key": "key",
            "openshock_shocker_ids": ["only-one"], "openshock_shocker_mode": "Random",
        })
        cfg, _ = load_config()
        self.assertEqual(cfg.openshock_shocker_mode, "All")

    def test_multiple_shocker_ids_keep_requested_mode(self):
        self.write_config({
            "provider": "openshock", "openshock_api_key": "key",
            "openshock_shocker_ids": ["a", "b"], "openshock_shocker_mode": "Random",
        })
        cfg, _ = load_config()
        self.assertEqual(cfg.openshock_shocker_mode, "Random")

    def test_single_pishock_share_code_forces_all_mode(self):
        self.write_config({
            "provider": "pishock", "pishock_username": "u", "pishock_api_key": "key",
            "pishock_share_codes": ["only-one"], "pishock_shocker_mode": "Random",
        })
        cfg, _ = load_config()
        self.assertEqual(cfg.pishock_shocker_mode, "All")

    def test_pishock_fields_load_independently_of_openshock_fields(self):
        self.write_config({
            "provider": "pishock",
            "pishock_username": "user1", "pishock_api_key": "pikey", "pishock_share_codes": ["c1", "c2"],
            "openshock_api_key": "oskey", "openshock_shocker_ids": ["a"],
        })
        cfg, _ = load_config()
        self.assertEqual(cfg.provider, "pishock")
        self.assertEqual(cfg.pishock_username, "user1")
        self.assertEqual(cfg.pishock_api_key, "pikey")
        self.assertEqual(cfg.pishock_share_codes, ["c1", "c2"])
        self.assertTrue(cfg.is_complete)
        # OpenShock config is preserved even while PiShock is active, so switching back is instant.
        self.assertEqual(cfg.openshock_api_key, "oskey")
        self.assertEqual(cfg.openshock_shocker_ids, ["a"])

    def test_is_complete_checks_only_the_active_provider(self):
        self.write_config({
            "provider": "pishock",
            "openshock_api_key": "oskey", "openshock_shocker_ids": ["a"],
            "pishock_username": "", "pishock_api_key": "", "pishock_share_codes": [],
        })
        cfg, _ = load_config()
        self.assertFalse(cfg.is_complete)

    def test_unknown_provider_falls_back_to_openshock(self):
        self.write_config({"provider": "bogus", "openshock_api_key": "key", "openshock_shocker_ids": ["a"]})
        cfg, _ = load_config()
        self.assertEqual(cfg.provider, "openshock")

    def test_legacy_flat_config_is_migrated_to_openshock_fields(self):
        self.write_config({
            "api_key": "legacy-key", "shocker_ids": ["a", "b"], "shocker_mode": "Random",
        })
        cfg, _ = load_config()
        self.assertEqual(cfg.provider, "openshock")
        self.assertEqual(cfg.openshock_api_key, "legacy-key")
        self.assertEqual(cfg.openshock_shocker_ids, ["a", "b"])
        self.assertEqual(cfg.openshock_shocker_mode, "Random")
        on_disk = json.loads(self.config_path.read_text())
        self.assertEqual(on_disk["openshock_api_key"], "legacy-key")

    def test_legacy_single_shocker_id_is_migrated_and_persisted(self):
        self.write_config({"api_key": "key", "shocker_ids": [], "shocker_id": "legacy-id"})
        cfg, _ = load_config()
        self.assertIn("legacy-id", cfg.openshock_shocker_ids)
        on_disk = json.loads(self.config_path.read_text())
        self.assertIn("legacy-id", on_disk["openshock_shocker_ids"])

    def test_legacy_shocker_id_not_duplicated_if_already_present(self):
        self.write_config({"api_key": "key", "shocker_ids": ["legacy-id"], "shocker_id": "legacy-id"})
        cfg, _ = load_config()
        self.assertEqual(cfg.openshock_shocker_ids.count("legacy-id"), 1)


class SaveConfigTests(ConfigTestCase):
    def test_save_writes_all_fields_as_json(self):
        cfg = AppConfig(provider="openshock", openshock_api_key="abc", openshock_shocker_ids=["x", "y"], openshock_shocker_mode="All")
        cfg.save()
        on_disk = json.loads(self.config_path.read_text())
        self.assertEqual(on_disk["openshock_api_key"], "abc")
        self.assertEqual(on_disk["openshock_shocker_ids"], ["x", "y"])
        self.assertEqual(on_disk["openshock_shocker_mode"], "All")

    def test_round_trip_through_save_and_load(self):
        AppConfig(provider="pishock", pishock_username="u", pishock_api_key="k", pishock_share_codes=["a", "b"]).save()
        cfg, error = load_config()
        self.assertIsNone(error)
        self.assertEqual(cfg.provider, "pishock")
        self.assertEqual(cfg.pishock_username, "u")
        self.assertEqual(cfg.pishock_api_key, "k")
        self.assertEqual(cfg.pishock_share_codes, ["a", "b"])


if __name__ == "__main__":
    unittest.main()
