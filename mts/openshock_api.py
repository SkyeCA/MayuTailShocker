import logging
import random
from typing import List, Optional, Tuple

import requests

from .constants import USER_AGENT

CONTROL_URL = "https://api.openshock.app/2/shockers/control"
ACTION_TYPES = {"Stop": 0, "Shock": 1, "Vibrate": 2, "Sound": 3}

logger = logging.getLogger(__name__)


class OpenShockClient:
    """Thin wrapper around the OpenShock HTTP control API."""

    def __init__(self, api_key: str = "", shocker_ids: Optional[List[str]] = None, shocker_mode: str = "All"):
        self.api_key = api_key
        self.shocker_ids = shocker_ids or []
        self.shocker_mode = shocker_mode

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.shocker_ids)

    def _target_ids(self, action_type: str) -> List[str]:
        # A Stop always goes to every shocker: in Random mode we can't be sure which one
        # is still running.
        if action_type != "Stop" and self.shocker_mode == "Random" and len(self.shocker_ids) > 1:
            return [random.choice(self.shocker_ids)]
        return self.shocker_ids

    def send(self, intensity: int, duration_ms: int, action_type: str) -> Optional[Tuple[bool, str]]:
        """Send a control command. Returns (success, message), or None if unconfigured."""
        if not self.is_configured:
            return None

        action_int = ACTION_TYPES.get(action_type, ACTION_TYPES["Vibrate"])
        payload = {
            "shocks": [
                {"id": sid, "type": action_int, "intensity": intensity, "duration": duration_ms}
                for sid in self._target_ids(action_type)
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
        except Exception as e:
            logger.warning("%s request failed: %r", action_type, e)
            return False, "FAIL SAFE: Could not send command (HTTP Timeout/Error)."

        if response.status_code == 200:
            return True, f"SUCCESS (HTTP): {action_type} command sent."
        logger.warning("%s request got HTTP %s: %s", action_type, response.status_code, response.text[:300])
        return False, f"HTTP Error: Received {response.status_code} from OpenShock API"
