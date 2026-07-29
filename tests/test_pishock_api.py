import unittest
from unittest.mock import MagicMock, patch

from mts.pishock_api import PiShockClient


def mock_response(status_code=204, text="", json_body=None):
    resp = MagicMock(status_code=status_code)
    resp.text = text
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.side_effect = ValueError("no body")
    return resp


def shared_response(entries):
    """entries: list of (share_code, shocker_id) already claimed on the account."""
    body = [{"ShareCode": code, "Id": sid} for code, sid in entries]
    return mock_response(200, json_body=body)


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
        with patch("mts.pishock_api.requests.get") as mock_get, patch("mts.pishock_api.requests.post") as mock_post:
            PiShockClient(username="", api_key="", share_codes=[]).send(10, 1000, "Shock")
            mock_get.assert_not_called()
            mock_post.assert_not_called()

    def test_stop_action_returns_none_even_when_configured(self):
        """PiShock has no Stop operation - see PiShockClient's docstring."""
        client = PiShockClient(username="user", api_key="key", share_codes=["a"])
        with patch("mts.pishock_api.requests.get") as mock_get, patch("mts.pishock_api.requests.post") as mock_post:
            self.assertIsNone(client.send(0, 1000, "Stop"))
            mock_get.assert_not_called()
            mock_post.assert_not_called()


class ResolutionTests(unittest.TestCase):
    """Covers the transparent Share Code -> numeric Shocker ID resolution
    (GET /Share/GetShared) and auto-claim (PUT /Share) flow."""

    def setUp(self):
        get_patcher = patch("mts.pishock_api.requests.get")
        post_patcher = patch("mts.pishock_api.requests.post")
        put_patcher = patch("mts.pishock_api.requests.put")
        self.mock_get = get_patcher.start()
        self.mock_post = post_patcher.start()
        self.mock_put = put_patcher.start()
        self.addCleanup(get_patcher.stop)
        self.addCleanup(post_patcher.stop)
        self.addCleanup(put_patcher.stop)
        self.mock_post.return_value = mock_response(204)

    def test_already_claimed_code_resolves_without_claiming(self):
        self.mock_get.return_value = shared_response([("mycode", 42)])
        success, message = PiShockClient("u", "k", ["mycode"]).send(10, 1000, "Shock")
        self.assertTrue(success)
        self.mock_put.assert_not_called()
        self.assertEqual(self.mock_post.call_args.args[0], "https://api.pishock.com/Shockers/42")

    def test_unclaimed_code_gets_claimed_then_resolved(self):
        # First GetShared call: not yet claimed. After PUT /Share, second call finds it.
        self.mock_get.side_effect = [shared_response([]), shared_response([("newcode", 7)])]
        self.mock_put.return_value = mock_response(204)

        success, message = PiShockClient("u", "k", ["newcode"]).send(10, 1000, "Shock")

        self.assertTrue(success)
        self.mock_put.assert_called_once()
        self.assertEqual(self.mock_put.call_args.kwargs["json"], {"Shares": ["newcode"]})
        self.assertEqual(self.mock_post.call_args.args[0], "https://api.pishock.com/Shockers/7")

    def test_resolution_is_cached_across_sends(self):
        self.mock_get.return_value = shared_response([("mycode", 42)])
        client = PiShockClient("u", "k", ["mycode"])
        client.send(10, 1000, "Shock")
        client.send(10, 1000, "Shock")
        self.assertEqual(self.mock_get.call_count, 1)
        self.assertEqual(self.mock_post.call_count, 2)

    def test_code_claimed_by_someone_else_is_reported_clearly(self):
        # Never appears in GetShared, and claiming reports 410 (already claimed).
        self.mock_get.return_value = shared_response([])
        self.mock_put.return_value = mock_response(410)

        success, message = PiShockClient("u", "k", ["notmine"]).send(10, 1000, "Shock")

        self.assertFalse(success)
        self.assertIn("notmine", message)
        self.mock_post.assert_not_called()

    def test_claim_failure_is_surfaced(self):
        self.mock_get.return_value = shared_response([])
        self.mock_put.return_value = mock_response(404, json_body={"Message": "Could not find one of the shares. No shares claimed.", "Errors": {}})

        success, message = PiShockClient("u", "k", ["typo'd"]).send(10, 1000, "Shock")

        self.assertFalse(success)
        self.assertIn("Could not find one of the shares", message)
        self.mock_post.assert_not_called()

    def test_network_error_during_lookup_is_a_fail_safe_not_a_crash(self):
        self.mock_get.side_effect = TimeoutError("boom")
        success, message = PiShockClient("u", "k", ["a"]).send(10, 1000, "Shock")
        self.assertFalse(success)
        self.assertIn("PiShock Error", message)

    def test_stale_cached_id_is_dropped_on_404_from_operate(self):
        self.mock_get.return_value = shared_response([("mycode", 42)])
        self.mock_post.return_value = mock_response(404, json_body={"Message": "Not found.", "Errors": {}})

        client = PiShockClient("u", "k", ["mycode"])
        client.send(10, 1000, "Shock")
        self.assertNotIn("mycode", client._id_cache)


