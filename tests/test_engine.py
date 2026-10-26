import struct
import threading
import unittest
from unittest.mock import MagicMock, patch

from mts.config import AppConfig
from mts.constants import (
    MTS_COOLDOWN,
    MTS_DURATION,
    MTS_DYNAMIC,
    MTS_ENABLE,
    MTS_INTENSITY,
    MTS_VIBRATE,
)
from mts.engine import EngineListener, ShockEngine, ShockSettings


class FakeOSC:
    def __init__(self):
        self.sent = []
        self.started = 0
        self.restarted = 0
        self.stopped = 0
        self.start_error = None

    def start(self, handlers):
        if self.start_error:
            raise self.start_error
        self.started += 1

    def restart(self, handlers):
        self.restarted += 1

    def stop(self):
        self.stopped += 1

    def send(self, address, value):
        self.sent.append((address, value))


class RecordingListener(EngineListener):
    def __init__(self):
        self.logs = []
        self.active_changes = []
        self.settings_changes = []
        self.shock_counts = []
        self.status_changes = 0

    def on_log(self, message):
        self.logs.append(message)

    def on_active_changed(self, is_active):
        self.active_changes.append(is_active)

    def on_settings_changed(self, settings):
        self.settings_changes.append(settings)

    def on_shock_count_changed(self, count):
        self.shock_counts.append(count)

    def on_status_changed(self):
        self.status_changes += 1


class EngineTestCase(unittest.TestCase):
    """Builds an engine with fake OSC/client, runs spawned threads inline, and stubs
    out session-state persistence so tests never touch real files."""

    def setUp(self):
        for name in ("update_session_state", "finalize_session", "recover_previous_session"):
            patcher = patch(f"mts.engine.{name}", return_value=None)
            setattr(self, f"mock_{name}", patcher.start())
            self.addCleanup(patcher.stop)

        self.config = AppConfig(api_key="key", shocker_ids=["a"])
        self.config.save = MagicMock()
        self.client = MagicMock(is_configured=True)
        self.client.send.return_value = (True, "ok")
        self.osc = FakeOSC()
        self.listener = RecordingListener()
        self.engine = ShockEngine(self.config, self.client, self.osc, self.listener)
        self.engine._spawn = lambda target, *args: target(*args)

    def sent_commands(self):
        return [c.args for c in self.client.send.call_args_list]


class SettingsTests(EngineTestCase):
    def test_ui_change_sends_only_the_changed_setting_scaled_for_the_avatar_menu(self):
        self.engine.update_settings(max_intensity=50, cooldown=5.0)
        self.assertEqual(self.osc.sent, [(MTS_INTENSITY, 0.5)])

    def test_ui_change_is_not_echoed_back_to_the_listener(self):
        self.engine.update_settings(max_intensity=50)
        self.assertEqual(self.listener.settings_changes, [])

    def test_osc_change_notifies_the_listener_but_is_not_sent_back_out(self):
        self.engine.update_settings(vibrate=False, from_osc=True)
        self.assertEqual(self.osc.sent, [])
        self.assertEqual(self.listener.settings_changes, [ShockSettings(vibrate=False)])

    def test_unchanged_values_do_nothing(self):
        self.engine.update_settings(max_intensity=ShockSettings().max_intensity, from_osc=True)
        self.assertEqual(self.osc.sent, [])
        self.assertEqual(self.listener.settings_changes, [])

    def test_switching_mode_is_logged(self):
        self.engine.update_settings(dynamic=True)
        self.engine.update_settings(dynamic=False)
        self.assertEqual(self.listener.logs, ["Physbone Stretch Mode enabled.", "Random Mode enabled."])

    def test_sync_osc_sends_every_setting_and_the_enabled_state(self):
        self.engine.sync_osc()
        self.assertEqual(dict(self.osc.sent), {
            MTS_ENABLE: True,
            MTS_INTENSITY: 0.3,
            MTS_DURATION: 0.1,
            MTS_COOLDOWN: 0.5,
            MTS_VIBRATE: True,
            MTS_DYNAMIC: False,
        })


