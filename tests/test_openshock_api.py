import unittest
from unittest.mock import MagicMock, patch

from mts.openshock_api import OpenShockClient


class NotConfiguredTests(unittest.TestCase):
    def test_returns_none_with_no_api_key(self):
        client = OpenShockClient(api_key="", shocker_ids=["a"])
        self.assertIsNone(client.send(10, 100, "Shock"))

    def test_returns_none_with_no_shocker_ids(self):
        client = OpenShockClient(api_key="key", shocker_ids=[])
        self.assertIsNone(client.send(10, 100, "Shock"))

    def test_does_not_hit_the_network_when_unconfigured(self):
        with patch("mts.openshock_api.requests.post") as mock_post:
            OpenShockClient(api_key="", shocker_ids=[]).send(10, 100, "Shock")
            mock_post.assert_not_called()


class SendResultTests(unittest.TestCase):
    @patch("mts.openshock_api.requests.post")
    def test_http_200_is_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        success, message = OpenShockClient(api_key="key", shocker_ids=["a"]).send(50, 500, "Vibrate")
        self.assertTrue(success)
        self.assertIn("Vibrate", message)

    @patch("mts.openshock_api.requests.post")
    def test_non_200_status_is_reported_as_failure(self, mock_post):
        mock_post.return_value = MagicMock(status_code=500)
        success, message = OpenShockClient(api_key="key", shocker_ids=["a"]).send(50, 500, "Shock")
        self.assertFalse(success)
        self.assertIn("500", message)

    @patch("mts.openshock_api.requests.post", side_effect=TimeoutError("boom"))
    def test_network_error_is_a_fail_safe_not_a_crash(self, mock_post):
        success, message = OpenShockClient(api_key="key", shocker_ids=["a"]).send(50, 500, "Shock")
        self.assertFalse(success)
        self.assertIn("FAIL SAFE", message)


class PayloadTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("mts.openshock_api.requests.post")
        self.mock_post = patcher.start()
        self.mock_post.return_value = MagicMock(status_code=200)
        self.addCleanup(patcher.stop)

    def sent_payload(self):
        return self.mock_post.call_args.kwargs["json"]

    def test_all_mode_targets_every_shocker(self):
        OpenShockClient(api_key="key", shocker_ids=["a", "b", "c"], shocker_mode="All").send(10, 100, "Shock")
        self.assertEqual([s["id"] for s in self.sent_payload()["shocks"]], ["a", "b", "c"])

    @patch("mts.openshock_api.random.choice", return_value="b")
    def test_random_mode_targets_exactly_one_shocker(self, mock_choice):
        OpenShockClient(api_key="key", shocker_ids=["a", "b", "c"], shocker_mode="Random").send(10, 100, "Shock")
        self.assertEqual([s["id"] for s in self.sent_payload()["shocks"]], ["b"])

    def test_random_mode_with_a_single_shocker_still_targets_it(self):
        OpenShockClient(api_key="key", shocker_ids=["only"], shocker_mode="Random").send(10, 100, "Shock")
        self.assertEqual([s["id"] for s in self.sent_payload()["shocks"]], ["only"])

    @patch("mts.openshock_api.random.choice", return_value="b")
    def test_force_all_overrides_random_mode(self, mock_choice):
        OpenShockClient(api_key="key", shocker_ids=["a", "b", "c"], shocker_mode="Random").send(10, 100, "Vibrate", force_all=True)
        self.assertEqual([s["id"] for s in self.sent_payload()["shocks"]], ["a", "b", "c"])

    def test_action_type_is_mapped_to_the_correct_code(self):
        OpenShockClient(api_key="key", shocker_ids=["a"]).send(10, 100, "Stop")
        self.assertEqual(self.sent_payload()["shocks"][0]["type"], 0)

    def test_unknown_action_type_falls_back_to_vibrate(self):
        OpenShockClient(api_key="key", shocker_ids=["a"]).send(10, 100, "Bogus")
        self.assertEqual(self.sent_payload()["shocks"][0]["type"], 2)

    def test_intensity_and_duration_are_forwarded_as_given(self):
        OpenShockClient(api_key="key", shocker_ids=["a"]).send(42, 777, "Shock")
        shock = self.sent_payload()["shocks"][0]
        self.assertEqual(shock["intensity"], 42)
        self.assertEqual(shock["duration"], 777)

    def test_api_key_is_sent_as_the_openshock_token_header(self):
        OpenShockClient(api_key="secret-token", shocker_ids=["a"]).send(10, 100, "Shock")
        headers = self.mock_post.call_args.kwargs["headers"]
        self.assertEqual(headers["OpenShockToken"], "secret-token")


if __name__ == "__main__":
    unittest.main()