class SendResultTests(unittest.TestCase):
    def setUp(self):
        get_patcher = patch("mts.pishock_api.requests.get")
        self.mock_get = get_patcher.start()
        self.mock_get.return_value = shared_response([("a", 1)])
        self.addCleanup(get_patcher.stop)
        post_patcher = patch("mts.pishock_api.requests.post")
        self.mock_post = post_patcher.start()
        self.addCleanup(post_patcher.stop)

    def test_204_no_content_is_success(self):
        self.mock_post.return_value = mock_response(204)
        success, message = PiShockClient("user", "key", ["a"]).send(50, 1000, "Vibrate")
        self.assertTrue(success)
        self.assertIn("Vibrate", message)

    def test_401_is_reported_as_unauthorized(self):
        self.mock_post.return_value = mock_response(401)
        success, message = PiShockClient("user", "key", ["a"]).send(50, 1000, "Shock")
        self.assertFalse(success)
        self.assertIn("401", message)
        self.assertIn("Unauthorized", message)

    def test_unmapped_status_falls_back_to_response_text(self):
        self.mock_post.return_value = mock_response(500, "Internal Server Error")
        success, message = PiShockClient("user", "key", ["a"]).send(50, 1000, "Shock")
        self.assertFalse(success)
        self.assertIn("500", message)
        self.assertIn("Internal Server Error", message)

    def test_structured_validation_error_body_is_surfaced(self):
        self.mock_post.return_value = mock_response(400, json_body={
            "StatusCode": 400,
            "Message": "One or more errors occurred!",
            "Errors": {"ShockerId": ["Unable to read value of route parameter!"]},
        })
        success, message = PiShockClient("user", "key", ["a"]).send(50, 1000, "Shock")
        self.assertFalse(success)
        self.assertIn("One or more errors occurred!", message)
        self.assertIn("ShockerId: Unable to read value of route parameter!", message)

    def test_network_error_is_a_fail_safe_not_a_crash(self):
        self.mock_post.side_effect = TimeoutError("boom")
        success, message = PiShockClient("user", "key", ["a"]).send(50, 1000, "Shock")
        self.assertFalse(success)
        self.assertIn("FAIL SAFE", message)


