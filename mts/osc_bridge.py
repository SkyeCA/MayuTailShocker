import threading

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient


class OSCBridge:
    """Owns the OSC send client plus a restartable listener thread/server."""

    def __init__(self, ip, listen_port, send_port):
        self.ip = ip
        self.listen_port = listen_port
        self.client = SimpleUDPClient(ip, send_port)
        self.server = None
        self.thread = None

    def start(self, handlers: dict):
        dispatcher = Dispatcher()
        for address, handler in handlers.items():
            dispatcher.map(address, handler)

        self.server = BlockingOSCUDPServer((self.ip, self.listen_port), dispatcher)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def restart(self, handlers: dict):
        self.stop()
        self.start(handlers)

    def stop(self):
        if self.server:
            try:
                self.server.shutdown()
            except Exception:
                pass

    def send(self, address, value):
        try:
            self.client.send_message(address, value)
        except Exception:
            pass
