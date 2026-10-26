import random
import threading
import time
from dataclasses import dataclass, replace

from .constants import (
    MTS_COOLDOWN,
    MTS_DURATION,
    MTS_DYNAMIC,
    MTS_ENABLE,
    MTS_INTENSITY,
    MTS_VIBRATE,
)
from .session_log import finalize_session, recover_previous_session, update_session_state

# Stretch below this is treated as "not pulled" even while grabbed.
STRETCH_THRESHOLD = 0.1


@dataclass(frozen=True)
class ShockSettings:
    max_intensity: int = 30  # percent, 1-100
    max_duration: float = 1.0  # seconds, 0.3-10
    cooldown: float = 5.0  # seconds, 1-10
    vibrate: bool = True
    dynamic: bool = False


# How each setting maps onto its in-game menu parameter. The avatar menu works in
# 0-1 floats: intensity is a straight percentage, duration/cooldown use 1% = 100ms.
_OSC_SETTINGS = {
    "max_intensity": (MTS_INTENSITY, lambda v: v / 100.0),
    "max_duration": (MTS_DURATION, lambda v: v / 10.0),
    "cooldown": (MTS_COOLDOWN, lambda v: v / 10.0),
    "vibrate": (MTS_VIBRATE, bool),
    "dynamic": (MTS_DYNAMIC, bool),
}


class EngineListener:
    """Receives engine events. Every method may be called from any thread (OSC
    listener, shock workers, ...), so a UI implementation must marshal onto its own
    UI thread before touching widgets."""

    def on_log(self, message):
        pass

    def on_active_changed(self, is_active):
        pass

    def on_settings_changed(self, settings):
        """Settings were changed from the avatar menu (OSC). Changes made through
        update_settings by the UI itself are not echoed back."""

    def on_shock_count_changed(self, count):
        pass

    def on_status_changed(self):
        """A shock or stretch pull started or ended - see current_output and
        cooldown_remaining."""


