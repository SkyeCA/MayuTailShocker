import json
import os
from dataclasses import asdict, dataclass, field
from typing import List, Optional, Tuple

from .constants import CONFIG_FILE, DEFAULT_PARAM_GRABBED, DEFAULT_PARAM_STRETCH


@dataclass
class AppConfig:
    api_key: str = ""
    shocker_ids: List[str] = field(default_factory=list)
    shocker_mode: str = "All"
    param_grabbed: str = DEFAULT_PARAM_GRABBED
    param_stretch: str = DEFAULT_PARAM_STRETCH

    @property
    def is_complete(self) -> bool:
        return bool(self.api_key and self.shocker_ids)

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

    cfg = AppConfig(
        api_key=data.get("api_key", ""),
        shocker_ids=data.get("shocker_ids", []),
        shocker_mode=data.get("shocker_mode", "All"),
        param_grabbed=data.get("param_grabbed") or DEFAULT_PARAM_GRABBED,
        param_stretch=data.get("param_stretch") or DEFAULT_PARAM_STRETCH,
    )

    # Migrate the old single-shocker config format.
    legacy_id = data.get("shocker_id")
    if legacy_id and legacy_id not in cfg.shocker_ids:
        cfg.shocker_ids.append(legacy_id)
        cfg.save()

    if len(cfg.shocker_ids) <= 1:
        cfg.shocker_mode = "All"

    return cfg, None
