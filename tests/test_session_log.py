import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from mts import session_log


class SessionLogTestCase(unittest.TestCase):
    """Redirects the state/log files to a scratch dir so tests never touch real ones."""

    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)
        self.state_path = Path(self.tmp_dir.name) / "session_state.json"
        self.log_path = Path(self.tmp_dir.name) / "shock_log.txt"

        state_patcher = patch("mts.session_log.SESSION_STATE_FILE", str(self.state_path))
        log_patcher = patch("mts.session_log.SHOCK_LOG_FILE", str(self.log_path))
        state_patcher.start()
        log_patcher.start()
        self.addCleanup(state_patcher.stop)
        self.addCleanup(log_patcher.stop)


class UpdateSessionStateTests(SessionLogTestCase):
    def test_persists_the_given_count(self):
        session_log.update_session_state(3)
        self.assertEqual(json.loads(self.state_path.read_text()), {"shock_count": 3})

    def test_overwrites_the_previous_value(self):
        session_log.update_session_state(1)
        session_log.update_session_state(5)
        self.assertEqual(json.loads(self.state_path.read_text()), {"shock_count": 5})

    def test_does_not_leave_temp_files_behind(self):
        session_log.update_session_state(1)
        leftovers = [p for p in Path(self.tmp_dir.name).iterdir() if p.name.startswith(".session_state_")]
        self.assertEqual(leftovers, [])


class ClearSessionStateTests(SessionLogTestCase):
    def test_removes_an_existing_state_file(self):
        session_log.update_session_state(1)
        session_log.clear_session_state()
        self.assertFalse(self.state_path.exists())

    def test_is_a_no_op_when_there_is_nothing_to_clear(self):
        session_log.clear_session_state()  # must not raise


class FinalizeSessionTests(SessionLogTestCase):
    def test_logs_and_clears_state_when_shocks_happened(self):
        session_log.update_session_state(4)
        session_log.finalize_session(4)
        self.assertFalse(self.state_path.exists())
        self.assertIn("Session ended. Total shocks sent/scaled: 4", self.log_path.read_text())

    def test_skips_the_log_entirely_when_there_were_no_shocks(self):
        session_log.finalize_session(0)
        self.assertFalse(self.log_path.exists())

    def test_still_clears_leftover_state_when_there_were_no_shocks(self):
        session_log.update_session_state(0)
        session_log.finalize_session(0)
        self.assertFalse(self.state_path.exists())


class RecoverPreviousSessionTests(SessionLogTestCase):
    def test_returns_none_when_nothing_was_left_behind(self):
        self.assertIsNone(session_log.recover_previous_session())

    def test_recovers_and_logs_a_leftover_count_then_clears_it(self):
        # Simulates a hard kill: state was written mid-session but never finalized.
        session_log.update_session_state(7)
        recovered = session_log.recover_previous_session()
        self.assertEqual(recovered, 7)
        self.assertFalse(self.state_path.exists())
        self.assertIn("Last known shock count: 7", self.log_path.read_text())

    def test_leftover_zero_count_is_cleared_without_a_log_entry(self):
        session_log.update_session_state(0)
        recovered = session_log.recover_previous_session()
        self.assertEqual(recovered, 0)
        self.assertFalse(self.log_path.exists())

    def test_corrupt_state_file_is_handled_gracefully(self):
        self.state_path.write_text("not valid json")
        recovered = session_log.recover_previous_session()
        self.assertIsNone(recovered)
        self.assertFalse(self.state_path.exists())


if __name__ == "__main__":
    unittest.main()