class ShockEngine:
    """All shock/OSC behaviour, independent of any UI toolkit."""

    def __init__(self, config, client, osc, listener=None):
        self.config = config
        self.client = client
        self.osc = osc
        self.listener = listener or EngineListener()

        # Replaced wholesale (never mutated) so worker threads can read it without
        # taking the lock - change it through update_settings.
        self.settings = ShockSettings()
        self.is_active = True
        # When the current or last shock should end. We only know when its command was
        # sent, not when the hardware actually starts, so this is an estimate. The
        # cooldown runs from here.
        self.shock_end_time = 0.0
        self._output = None  # "Shock"/"Vibrate" of the current or last shock
        self.is_grabbed = False
        self.current_stretch = 0.0
        self.session_shock_count = 0
        self.is_dynamic_loop_running = False
        self._session_open = False  # start() succeeded and the session isn't finalized
        self._stopping = False
        self.lock = threading.Lock()
        # Held for each OpenShock request, so commands go out one at a time, in order.
        self._send_lock = threading.Lock()

    def _spawn(self, target, *args):
        threading.Thread(target=target, args=args, daemon=True).start()

    def log(self, message):
        self.listener.on_log(message)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self):
        # Raises OSError if the OSC port is taken (e.g. by another instance). Done
        # first so that case leaves the session state alone - it may be the other
        # instance's.
        self.osc.start(self._osc_handlers())
        self._session_open = True
        recovered = recover_previous_session()
        if recovered:
            self.log(f"Previous session didn't exit cleanly - recovered {recovered} shock(s) into shock_log.txt.")
        self.sync_osc()
        self.log("System Started.")

    def save_shock_stats(self):
        # Idempotent: may be invoked twice (e.g. shutdown then atexit on top of it).
        if not self._session_open:
            return
        self._session_open = False
        finalize_session(self.session_shock_count)

    def shutdown(self):
        # Nothing to do if start() failed - the shockers may be in use by another instance.
        if not self._session_open:
            return
        with self.lock:
            self._stopping = True  # ignore the avatar's Enable from here on
            self.is_active = False  # nothing new is sent, and a stretch pull ends
        self.send_halt_command()
        self.save_shock_stats()
        # Last, as it can block for a moment while the listener thread winds down.
        self.osc.stop()

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    def set_active(self, active, from_osc=False):
        with self.lock:
            if active == self.is_active or self._stopping:
                return
            self.is_active = active
            if not active:
                # The halt below cuts any running shock short, so its cooldown starts now.
                self.shock_end_time = min(self.shock_end_time, time.time())

        if active:
            self.log("System Enabled.")
        else:
            self.log("System Disabled.")
            self._spawn(self.send_halt_command)

        self.listener.on_active_changed(active)
        if not from_osc:
            self.osc.send(MTS_ENABLE, active)

    def update_settings(self, from_osc=False, **changes):
        with self.lock:
            old = self.settings
            self.settings = new = replace(old, **changes)

        changed = [name for name in changes if getattr(old, name) != getattr(new, name)]
        if not changed:
            return

        if "dynamic" in changed:
            self.log("Physbone Stretch Mode enabled." if new.dynamic else "Random Mode enabled.")

        if from_osc:
            self.listener.on_settings_changed(new)
        else:
            for name in changed:
                address, encode = _OSC_SETTINGS[name]
                self.osc.send(address, encode(getattr(new, name)))

    def current_output(self):
        """"Shock" or "Vibrate" while one is (estimated to be) running, otherwise None."""
        if not self.is_active:
            return None
        if self.is_dynamic_loop_running or time.time() < self.shock_end_time:
            return self._output
        return None

    def cooldown_remaining(self):
        """Cooldown left after the current or last shock, not counting the shock itself."""
        settings = self.settings
        if not self.is_active or settings.dynamic:
            return 0.0
        remaining = self.shock_end_time + settings.cooldown - time.time()
        return min(max(remaining, 0.0), settings.cooldown)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    def update_config(self, **changes):
        """Saves the given AppConfig fields and applies whichever changed. If the save
        fails it raises with nothing changed, so the caller can report it."""
        config = self.config
        changed = [name for name, value in changes.items() if getattr(config, name) != value]
        if not changed:
            return

        # Save a copy first: the client reads the live config from other threads, so it
        # must never see values that then fail to save.
        replace(config, **changes).save()
        for name in changed:
            setattr(config, name, changes[name])
        self.log("Configuration saved.")

        if "param_grabbed" in changed or "param_stretch" in changed:
            self.log("OSC Parameters changed. Restarting OSC listener...")
            self._spawn(self._restart_osc_server)

    def _restart_osc_server(self):
        self.osc.restart(self._osc_handlers())
        self.log("OSC listener restarted and mapped to new parameters.")

    # ------------------------------------------------------------------
    # OSC: outgoing (avatar menu sync)
    # ------------------------------------------------------------------
    def sync_osc(self):
        settings = self.settings
        self.osc.send(MTS_ENABLE, self.is_active)
        for name, (address, encode) in _OSC_SETTINGS.items():
            self.osc.send(address, encode(getattr(settings, name)))

    # ------------------------------------------------------------------
    # OSC: incoming handlers
    # ------------------------------------------------------------------
    def _osc_handlers(self):
        return {
            self.config.param_grabbed: self.on_grabbed_update,
            self.config.param_stretch: self.on_stretch_update,
            "/avatar/change": self.on_avatar_change,
            MTS_ENABLE: self.on_mts_enable,
            MTS_VIBRATE: self.on_mts_vibrate,
            MTS_DYNAMIC: self.on_mts_dynamic,
            MTS_INTENSITY: self.on_mts_intensity,
            MTS_DURATION: self.on_mts_duration,
            MTS_COOLDOWN: self.on_mts_cooldown,
        }

    def on_avatar_change(self, address, *args):
        self.log("Avatar load detected. Resyncing menu...")

        def delayed_sync():
            time.sleep(1.5)
            self.sync_osc()

        self._spawn(delayed_sync)

    def on_grabbed_update(self, address, *args):
        if args:
            self.is_grabbed = bool(args[0])
            self.evaluate_state()

    def on_stretch_update(self, address, *args):
        if args:
            self.current_stretch = float(args[0])
            self.evaluate_state()

    def on_mts_enable(self, address, *args):
        if args:
            self.set_active(bool(args[0]), from_osc=True)

    def on_mts_vibrate(self, address, *args):
        if args:
            self.update_settings(vibrate=bool(args[0]), from_osc=True)

    def on_mts_dynamic(self, address, *args):
        if args:
            self.update_settings(dynamic=bool(args[0]), from_osc=True)

    def on_mts_intensity(self, address, *args):
        if args:
            # round(), not int(): OSC floats are 32-bit, so e.g. 45% arrives as 0.44999998.
            percent = min(max(round(float(args[0]) * 100), 1), 100)
            self.update_settings(max_intensity=percent, from_osc=True)

    def on_mts_duration(self, address, *args):
        if args:
            val = min(max(float(args[0]), 0.03), 1.0)
            self.update_settings(max_duration=round(val * 10.0, 1), from_osc=True)

    def on_mts_cooldown(self, address, *args):
        if args:
            seconds = min(max(float(args[0]) * 10.0, 1.0), 10.0)
            self.update_settings(cooldown=round(seconds, 1), from_osc=True)

    # ------------------------------------------------------------------
    # Shock triggering
    # ------------------------------------------------------------------
    def _is_pulled(self):
        return self.is_grabbed and self.current_stretch > STRETCH_THRESHOLD

    def evaluate_state(self):
        if self._is_pulled():
            if self.settings.dynamic:
                if not self.is_dynamic_loop_running:
                    self._spawn(self.dynamic_shock_loop)
            else:
                self.trigger_shock()

    def trigger_shock(self):
        if not self.client.is_configured:
            return

        settings = self.settings
        max_d = settings.max_duration
        action_type = "Vibrate" if settings.vibrate else "Shock"
        with self.lock:
            # A stretch pull's cooldown only starts once its loop has finished.
            if not self.is_active or self.is_dynamic_loop_running:
                return
            current_time = time.time()
            if current_time < self.shock_end_time + settings.cooldown:
                return
            duration_s = round(random.uniform(0.3, max_d), 2) if max_d > 0.3 else 0.3
            self.shock_end_time = current_time + duration_s
            self._output = action_type

        self.listener.on_status_changed()

        max_i = settings.max_intensity
        duration_ms = int(duration_s * 1000)
        intensity = random.randint(1, max_i) if max_i > 1 else 1

        if action_type == "Shock":
            self._increment_shock_count()

        self.log(f"Triggering Burst: {intensity}% intensity for {duration_s}s ({action_type})")
        self._spawn(self.send_openshock_command, intensity, duration_ms, action_type)

    def dynamic_shock_loop(self):
        with self.lock:
            if self.is_dynamic_loop_running:
                return
            self.is_dynamic_loop_running = True
            self._output = "Vibrate" if self.settings.vibrate else "Shock"
        self.listener.on_status_changed()

        self.log("Physbone Stretch: Started.")

        is_real_shock = not self.settings.vibrate
        if is_real_shock:
            self._increment_shock_count()

        accumulated_time = 0.0

        while self.is_active and self.settings.dynamic and self._is_pulled():
            settings = self.settings

            stretch_clamped = min(max(self.current_stretch, 0.0), 1.0)
            intensity = max(int(stretch_clamped * settings.max_intensity), 1)

            action_type = "Vibrate" if settings.vibrate else "Shock"
            self._output = action_type

            self.send_openshock_command(intensity, 400, action_type, log_success=False)
            time.sleep(0.2)

            if is_real_shock:
                accumulated_time += 0.2
                if accumulated_time >= 1.0:
                    self._increment_shock_count()
                    accumulated_time -= 1.0

        if self.is_active:
            self.send_openshock_command(0, 300, "Stop", log_success=False)

        self.log("Physbone Stretch: Ended.")

        with self.lock:
            self.is_dynamic_loop_running = False
            self.shock_end_time = time.time()
        self.listener.on_status_changed()

    def send_openshock_command(self, intensity, duration_ms, action_type, log_success=True):
        # One request at a time, so a Stop can't overtake a shock that's already on its
        # way. A shock still waiting its turn when the system is disabled is dropped.
        with self._send_lock:
            if action_type != "Stop" and not self.is_active:
                return
            result = self.client.send(intensity, duration_ms, action_type)
        if result is None:
            return
        success, message = result
        if log_success:
            self.log(message)

    def send_halt_command(self):
        self.send_openshock_command(0, 300, "Stop")

    def _increment_shock_count(self):
        with self.lock:
            self.session_shock_count += 1
            count = self.session_shock_count
            # Persisted immediately (not just at exit) so the count survives a hard
            # kill - SteamVR force-closing us or an OS shutdown never runs our
            # shutdown code at all, so exit-time logging alone can't be relied on.
            update_session_state(count)
        self.listener.on_shock_count_changed(count)