class PayloadTests(unittest.TestCase):
    def setUp(self):
        get_patcher = patch("mts.pishock_api.requests.get")
        self.mock_get = get_patcher.start()
        self.mock_get.return_value = shared_response([("a", 1), ("b", 2), ("c", 3), ("mycode", 99), ("only", 5)])
        self.addCleanup(get_patcher.stop)
        post_patcher = patch("mts.pishock_api.requests.post")
        self.mock_post = post_patcher.start()
        self.mock_post.return_value = mock_response(204)
        self.addCleanup(post_patcher.stop)

    def sent_payload(self):
        return self.mock_post.call_args.kwargs["json"]

    def sent_headers(self):
        return self.mock_post.call_args.kwargs["headers"]

    def sent_url(self):
        return self.mock_post.call_args.args[0]

    def test_resolved_shocker_id_is_appended_to_the_url_path(self):
        PiShockClient("u", "k", ["mycode"]).send(10, 1000, "Shock")
        self.assertEqual(self.sent_url(), "https://api.pishock.com/Shockers/99")

    def test_credentials_are_sent_as_headers_not_body(self):
        PiShockClient("myuser", "mykey", ["mycode"]).send(10, 1000, "Shock")
        headers = self.sent_headers()
        self.assertEqual(headers["X-PiShock-Username"], "myuser")
        self.assertEqual(headers["X-PiShock-Api-Key"], "mykey")
        payload = self.sent_payload()
        self.assertNotIn("Username", payload)
        self.assertNotIn("Apikey", payload)
        self.assertNotIn("Code", payload)

    def test_action_type_is_mapped_to_the_correct_operation(self):
        PiShockClient("u", "k", ["a"]).send(10, 1000, "Shock")
        self.assertEqual(self.sent_payload()["Operation"], 0)

        PiShockClient("u", "k", ["a"]).send(10, 1000, "Vibrate")
        self.assertEqual(self.sent_payload()["Operation"], 1)

    def test_unknown_action_type_falls_back_to_vibrate(self):
        PiShockClient("u", "k", ["a"]).send(10, 1000, "Bogus")
        self.assertEqual(self.sent_payload()["Operation"], 1)

    def test_intensity_is_forwarded_as_given(self):
        PiShockClient("u", "k", ["a"]).send(42, 1000, "Shock")
        self.assertEqual(self.sent_payload()["Intensity"], 42)

    def test_duration_is_forwarded_in_milliseconds_unconverted(self):
        PiShockClient("u", "k", ["a"]).send(10, 2600, "Shock")
        self.assertEqual(self.sent_payload()["Duration"], 2600)

    def test_duration_below_sixteen_ms_is_clamped(self):
        PiShockClient("u", "k", ["a"]).send(10, 5, "Shock")
        self.assertEqual(self.sent_payload()["Duration"], 16)

    def test_duration_above_fifteen_seconds_is_clamped(self):
        PiShockClient("u", "k", ["a"]).send(10, 20000, "Shock")
        self.assertEqual(self.sent_payload()["Duration"], 15000)

    def test_random_mode_targets_exactly_one_shocker(self):
        with patch("mts.pishock_api.random.choice", return_value="b"):
            PiShockClient("u", "k", ["a", "b", "c"], shocker_mode="Random").send(10, 1000, "Shock")
        self.assertEqual(self.mock_post.call_count, 1)
        self.assertEqual(self.sent_url(), "https://api.pishock.com/Shockers/2")

    def test_random_mode_with_a_single_shocker_still_targets_it(self):
        PiShockClient("u", "k", ["only"], shocker_mode="Random").send(10, 1000, "Shock")
        self.assertEqual(self.sent_url(), "https://api.pishock.com/Shockers/5")

    def test_force_all_overrides_random_mode(self):
        with patch("mts.pishock_api.random.choice", return_value="b"):
            PiShockClient("u", "k", ["a", "b", "c"], shocker_mode="Random").send(10, 1000, "Shock", force_all=True)
        self.assertEqual(self.mock_post.call_count, 3)


class AllModeMultiShockerTests(unittest.TestCase):
    """PiShock's operate endpoint only accepts one Shocker ID per request, unlike
    OpenShock's single batched call - so "All" mode fires one request per ID."""

    def setUp(self):
        get_patcher = patch("mts.pishock_api.requests.get")
        self.mock_get = get_patcher.start()
        self.mock_get.return_value = shared_response([("a", 1), ("b", 2), ("c", 3)])
        self.addCleanup(get_patcher.stop)
        post_patcher = patch("mts.pishock_api.requests.post")
        self.mock_post = post_patcher.start()
        self.mock_post.return_value = mock_response(204)
        self.addCleanup(post_patcher.stop)

    def sent_ids(self):
        return {call.args[0].rsplit("/", 1)[-1] for call in self.mock_post.call_args_list}

    def test_all_mode_sends_one_request_per_shocker(self):
        PiShockClient("u", "k", ["a", "b", "c"], shocker_mode="All").send(10, 1000, "Shock")
        self.assertEqual(self.mock_post.call_count, 3)
        self.assertEqual(self.sent_ids(), {"1", "2", "3"})

    def test_all_mode_succeeds_only_if_every_shocker_succeeds(self):
        self.mock_post.side_effect = [mock_response(204), mock_response(401)]
        success, message = PiShockClient("u", "k", ["a", "b"], shocker_mode="All").send(10, 1000, "Shock")
        self.assertFalse(success)
        self.assertIn("Unauthorized", message)


if __name__ == "__main__":
    unittest.main()