class IncomingOSCTests(EngineTestCase):
    def test_intensity_is_converted_to_a_percentage(self):
        self.engine.on_mts_intensity(MTS_INTENSITY, 0.75)
        self.assertEqual(self.engine.settings.max_intensity, 75)

    def test_every_menu_percentage_survives_osc_float32_precision(self):
        # OSC floats are 32-bit: 0.45 arrives as 0.44999998..., which must still read as 45%.
        for percent in range(1, 101):
            as_sent = struct.unpack("f", struct.pack("f", percent / 100))[0]
            self.engine.on_mts_intensity(MTS_INTENSITY, as_sent)
            self.assertEqual(self.engine.settings.max_intensity, percent)

    def test_intensity_of_zero_is_clamped_to_one_percent(self):
        self.engine.on_mts_intensity(MTS_INTENSITY, 0.0)
        self.assertEqual(self.engine.settings.max_intensity, 1)

    def test_duration_uses_100ms_per_percent_with_a_300ms_floor(self):
        self.engine.on_mts_duration(MTS_DURATION, 0.25)
        self.assertEqual(self.engine.settings.max_duration, 2.5)
        self.engine.on_mts_duration(MTS_DURATION, 0.01)
        self.assertEqual(self.engine.settings.max_duration, 0.3)

    def test_cooldown_is_clamped_between_one_and_ten_seconds(self):
        self.engine.on_mts_cooldown(MTS_COOLDOWN, 0.0)
        self.assertEqual(self.engine.settings.cooldown, 1.0)
        self.engine.on_mts_cooldown(MTS_COOLDOWN, 0.33)
        self.assertEqual(self.engine.settings.cooldown, 3.3)

    def test_enable_from_the_avatar_is_not_sent_back_out(self):
        self.engine.on_mts_enable(MTS_ENABLE, False)
        self.assertFalse(self.engine.is_active)
        self.assertNotIn((MTS_ENABLE, False), self.osc.sent)

    def test_messages_without_arguments_are_ignored(self):
        self.engine.on_mts_intensity(MTS_INTENSITY)
        self.engine.on_mts_enable(MTS_ENABLE)
        self.assertEqual(self.engine.settings, ShockSettings())
        self.assertTrue(self.engine.is_active)


class ActiveStateTests(EngineTestCase):
    def test_disabling_halts_the_shockers_and_updates_the_avatar(self):
        self.engine.set_active(False)
        self.assertEqual(self.sent_commands(), [(0, 300, "Stop")])
        self.assertIn((MTS_ENABLE, False), self.osc.sent)
        self.assertEqual(self.listener.active_changes, [False])

    def test_setting_the_current_state_is_a_no_op(self):
        self.engine.set_active(True)
        self.assertEqual(self.listener.active_changes, [])
        self.assertEqual(self.osc.sent, [])

    def test_cooldown_remaining_is_zero_while_disabled_or_in_dynamic_mode(self):
        self.engine.shock_end_time = 10**12  # far future: always "in cooldown"
        self.assertGreater(self.engine.cooldown_remaining(), 0)
        self.engine.update_settings(dynamic=True)
        self.assertEqual(self.engine.cooldown_remaining(), 0.0)
        self.engine.update_settings(dynamic=False)
        self.engine.set_active(False)
        self.assertEqual(self.engine.cooldown_remaining(), 0.0)


class SendOrderTests(EngineTestCase):
    def test_a_shock_still_waiting_to_send_when_disabled_is_dropped(self):
        pending = []
        self.engine._spawn = lambda target, *args: pending.append((target, args))
        self.engine.trigger_shock()  # decided, but its request hasn't gone out yet
        self.engine.set_active(False)
        for target, args in pending:
            target(*args)
        self.assertEqual(self.sent_commands(), [(0, 300, "Stop")])

    def test_a_stop_waits_for_a_shock_already_being_sent(self):
        in_flight, release = threading.Event(), threading.Event()

        def send(intensity, duration_ms, action_type):
            if action_type == "Shock":
                in_flight.set()
                release.wait(2)
            return True, "ok"

        self.client.send.side_effect = send
        shock = threading.Thread(target=self.engine.send_openshock_command, args=(50, 1000, "Shock"))
        shock.start()
        in_flight.wait(2)
        halt = threading.Thread(target=self.engine.send_halt_command)
        halt.start()
        halt.join(0.1)
        self.assertTrue(halt.is_alive())  # held back until the shock's request completes
        release.set()
        shock.join(2)
        halt.join(2)
        self.assertEqual([action for _, _, action in self.sent_commands()], ["Shock", "Stop"])


