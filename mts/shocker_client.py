from abc import ABC, abstractmethod
from typing import Optional, Tuple


class ShockerClient(ABC):
    """Common contract both provider clients (OpenShock, PiShock) implement.

    Provider-specific quirks (min/max duration, what a "shocker" is called in
    the UI) are exposed as class attributes so app.py and the dialogs can stay
    generic instead of branching on provider name.
    """

    PROVIDER_KEY: str = ""
    PROVIDER_LABEL: str = ""
    ID_LABEL: str = "Shocker ID"
    MIN_DURATION_MS: int = 300
    MAX_DURATION_MS: int = 10000
    DURATION_RESOLUTION_S: float = 0.1

    # Physbone Stretch (Dynamic) Mode re-triggers on a timer while the tail is
    # held; these control how often it re-sends and how long each pulse lasts.
    DYNAMIC_PULSE_INTERVAL_S: float = 0.2
    DYNAMIC_PULSE_DURATION_MS: int = 400

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    def send(self, intensity: int, duration_ms: int, action_type: str) -> Optional[Tuple[bool, str]]:
        """Send a control command. Returns (success, message), or None if unconfigured
        or the action isn't supported by this provider (e.g. PiShock has no Stop)."""
        ...


def build_client(config) -> ShockerClient:
    """Construct the ShockerClient for whichever provider is active in config."""
    from .openshock_api import OpenShockClient
    from .pishock_api import PiShockClient

    if config.provider == PiShockClient.PROVIDER_KEY:
        return PiShockClient(config.pishock_username, config.pishock_api_key, config.pishock_share_codes, config.pishock_shocker_mode)
    return OpenShockClient(config.openshock_api_key, config.openshock_shocker_ids, config.openshock_shocker_mode)
