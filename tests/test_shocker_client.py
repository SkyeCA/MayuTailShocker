import unittest

from mts.config import AppConfig
from mts.openshock_api import OpenShockClient
from mts.pishock_api import PiShockClient
from mts.shocker_client import build_client


class BuildClientTests(unittest.TestCase):
    def test_defaults_to_openshock(self):
        client = build_client(AppConfig())
        self.assertIsInstance(client, OpenShockClient)

    def test_openshock_provider_builds_openshock_client_with_its_fields(self):
        config = AppConfig(
            provider="openshock",
            openshock_api_key="key123",
            openshock_shocker_ids=["a", "b"],
            openshock_shocker_mode="Random",
        )
        client = build_client(config)
        self.assertIsInstance(client, OpenShockClient)
        self.assertEqual(client.api_key, "key123")
        self.assertEqual(client.shocker_ids, ["a", "b"])
        self.assertEqual(client.shocker_mode, "Random")

    def test_pishock_provider_builds_pishock_client_with_its_fields(self):
        config = AppConfig(
            provider="pishock",
            pishock_username="user1",
            pishock_api_key="pikey",
            pishock_share_codes=["c1", "c2"],
            pishock_shocker_mode="Random",
        )
        client = build_client(config)
        self.assertIsInstance(client, PiShockClient)
        self.assertEqual(client.username, "user1")
        self.assertEqual(client.api_key, "pikey")
        self.assertEqual(client.share_codes, ["c1", "c2"])
        self.assertEqual(client.shocker_mode, "Random")

    def test_switching_provider_does_not_leak_the_other_providers_credentials(self):
        config = AppConfig(
            provider="pishock",
            openshock_api_key="openshock-secret",
            pishock_username="user1",
            pishock_api_key="pishock-secret",
            pishock_share_codes=["c1"],
        )
        client = build_client(config)
        self.assertNotIn("openshock-secret", vars(client).values())


if __name__ == "__main__":
    unittest.main()