class TriggerShockTests(EngineTestCase):
    def pull(self, stretch=0.5):
        self.engine.on_grabbed_update("grab", True)
        self.engine.on_stretch_update("stretch", stretch)

    def test_vibrate_mode_vibrates_and_does_not_count_as_a_shock(self):
        self.pull()
        (intensity, duration_ms, action), = self.sent_commands()
        self.assertEqual(action, "Vibrate")
        self.assertEqual(self.engine.session_shock_count, 0)

    def test_shock_is_counted_persisted_and_reported(self):
        self.engine.update_settings(vibrate=False)
        self.pull()
        self.assertEqual(self.sent_commands()[0][2], "Shock")
        self.assertEqual(self.listener.shock_counts, [1])
        self.mock_update_session_state.assert_called_once_with(1)

    def test_intensity_and_duration_stay_within_the_configured_maximums(self):
        self.engine.update_settings(max_intensity=40, max_duration=2.0, cooldown=1.0)
        for _ in range(50):
            self.engine.shock_end_time = 0.0
            self.engine.trigger_shock()
        for intensity, duration_ms, _ in self.sent_commands():
            self.assertTrue(1 <= intensity <= 40)
            self.assertTrue(300 <= duration_ms <= 2000)

    def test_cooldown_blocks_a_second_trigger(self):
        self.pull()
        self.pull()
        self.assertEqual(len(self.sent_commands()), 1)
        self.assertEqual(self.listener.status_changes, 1)

    def test_nothing_is_sent_while_disabled(self):
        self.engine.set_active(False)
        self.client.send.reset_mock()
        self.pull()
        self.assertEqual(self.sent_commands(), [])

    def test_nothing_is_sent_when_unconfigured(self):
        self.client.is_configured = False
        self.pull()
        self.assertEqual(self.sent_commands(), [])

    def test_stretch_at_or_below_the_threshold_does_not_trigger(self):
        self.pull(stretch=0.1)
        self.assertEqual(self.sent_commands(), [])

    def test_no_random_shock_while_a_stretch_pull_is_still_ending(self):
        self.engine.is_dynamic_loop_running = True
        self.pull()
        self.assertEqual(self.sent_commands(), [])


class CooldownTests(EngineTestCase):
    """A 10 s shock at t=1000 with a 1 s cooldown."""

    def setUp(self):
        super().setUp()
        self.engine.update_settings(max_duration=10.0, cooldown=1.0, vibrate=False)
        self.now = 1000.0
        for target, kwargs in (("mts.engine.time.time", {"side_effect": lambda: self.now}),
                               ("mts.engine.random.uniform", {"return_value": 10.0})):
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.engine.trigger_shock()

    def trigger_at(self, now):
        self.now = now
        self.client.send.reset_mock()
        self.engine.trigger_shock()
        return self.sent_commands()

    def test_cooldown_runs_from_when_the_shock_ends_not_when_it_starts(self):
        self.assertEqual(self.trigger_at(1005.0), [])  # shock still running
        self.assertEqual(self.trigger_at(1010.5), [])  # in the cooldown after it
        self.assertEqual(len(self.trigger_at(1011.5)), 1)

    def test_status_shows_the_running_output_then_the_cooldown(self):
        self.now = 1005.0
        self.assertEqual(self.engine.current_output(), "Shock")
        self.assertEqual(self.engine.cooldown_remaining(), 1.0)
        self.now = 1010.25
        self.assertIsNone(self.engine.current_output())
        self.assertAlmostEqual(self.engine.cooldown_remaining(), 0.75)
        self.now = 1012.0
        self.assertEqual(self.engine.cooldown_remaining(), 0.0)

    def test_disabling_cuts_the_shock_short_so_the_cooldown_starts_then(self):
        self.now = 1002.0
        self.engine.set_active(False)
        self.engine.set_active(True)
        self.assertIsNone(self.engine.current_output())
        self.assertEqual(len(self.trigger_at(1003.5)), 1)


