import random
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

import requests

from .constants import USER_AGENT
from .shocker_client import ShockerClient

API_BASE = "https://api.pishock.com"
OPERATE_URL = f"{API_BASE}/Shockers"
SHARE_URL = f"{API_BASE}/Share"
GET_SHARED_URL = f"{API_BASE}/Share/GetShared"
ACTION_OPS = {"Shock": 0, "Vibrate": 1, "Beep": 2}

# Reference: https://api.pishock.com/swagger/v1/swagger.json (PiShock Public API v1).
# The old do.pishock.com/api/apioperate endpoint used in previous versions of this
# app is undocumented and returns a bare 404 for every request now.
ERROR_MESSAGES = {
    401: "Unauthorized - check your PiShock Username and API Key in File > API Config.",
    403: "Forbidden - this API Key doesn't have access to that shocker.",
    404: "Could not find that Share Code - check it for typos in File > Shocker Config.",
    405: "That operation isn't allowed on this share (e.g. shock disabled on it).",
    406: "Device isn't running PiShock V3 firmware.",
    410: "Share is locked, or already claimed by a different PiShock account.",
    412: "Intensity is out of bounds for this share.",
    416: "Duration is out of bounds for this share (16ms-15000ms, or lower than the share's own max).",
    503: "Share or shocker is paused.",
}


