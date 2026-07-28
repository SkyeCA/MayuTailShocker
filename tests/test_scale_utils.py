import unittest

from mts.scale_utils import snap_to_resolution


class SnapToResolutionTests(unittest.TestCase):
    def test_snaps_down_to_the_nearest_step(self):
        self.assertEqual(snap_to_resolution(7.32, 0.5), 7.5)

    def test_snaps_up_to_the_nearest_step(self):
        self.assertEqual(snap_to_resolution(7.2, 0.5), 7.0)

    def test_value_already_on_a_step_is_unchanged(self):
        self.assertEqual(snap_to_resolution(3.0, 0.5), 3.0)

    def test_sub_one_resolution_keeps_fractional_seconds(self):
        # OpenShock's duration slider uses a 0.1s resolution.
        self.assertEqual(snap_to_resolution(1.24, 0.1), 1.2)

    def test_whole_number_resolution_snaps_to_whole_numbers(self):
        # PiShock's duration slider uses a 1.0s resolution (whole seconds only).
        self.assertEqual(snap_to_resolution(2.6, 1.0), 3.0)

    def test_is_int_returns_a_python_int_not_a_float(self):
        result = snap_to_resolution(29.6, 1, is_int=True)
        self.assertEqual(result, 30)
        self.assertIsInstance(result, int)

    def test_is_int_false_returns_a_float(self):
        result = snap_to_resolution(3.0, 0.5, is_int=False)
        self.assertIsInstance(result, float)

    def test_accepts_string_input_like_ttk_scale_command_provides(self):
        # ttk.Scale's `command` callback passes the new value as a string.
        self.assertEqual(snap_to_resolution("7.2", 0.5), 7.0)


if __name__ == "__main__":
    unittest.main()
