import unittest
from unittest.mock import MagicMock, patch

from mts.pishock_api import PiShockClient


def mock_response(status_code=200, message="Operation Succeeded."):
    """PiShock's operate endpoint returns its message as a JSON-encoded string body."""
    resp = MagicMock(status_code=status_code)
    resp.text = f'"{message}"'
    resp.json.return_value = message
    return resp


class NotConfiguredTests(unittest.TestCase):
    def test_returns_none_with_no_username(self):
        client = PiShockClient(username="", api_key="key", share_codes=["a"])
        self.assertIsNone(client.send(10, 1000, "Shock"))

    def test_returns_none_with_no_api_key(self):
        client = PiShockClient(username="user", api_key="", share_codes=["a"])
        self.assertIsNone(client.send(10, 1000, "Shock"))

    def test_returns_none_with_no_share_codes(self):
        client = PiShockClient(username="user", api_key="key", share_codes=[])
        self.assertIsNone(client.send(10, 1000, "Shock"))

    def test_does_not_hit_the_network_when_unconfigured(self):
        with patch("mts.pishock_api.requests.post") as mock_post:
            PiShockClient(username="", api_key="", share_codes=[]).send(10, 1000, "Shock")
            mock_post.assert_not_called()

    def test_stop_action_returns_none_even_when_configured(self):
        """PiShock has no Stop operation - see PiShockClient's docstring."""
        client = PiShockClient(username="user", api_key="key", share_codes=["a"])
        with patch("mts.pishock_api.requests.post") as mock_post:
            self.assertIsNone(client.send(0, 1000, "Stop"))
            mock_post.assert_not_called()


class SendResultTests(unittest.TestCase):
    @patch("mts.pishock_api.requests.post")
    def test_success_text_is_success(self, mock_post):
        mock_post.return_value = mock_response(200, "Operation Succeeded.")
        success, message = PiShockClient("user", "key", ["a"]).send(50, 1000, "Vibrate")
        self.assertTrue(success)
        self.assertIn("Vibrate", message)

    @patch("mts.pishock_api.requests.post")
    def test_failure_text_is_reported_as_failure(self, mock_post):
        mock_post.return_value = mock_response(200, "Not Authorized.")
        success, message = PiShockClient("user", "key", ["a"]).send(50, 1000, "Shock")
        self.assertFalse(success)
        self.assertIn("Not Authorized", message)

    @patch("mts.pishock_api.requests.post", side_effect=TimeoutError("boom"))
    def test_network_error_is_a_fail_safe_not_a_crash(self, mock_post):
        success, message = PiShockClient("user", "key", ["a"]).send(50, 1000, "Shock")
        self.assertFalse(success)
        self.assertIn("FAIL SAFE", message)

    @patch("mts.pishock_api.requests.post")
    def test_non_json_body_falls_back_to_raw_text(self, mock_post):
        resp = MagicMock(status_code=502)
        resp.text = "<html>Bad Gateway</html>"
        resp.json.side_effect = ValueError("not json")
        mock_post.return_value = resp
        success, message = PiShockClient("user", "key", ["a"]).send(50, 1000, "Shock")
        self.assertFalse(success)
        self.assertIn("Bad Gateway", message)


class PayloadTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("mts.pishock_api.requests.post")
        self.mock_post = patcher.start()
        self.mock_post.return_value = mock_response()
        self.addCleanup(patcher.stop)

    def sent_payload(self):
        return self.mock_post.call_args.kwargs["json"]

    def test_credentials_and_code_are_forwarded_lowercase(self):
        PiShockClient("myuser", "mykey", ["mycode"]).send(10, 1000, "Shock")
        payload = self.sent_payload()
        self.assertEqual(payload["username"], "myuser")
        self.assertEqual(payload["apikey"], "mykey")
        self.assertEqual(payload["code"], "mycode")

    def test_action_type_is_mapped_to_the_correct_op(self):
        PiShockClient("u", "k", ["a"]).send(10, 1000, "Shock")
        self.assertEqual(self.sent_payload()["op"], 0)

        PiShockClient("u", "k", ["a"]).send(10, 1000, "Vibrate")
        self.assertEqual(self.sent_payload()["op"], 1)

    def test_unknown_action_type_falls_back_to_vibrate(self):
        PiShockClient("u", "k", ["a"]).send(10, 1000, "Bogus")
        self.assertEqual(self.sent_payload()["op"], 1)

    def test_intensity_is_forwarded_as_given(self):
        PiShockClient("u", "k", ["a"]).send(42, 1000, "Shock")
        self.assertEqual(self.sent_payload()["intensity"], 42)

    def test_duration_is_converted_from_ms_to_whole_seconds(self):
        PiShockClient("u", "k", ["a"]).send(10, 2600, "Shock")
        self.assertEqual(self.sent_payload()["duration"], 3)

    def test_duration_below_one_second_is_clamped_to_one(self):
        PiShockClient("u", "k", ["a"]).send(10, 400, "Shock")
        self.assertEqual(self.sent_payload()["duration"], 1)

    def test_duration_above_fifteen_seconds_is_clamped(self):
        PiShockClient("u", "k", ["a"]).send(10, 20000, "Shock")
        self.assertEqual(self.sent_payload()["duration"], 15)

    def test_random_mode_targets_exactly_one_shocker(self):
        with patch("mts.pishock_api.random.choice", return_value="b"):
            PiShockClient("u", "k", ["a", "b", "c"], shocker_mode="Random").send(10, 1000, "Shock")
        self.assertEqual(self.mock_post.call_count, 1)
        self.assertEqual(self.sent_payload()["code"], "b")

    def test_random_mode_with_a_single_shocker_still_targets_it(self):
        PiShockClient("u", "k", ["only"], shocker_mode="Random").send(10, 1000, "Shock")
        self.assertEqual(self.sent_payload()["code"], "only")

    def test_force_all_overrides_random_mode(self):
        with patch("mts.pishock_api.random.choice", return_value="b"):
            PiShockClient("u", "k", ["a", "b", "c"], shocker_mode="Random").send(10, 1000, "Shock", force_all=True)
        self.assertEqual(self.mock_post.call_count, 3)


class AllModeMultiShockerTests(unittest.TestCase):
    """PiShock's operate endpoint only accepts one share code per request, unlike
    OpenShock's single batched call - so "All" mode fires one request per code."""

    def setUp(self):
        patcher = patch("mts.pishock_api.requests.post")
        self.mock_post = patcher.start()
        self.mock_post.return_value = mock_response()
        self.addCleanup(patcher.stop)

    def sent_codes(self):
        return {call.kwargs["json"]["code"] for call in self.mock_post.call_args_list}

    def test_all_mode_sends_one_request_per_share_code(self):
        PiShockClient("u", "k", ["a", "b", "c"], shocker_mode="All").send(10, 1000, "Shock")
        self.assertEqual(self.mock_post.call_count, 3)
        self.assertEqual(self.sent_codes(), {"a", "b", "c"})

    def test_all_mode_succeeds_only_if_every_shocker_succeeds(self):
        self.mock_post.side_effect = [mock_response(200, "Operation Succeeded."), mock_response(200, "Not Authorized.")]
        success, message = PiShockClient("u", "k", ["a", "b"], shocker_mode="All").send(10, 1000, "Shock")
        self.assertFalse(success)
        self.assertIn("Not Authorized", message)


if __name__ == "__main__":
    unittest.main()
