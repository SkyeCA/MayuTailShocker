import json
import os
from dataclasses import asdict, dataclass, field
from typing import List, Optional, Tuple

from .constants import CONFIG_FILE, DEFAULT_PARAM_GRABBED, DEFAULT_PARAM_STRETCH

PROVIDERS = ("openshock", "pishock")


@dataclass
class AppConfig:
    provider: str = "openshock"

    openshock_api_key: str = ""
    openshock_shocker_ids: List[str] = field(default_factory=list)
    openshock_shocker_mode: str = "All"

    pishock_username: str = ""
    pishock_api_key: str = ""
    pishock_share_codes: List[str] = field(default_factory=list)
    pishock_shocker_mode: str = "All"

    param_grabbed: str = DEFAULT_PARAM_GRABBED
    param_stretch: str = DEFAULT_PARAM_STRETCH

    @property
    def is_complete(self) -> bool:
        if self.provider == "pishock":
            return bool(self.pishock_username and self.pishock_api_key and self.pishock_share_codes)
        return bool(self.openshock_api_key and self.openshock_shocker_ids)

    def save(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(asdict(self), f, indent=4)


def load_config() -> Tuple[AppConfig, Optional[str]]:
    """Load AppConfig from disk.

    Returns (config, error). error is "parse_error" if the file exists but
    could not be read, otherwise None (including when no file exists yet).
    """
    if not os.path.exists(CONFIG_FILE):
        return AppConfig(), None

    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
    except Exception:
        return AppConfig(), "parse_error"

    provider = data.get("provider", "openshock")
    if provider not in PROVIDERS:
        provider = "openshock"

    cfg = AppConfig(
        provider=provider,
        openshock_api_key=data.get("openshock_api_key", ""),
        openshock_shocker_ids=data.get("openshock_shocker_ids", []),
        openshock_shocker_mode=data.get("openshock_shocker_mode", "All"),
        pishock_username=data.get("pishock_username", ""),
        pishock_api_key=data.get("pishock_api_key", ""),
        pishock_share_codes=data.get("pishock_share_codes", []),
        pishock_shocker_mode=data.get("pishock_shocker_mode", "All"),
        param_grabbed=data.get("param_grabbed") or DEFAULT_PARAM_GRABBED,
        param_stretch=data.get("param_stretch") or DEFAULT_PARAM_STRETCH,
    )

    # Migrate the old pre-multi-provider flat config format (api_key/shocker_ids/
    # shocker_mode with no provider field) into the openshock_* fields.
    if "provider" not in data:
        legacy_api_key = data.get("api_key")
        legacy_shocker_ids = data.get("shocker_ids")
        if legacy_api_key and not cfg.openshock_api_key:
            cfg.openshock_api_key = legacy_api_key
        if legacy_shocker_ids and not cfg.openshock_shocker_ids:
            cfg.openshock_shocker_ids = list(legacy_shocker_ids)
        if data.get("shocker_mode") and cfg.openshock_shocker_mode == "All":
            cfg.openshock_shocker_mode = data["shocker_mode"]

        # Migrate the even older single-shocker config format.
        legacy_id = data.get("shocker_id")
        if legacy_id and legacy_id not in cfg.openshock_shocker_ids:
            cfg.openshock_shocker_ids.append(legacy_id)

        cfg.save()

    if len(cfg.openshock_shocker_ids) <= 1:
        cfg.openshock_shocker_mode = "All"
    if len(cfg.pishock_share_codes) <= 1:
        cfg.pishock_shocker_mode = "All"

    return cfg, None
