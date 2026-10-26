import logging
import random
from typing import List, Optional, Tuple

import requests

from .constants import USER_AGENT

CONTROL_URL = "https://api.openshock.app/2/shockers/control"
ACTION_TYPES = {"Stop": 0, "Shock": 1, "Vibrate": 2, "Sound": 3}

logger = logging.getLogger(__name__)


class OpenShockClient:
    """Thin wrapper around the OpenShock HTTP control API. Reads the token, shocker IDs
    and mode from the AppConfig on every send, so saved changes apply straight away."""

    def __init__(self, config):
        self.config = config

    @property
    def is_configured(self) -> bool:
        return self.config.is_complete

    def _target_ids(self, action_type: str) -> List[str]:
        shocker_ids = self.config.shocker_ids
        # A Stop always goes to every shocker: in Random mode we can't be sure which one
        # is still running.
        if action_type != "Stop" and self.config.shocker_mode == "Random" and len(shocker_ids) > 1:
            return [random.choice(shocker_ids)]
        return shocker_ids

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
            "OpenShockToken": self.config.api_key,
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
