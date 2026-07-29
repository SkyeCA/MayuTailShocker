import random
from typing import List, Optional, Tuple

import requests

from .constants import USER_AGENT
from .shocker_client import ShockerClient

CONTROL_URL = "https://api.openshock.app/2/shockers/control"
ACTION_TYPES = {"Stop": 0, "Shock": 1, "Vibrate": 2, "Sound": 3}


class OpenShockClient(ShockerClient):
    """Thin wrapper around the OpenShock HTTP control API."""

    PROVIDER_KEY = "openshock"
    PROVIDER_LABEL = "OpenShock"
    ID_LABEL = "Shocker ID"
    MIN_DURATION_MS = 300
    MAX_DURATION_MS = 10000
    DURATION_RESOLUTION_S = 0.1

    def __init__(self, api_key: str = "", shocker_ids: Optional[List[str]] = None, shocker_mode: str = "All"):
        self.api_key = api_key
        self.shocker_ids = shocker_ids or []
        self.shocker_mode = shocker_mode

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.shocker_ids)

    def _target_ids(self, force_all: bool = False) -> List[str]:
        if not force_all and self.shocker_mode == "Random" and len(self.shocker_ids) > 1:
            return [random.choice(self.shocker_ids)]
        return self.shocker_ids

    def send(self, intensity: int, duration_ms: int, action_type: str, force_all: bool = False) -> Optional[Tuple[bool, str]]:
        """Send a control command. Returns (success, message), or None if unconfigured.

        force_all bypasses "Random" shocker mode and targets every configured
        shocker - used by the manual test command.
        """
        if not self.is_configured:
            return None

        action_int = ACTION_TYPES.get(action_type, ACTION_TYPES["Vibrate"])
        payload = {
            "shocks": [
                {"id": sid, "type": action_int, "intensity": intensity, "duration": duration_ms}
                for sid in self._target_ids(force_all)
            ],
            "customName": "MayuTailShocker",
        }
        headers = {
            "OpenShockToken": self.api_key,
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(CONTROL_URL, json=payload, headers=headers, timeout=2.0)
        except Exception:
            return False, "FAIL SAFE: Could not send command (HTTP Timeout/Error)."

        if response.status_code == 200:
            return True, f"SUCCESS (HTTP): {action_type} command sent."
        return False, f"HTTP Error: Received {response.status_code} from OpenShock API"
