import time
import unittest

from pythonosc.udp_client import SimpleUDPClient

from mts.osc_bridge import OSCBridge


class OSCBridgeTests(unittest.TestCase):
    """Uses port 0 (OS-assigned ephemeral port) so tests can't collide with a real
    instance of the app or with each other."""

    def test_stop_before_start_does_not_raise(self):
        OSCBridge("127.0.0.1", 0, 0).stop()

    def test_start_launches_a_running_listener_thread(self):
        bridge = OSCBridge("127.0.0.1", 0, 0)
        bridge.start({})
        try:
            self.assertTrue(bridge.thread.is_alive())
        finally:
            bridge.stop()

    def test_stop_shuts_down_the_listener_thread(self):
        bridge = OSCBridge("127.0.0.1", 0, 0)
        bridge.start({})
        bridge.stop()
        bridge.thread.join(timeout=2)
        self.assertFalse(bridge.thread.is_alive())

    def test_restart_swaps_in_a_fresh_server_and_stays_alive(self):
        bridge = OSCBridge("127.0.0.1", 0, 0)
        bridge.start({})
        first_server = bridge.server
        try:
            bridge.restart({})
            self.assertIsNot(bridge.server, first_server)
            self.assertTrue(bridge.thread.is_alive())
        finally:
            bridge.stop()

    def test_send_to_an_unreachable_target_does_not_raise(self):
        bridge = OSCBridge("127.0.0.1", 0, 1)  # port 1: nothing listening there
        bridge.send("/some/address", 1.0)

    def test_incoming_message_is_dispatched_to_the_mapped_handler(self):
        received = []
        bridge = OSCBridge("127.0.0.1", 0, 0)
        bridge.start({"/test/addr": lambda address, *args: received.append(args)})
        try:
            listen_port = bridge.server.server_address[1]
            with SimpleUDPClient("127.0.0.1", listen_port) as client:
                client.send_message("/test/addr", 42)

            deadline = time.time() + 2
            while not received and time.time() < deadline:
                time.sleep(0.02)

            self.assertEqual(received, [(42,)])
        finally:
            bridge.stop()

    def test_message_to_an_unmapped_address_is_ignored_not_fatal(self):
        received = []
        bridge = OSCBridge("127.0.0.1", 0, 0)
        bridge.start({"/mapped": lambda address, *args: received.append(args)})
        try:
            listen_port = bridge.server.server_address[1]
            with SimpleUDPClient("127.0.0.1", listen_port) as client:
                client.send_message("/not-mapped", 1)
                client.send_message("/mapped", 99)

            deadline = time.time() + 2
            while not received and time.time() < deadline:
                time.sleep(0.02)

            self.assertEqual(received, [(99,)])
        finally:
            bridge.stop()


if __name__ == "__main__":
    unittest.main()
