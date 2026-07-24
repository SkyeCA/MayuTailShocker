import json
import os
import tempfile
from datetime import datetime
from typing import Optional

from .constants import SESSION_STATE_FILE, SHOCK_LOG_FILE


def _append_log(message: str):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(SHOCK_LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def update_session_state(shock_count: int):
    """Durably persist the running count so it survives a hard kill (TerminateProcess,
    SteamVR force-closing us, an OS shutdown). Written atomically so a crash mid-write
    can't corrupt it; called on every shock, not just at exit."""
    directory = os.path.dirname(SESSION_STATE_FILE) or "."
    try:
        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".session_state_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump({"shock_count": shock_count}, f)
            os.replace(tmp_path, SESSION_STATE_FILE)
        except Exception:
            os.remove(tmp_path)
    except Exception:
        pass


def clear_session_state():
    try:
        os.remove(SESSION_STATE_FILE)
    except FileNotFoundError:
        pass
    except Exception:
        pass


def finalize_session(shock_count: int):
    """Called on a clean shutdown: log the final count and clear the state file."""
    if shock_count > 0:
        _append_log(f"Session ended. Total shocks sent/scaled: {shock_count}")
    clear_session_state()


def recover_previous_session() -> Optional[int]:
    """Called on startup. If the last session left behind state, it didn't shut down
    cleanly (crash / hard kill) - log what we last knew its count to be, then clear it.
    Returns the recovered count, or None if there was nothing to recover."""
    if not os.path.exists(SESSION_STATE_FILE):
        return None

    shock_count = None
    try:
        with open(SESSION_STATE_FILE, "r") as f:
            data = json.load(f)
        shock_count = int(data.get("shock_count", 0))
    except Exception:
        shock_count = None

    if shock_count:
        _append_log(f"Previous session did not exit cleanly. Last known shock count: {shock_count}")

    clear_session_state()
    return shock_count
