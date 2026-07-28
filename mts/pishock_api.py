import random
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Tuple

import requests

from .constants import USER_AGENT
from .shocker_client import ShockerClient

OPERATE_URL = "https://do.pishock.com/api/apioperate"
ACTION_OPS = {"Shock": 0, "Vibrate": 1, "Beep": 2}


class PiShockClient(ShockerClient):
    """Thin wrapper around the PiShock HTTP operate API.

    Unlike OpenShock, PiShock has no "Stop" operation and no way to cancel an
    in-flight command early, and Duration is a whole integer number of
    seconds (1-15) rather than milliseconds - see https://apidocs.pishock.com/.
    A "shocker" is identified by a per-device "share code" rather than an ID.
    """

    PROVIDER_KEY = "pishock"
    PROVIDER_LABEL = "PiShock"
    ID_LABEL = "Share Code"
    MIN_DURATION_MS = 1000
    MAX_DURATION_MS = 15000
    DURATION_RESOLUTION_S = 1.0

    # PiShock can't fire faster than once/second (whole-second durations, no
    # cancel), so Dynamic Mode is throttled to match instead of pulsing every 200ms.
    DYNAMIC_PULSE_INTERVAL_S = 1.0
    DYNAMIC_PULSE_DURATION_MS = 1000

    def __init__(self, username: str = "", api_key: str = "", share_codes: Optional[List[str]] = None, shocker_mode: str = "All"):
        self.username = username
        self.api_key = api_key
        self.share_codes = share_codes or []
        self.shocker_mode = shocker_mode

    @property
    def is_configured(self) -> bool:
        return bool(self.username and self.api_key and self.share_codes)

    def _target_codes(self) -> List[str]:
        if self.shocker_mode == "Random" and len(self.share_codes) > 1:
            return [random.choice(self.share_codes)]
        return self.share_codes

    def send(self, intensity: int, duration_ms: int, action_type: str) -> Optional[Tuple[bool, str]]:
        """Send a control command. Returns (success, message), or None if unconfigured
        or the action isn't supported (PiShock has no Stop - see class docstring)."""
        if not self.is_configured:
            return None
        if action_type == "Stop":
            return None

        op = ACTION_OPS.get(action_type, ACTION_OPS["Vibrate"])
        duration_s = max(1, min(15, round(duration_ms / 1000)))
        codes = self._target_codes()

        if len(codes) == 1:
            return self._send_one(codes[0], op, duration_s, intensity, action_type)

        with ThreadPoolExecutor(max_workers=len(codes)) as pool:
            results = list(pool.map(lambda code: self._send_one(code, op, duration_s, intensity, action_type), codes))

        if all(ok for ok, _ in results):
            return True, f"SUCCESS: {action_type} command sent to {len(codes)} shockers."
        return False, "; ".join(message for _, message in results)

    def _send_one(self, code: str, op: int, duration_s: int, intensity: int, action_type: str) -> Tuple[bool, str]:
        payload = {
            "Username": self.username,
            "Apikey": self.api_key,
            "Code": code,
            "Name": "MayuTailShocker",
            "Op": op,
            "Duration": duration_s,
            "Intensity": intensity,
        }
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(OPERATE_URL, json=payload, headers=headers, timeout=2.0)
        except Exception:
            return False, "FAIL SAFE: Could not send command (HTTP Timeout/Error)."

        text = response.text.strip()
        if response.status_code == 200 and "succeeded" in text.lower():
            return True, f"SUCCESS: {action_type} command sent."
        return False, f"PiShock Error: {text or response.status_code}"