class DynamicModeTests(EngineTestCase):
    def setUp(self):
        super().setUp()
        self.engine.update_settings(dynamic=True, max_intensity=80)
        self.iterations_left = 0

        def fake_sleep(seconds):
            self.iterations_left -= 1
            if self.iterations_left <= 0:
                self.engine.is_grabbed = False

        patcher = patch("mts.engine.time.sleep", side_effect=fake_sleep)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_loop(self, iterations, stretch):
        self.iterations_left = iterations
        self.engine.current_stretch = stretch
        self.engine.on_grabbed_update("grab", True)

    def test_intensity_scales_with_stretch_and_ends_with_a_stop(self):
        self.run_loop(iterations=2, stretch=0.5)
        self.assertEqual(self.sent_commands(), [
            (40, 400, "Vibrate"),
            (40, 400, "Vibrate"),
            (0, 300, "Stop"),
        ])

    def test_real_shocks_count_once_on_start_and_once_per_second_held(self):
        self.engine.update_settings(vibrate=False)
        self.run_loop(iterations=10, stretch=1.0)  # 10 x 0.2s = 2s
        self.assertEqual(self.engine.session_shock_count, 3)

    def test_loop_start_and_end_update_the_status_and_release_the_running_flag(self):
        self.run_loop(iterations=1, stretch=1.0)
        self.assertFalse(self.engine.is_dynamic_loop_running)
        self.assertEqual(self.listener.status_changes, 2)


class ConfigTests(EngineTestCase):
    def test_shocker_changes_are_applied_to_the_client_and_saved(self):
        self.engine.update_config(shocker_ids=["a", "b"], shocker_mode="Random")
        self.assertEqual(self.client.shocker_ids, ["a", "b"])
        self.assertEqual(self.client.shocker_mode, "Random")
        self.config.save.assert_called_once()

    def test_changed_osc_params_restart_the_listener(self):
        self.engine.update_config(param_grabbed="/new/grab", param_stretch="/new/stretch")
        self.assertEqual(self.osc.restarted, 1)

    def test_unchanged_values_are_not_saved_and_do_not_restart_the_listener(self):
        self.engine.update_config(api_key=self.config.api_key, param_grabbed=self.config.param_grabbed)
        self.config.save.assert_not_called()
        self.assertEqual(self.osc.restarted, 0)

    def test_a_failed_save_raises_and_changes_nothing(self):
        self.config.save.side_effect = OSError("read-only")
        with self.assertRaises(OSError):
            self.engine.update_config(api_key="new-key", param_grabbed="/new/grab")
        self.assertEqual(self.config.api_key, "key")
        self.assertEqual(self.config.param_grabbed, AppConfig().param_grabbed)
        self.assertEqual(self.osc.restarted, 0)
        self.assertNotIn("Configuration saved.", self.listener.logs)


class LifecycleTests(EngineTestCase):
    def test_start_listens_syncs_the_menu_and_reports_a_recovered_session(self):
        self.mock_recover_previous_session.return_value = 4
        self.engine.start()
        self.assertEqual(self.osc.started, 1)
        self.assertIn((MTS_ENABLE, True), self.osc.sent)
        self.assertIn("recovered 4 shock(s)", self.listener.logs[0])

    def test_a_taken_osc_port_raises_before_touching_session_state(self):
        # The state file may belong to the instance that has the port.
        self.osc.start_error = OSError("Address already in use")
        with self.assertRaises(OSError):
            self.engine.start()
        self.mock_recover_previous_session.assert_not_called()
        self.engine.shutdown()
        self.engine.save_shock_stats()
        self.mock_finalize_session.assert_not_called()
        self.assertEqual(self.sent_commands(), [])

    def test_shutdown_stops_every_shocker_then_finalizes_once(self):
        self.engine.start()
        self.engine.shutdown()
        self.engine.shutdown()
        self.engine.save_shock_stats()
        self.assertEqual(self.sent_commands(), [(0, 300, "Stop")])
        self.mock_finalize_session.assert_called_once_with(0)
        self.assertEqual(self.osc.stopped, 1)

    def test_the_avatar_cannot_re_enable_during_shutdown(self):
        self.engine.start()
        self.engine.shutdown()
        self.engine.on_mts_enable(MTS_ENABLE, True)
        self.assertFalse(self.engine.is_active)


if __name__ == "__main__":
    unittest.main()