class PiShockClient(ShockerClient):
    """Thin wrapper around the PiShock Public API v1 (api.pishock.com).

    Unlike OpenShock, PiShock has no "Stop" operation and no way to cancel an
    in-flight command early. A "shocker" is identified to users by the Share
    Code they were given - the same code PiShock's own app uses - but v1's
    operate endpoint (POST /Shockers/{ShockerId}) needs the numeric ID that
    code resolves to *after* being claimed onto the account. Both the
    claiming (PUT /Share) and the resolution (GET /Share/GetShared) happen
    transparently here so the app's UI never has to expose that distinction.
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
        # Share Code -> numeric Shocker ID, resolved lazily via GET /Share/GetShared.
        self._id_cache: Dict[str, int] = {}
        self._cache_lock = threading.Lock()

    @property
    def is_configured(self) -> bool:
        return bool(self.username and self.api_key and self.share_codes)

    def _target_codes(self, force_all: bool = False) -> List[str]:
        if not force_all and self.shocker_mode == "Random" and len(self.share_codes) > 1:
            return [random.choice(self.share_codes)]
        return self.share_codes

    def send(self, intensity: int, duration_ms: int, action_type: str, force_all: bool = False) -> Optional[Tuple[bool, str]]:
        """Send a control command. Returns (success, message), or None if unconfigured
        or the action isn't supported (PiShock has no Stop - see class docstring).

        force_all bypasses "Random" shocker mode and targets every configured
        shocker - used by the manual test command.
        """
        if not self.is_configured:
            return None
        if action_type == "Stop":
            return None

        op = ACTION_OPS.get(action_type, ACTION_OPS["Vibrate"])
        duration_ms = max(16, min(15000, duration_ms))
        codes = self._target_codes(force_all)

        if len(codes) == 1:
            return self._send_one(codes[0], op, duration_ms, intensity, action_type)

        with ThreadPoolExecutor(max_workers=len(codes)) as pool:
            results = list(pool.map(lambda code: self._send_one(code, op, duration_ms, intensity, action_type), codes))

        if all(ok for ok, _ in results):
            return True, f"SUCCESS: {action_type} command sent to {len(codes)} shockers."
        return False, "; ".join(message for _, message in results)

    def _send_one(self, code: str, op: int, duration_ms: int, intensity: int, action_type: str) -> Tuple[bool, str]:
        shocker_id, error = self._resolve_shocker_id(code)
        if error:
            return False, error

        payload = {
            "AgentName": "MayuTailShocker",
            "Operation": op,
            "Duration": duration_ms,
            "Intensity": intensity,
        }

        try:
            response = requests.post(f"{OPERATE_URL}/{shocker_id}", json=payload, headers=self._auth_headers(), timeout=2.0)
        except Exception:
            return False, "FAIL SAFE: Could not send command (HTTP Timeout/Error)."

        if response.status_code == 204:
            return True, f"SUCCESS: {action_type} command sent."

        if response.status_code == 404:
            # Cached ID no longer resolves (share revoked/re-issued on PiShock's end) -
            # drop it so the next attempt re-claims/re-resolves instead of failing forever.
            with self._cache_lock:
                self._id_cache.pop(code, None)

        return False, f"PiShock Error: {response.status_code} - {self._describe_error(response)}"

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "X-PiShock-Api-Key": self.api_key,
            "X-PiShock-Username": self.username,
        }

    def _resolve_shocker_id(self, code: str) -> Tuple[Optional[int], Optional[str]]:
        """Look up the numeric Shocker ID for a Share Code, claiming the code onto
        this account first if it hasn't been added yet. Returns (id, None) on
        success or (None, error_message) on failure."""
        with self._cache_lock:
            if code not in self._id_cache:
                if not self._refresh_shared_cache():
                    return None, "PiShock Error: could not reach PiShock to look up your Share Code (network/timeout)."

            if code not in self._id_cache:
                claim_error = self._claim_share_code(code)
                if claim_error:
                    return None, claim_error
                self._refresh_shared_cache()

            if code in self._id_cache:
                return self._id_cache[code], None

            return None, (
                f"PiShock Error: Share Code '{code}' isn't linked to this PiShock account and "
                "couldn't be added automatically. Double-check it's correct and hasn't already "
                "been claimed by a different account."
            )

    def _refresh_shared_cache(self) -> bool:
        """Repopulates the Share Code -> Shocker ID cache from GET /Share/GetShared.
        Caller must hold self._cache_lock."""
        try:
            response = requests.get(GET_SHARED_URL, headers=self._auth_headers(), timeout=2.0)
        except Exception:
            return False
        if response.status_code != 200:
            return False
        try:
            shared = response.json()
        except ValueError:
            return False

        self._id_cache = {
            item["ShareCode"]: item["Id"]
            for item in shared
            if isinstance(item, dict) and "ShareCode" in item and "Id" in item
        }
        return True

    def _claim_share_code(self, code: str) -> Optional[str]:
        """Adds a Share Code to this account via PUT /Share, mirroring what a user
        would otherwise do by hand in PiShock's own app. Caller must hold
        self._cache_lock. Returns an error message, or None on success."""
        try:
            response = requests.put(SHARE_URL, json={"Shares": [code]}, headers=self._auth_headers(), timeout=2.0)
        except Exception:
            return "PiShock Error: could not reach PiShock to add your Share Code (network/timeout)."

        # 410 means a share in the request is already claimed - possibly by us
        # already (fine, the next cache refresh will find it) or by someone else
        # (the refresh will still miss it, and _resolve_shocker_id reports that).
        if response.status_code in (204, 410):
            return None

        return f"PiShock Error: {response.status_code} - {self._describe_error(response)}"

    @staticmethod
    def _describe_error(response) -> str:
        """PiShock sometimes returns a structured JSON problem body (e.g. field-level
        validation errors) in addition to the plain per-status descriptions below -
        prefer that when present since it's more specific."""
        try:
            body = response.json()
        except ValueError:
            body = None

        if isinstance(body, dict):
            parts = []
            message = body.get("Message") or body.get("message")
            if message:
                parts.append(message)
            errors = body.get("Errors") or body.get("errors")
            if isinstance(errors, dict):
                for field, msgs in errors.items():
                    msgs = ", ".join(msgs) if isinstance(msgs, list) else msgs
                    parts.append(f"{field}: {msgs}")
            if parts:
                return " - ".join(parts)

        return ERROR_MESSAGES.get(response.status_code, response.text.strip() or "Unknown error.")
