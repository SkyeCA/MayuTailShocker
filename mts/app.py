import atexit
import random
import signal
import threading
import time
import webbrowser
from datetime import datetime

import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, scrolledtext, ttk

from .config import load_config
from .constants import (
    ABOUT_URL,
    DEFAULT_PARAM_GRABBED,
    DEFAULT_PARAM_STRETCH,
    GITHUB_URL,
    MTS_COOLDOWN,
    MTS_DURATION,
    MTS_DYNAMIC,
    MTS_ENABLE,
    MTS_INTENSITY,
    MTS_VIBRATE,
    OSC_IP,
    OSC_PORT,
    OSC_SEND_PORT,
    resource_path,
)
from .modals import APIConfigModal, OSCConfigModal, ShockerConfigModal
from .osc_bridge import OSCBridge
from .shocker_client import build_client
from .session_log import finalize_session, recover_previous_session, update_session_state
from .version import __version__


class TailShockerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mayu Tail Shocker")
        icon_image = self._load_icon_image()
        if icon_image is not None:
            self.root.iconphoto(True, icon_image)
        self.root.geometry("500x740")

        self.config, config_error = load_config()
        self.client = build_client(self.config)

        self.is_active = True
        self.last_shock_time = 0.0
        self.is_grabbed = False
        self.current_stretch = 0.0
        self.session_shock_count = 0
        self.is_dynamic_loop_running = False
        self._session_finalized = False
        self.lock = threading.Lock()

        self.osc = OSCBridge(OSC_IP, OSC_PORT, OSC_SEND_PORT)
        self._updating_from_osc = False

        self._setup_style()
        self._build_menu()
        self._build_gui()
        self._log_config_status(config_error)
        self._recover_previous_session()
        self.osc.start(self._osc_handlers())

        self._sync_all_osc()
        self.log_message("System Started.")

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def _load_icon_image(self):
        try:
            return tk.PhotoImage(file=resource_path("resources/icon.png"))
        except Exception:
            return None

    def _setup_style(self):
        style = ttk.Style(self.root)
        # Prefer each platform's native ttk theme; "clam" is the fallback for
        # platforms (mainly Linux) where the default theme still looks like Tk 8.5.
        for theme in ("vista", "aqua", "clam"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break

        bold = ("Helvetica", 10, "bold")
        style.configure("Vibrate.TCheckbutton", foreground="blue", font=bold)
        style.configure("Dynamic.TCheckbutton", foreground="purple", font=bold)
        style.configure("Status.TLabel", font=("Helvetica", 12, "bold"))
        self.style = style

    def _make_scale(self, parent, label_fmt, variable, frm, to, resolution):
        """A ttk.Scale wrapper that snaps to `resolution` and shows the current
        value in a label above it - ttk.Scale (unlike tk.Scale) has no built-in
        resolution or label option, so both are reimplemented here.

        The resolution is kept in a one-item list (rather than a plain closure
        variable) so it can still be changed later via scale.set_resolution(),
        which _apply_duration_bounds() needs when the provider switches.
        """
        is_int = isinstance(variable, tk.IntVar)
        resolution_holder = [resolution]
        label = ttk.Label(parent, text=label_fmt.format(variable.get()))
        label.pack(fill=tk.X, pady=(8, 0))

        def on_move(value):
            step = resolution_holder[0]
            snapped = round(float(value) / step) * step
            snapped = int(round(snapped)) if is_int else round(snapped, 2)
            if snapped != variable.get():
                variable.set(snapped)
            label.config(text=label_fmt.format(snapped))

        scale = ttk.Scale(parent, from_=frm, to=to, orient=tk.HORIZONTAL, variable=variable, command=on_move)
        scale.pack(fill=tk.X, pady=(0, 4))
        scale.set_resolution = lambda r: resolution_holder.__setitem__(0, r)
        return label, scale

    def _log_config_status(self, config_error):
        if config_error == "parse_error":
            self.log_message("Warning: Error reading config.json.")
            self.log_message("SETUP REQUIRED: Go to File > API Config to add your API Key, then File > Shocker Config to add Shockers.")
        elif self.config.is_complete:
            self.log_message("Configuration loaded successfully.")
        else:
            self.log_message("SETUP REQUIRED: Go to File > API Config to add your API Key, then File > Shocker Config to add Shockers.")

    def _recover_previous_session(self):
        recovered = recover_previous_session()
        if recovered:
            self.log_message(f"Previous session didn't exit cleanly - recovered {recovered} shock(s) into shock_log.txt.")

    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="API Config", command=self.open_api_config)
        file_menu.add_command(label="Shocker Config", command=self.open_shocker_config)
        file_menu.add_command(label="OSC Config", command=self.open_osc_config)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit_app)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="GitHub", command=self.open_github)
        help_menu.add_command(label="About", command=self.open_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_gui(self):
        # Left as a plain tk.Label rather than ttk.Button: this widget's whole job is
        # flipping between a solid red/green fill, and ttk widgets (especially under
        # macOS's native "aqua" theme) largely ignore background color overrides.
        button_font = tkfont.Font(size=20, weight="bold")
        self.stop_btn = tk.Label(
            self.root, text="Disable", bg="red", fg="white", font=button_font,
            relief="raised", borderwidth=5, cursor="hand2"
        )
        self.stop_btn.pack(fill=tk.X, padx=10, pady=10, ipady=20)
        self.stop_btn.bind("<Button-1>", lambda event: self.toggle_active())

        slider_frame = ttk.LabelFrame(self.root, text="Shocker Settings", padding=10)
        slider_frame.pack(fill=tk.X, padx=10, pady=5)

        self.max_intensity_var = tk.IntVar(value=30)
        self._make_scale(slider_frame, "Maximum Allowed Intensity: {}%", self.max_intensity_var, 1, 100, 1)

        self.max_duration_var = tk.DoubleVar(value=1.0)
        self.max_duration_label, self.max_duration_slider = self._make_scale(
            slider_frame, "Maximum Allowed Duration: {}s", self.max_duration_var,
            self.client.MIN_DURATION_MS / 1000, 10.0, self.client.DURATION_RESOLUTION_S
        )

        self.cooldown_var = tk.DoubleVar(value=5.0)
        self.cooldown_label, self.cooldown_slider = self._make_scale(
            slider_frame, "Cooldown Between Shocks: {}s", self.cooldown_var, 1.0, 10.0, 0.5
        )

        self.test_mode_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            slider_frame, text="Vibrate Mode", variable=self.test_mode_var, style="Vibrate.TCheckbutton"
        ).pack(anchor="w", pady=(10, 0))

        ttk.Separator(slider_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        self.dynamic_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            slider_frame, text="Physbone Stretch Mode", variable=self.dynamic_mode_var, style="Dynamic.TCheckbutton"
        ).pack(anchor="w", pady=(0, 5))

        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(status_frame, text="System Status:", font=("Helvetica", 12)).pack(side=tk.LEFT)
        self.status_label = ttk.Label(status_frame, text="READY", foreground="green", style="Status.TLabel")
        self.status_label.pack(side=tk.LEFT, padx=10)

        self.shock_count_label = ttk.Label(status_frame, text="Shocks This Session: 0")
        self.shock_count_label.pack(side=tk.RIGHT)

        self.log_area = scrolledtext.ScrolledText(self.root, height=10, state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        self.max_intensity_var.trace_add("write", lambda *_: self._send_osc_if_user(MTS_INTENSITY, self.max_intensity_var.get() / 100.0))
        self.max_duration_var.trace_add("write", lambda *_: self._send_osc_if_user(MTS_DURATION, self.max_duration_var.get() / 10.0))
        self.cooldown_var.trace_add("write", lambda *_: self._send_osc_if_user(MTS_COOLDOWN, self.cooldown_var.get() / 10.0))
        self.test_mode_var.trace_add("write", lambda *_: self._send_osc_if_user(MTS_VIBRATE, self.test_mode_var.get()))
        self.dynamic_mode_var.trace_add("write", self._on_dynamic_mode_changed)

    # ------------------------------------------------------------------
    # OSC: outgoing (avatar menu sync)
    # ------------------------------------------------------------------
    def _send_osc_if_user(self, address, value):
        if not self._updating_from_osc:
            self.osc.send(address, value)

    def _sync_all_osc(self):
        self._send_osc_if_user(MTS_ENABLE, self.is_active)
        self._send_osc_if_user(MTS_VIBRATE, self.test_mode_var.get())
        self._send_osc_if_user(MTS_DYNAMIC, self.dynamic_mode_var.get())
        self._send_osc_if_user(MTS_INTENSITY, self.max_intensity_var.get() / 100.0)
        self._send_osc_if_user(MTS_DURATION, self.max_duration_var.get() / 10.0)
        self._send_osc_if_user(MTS_COOLDOWN, self.cooldown_var.get() / 10.0)

    def _set_var_from_osc(self, var, value):
        self._updating_from_osc = True
        var.set(value)
        self._updating_from_osc = False

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
        self.log_message("Avatar load detected. Resyncing menu...")

        def delayed_sync():
            time.sleep(1.5)
            self._sync_all_osc()

        threading.Thread(target=delayed_sync, daemon=True).start()

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
            target_state = bool(args[0])
            if target_state != self.is_active:
                self.root.after(0, lambda: self.toggle_active(from_osc=True))

    def on_mts_vibrate(self, address, *args):
        if args:
            self.root.after(0, self._set_var_from_osc, self.test_mode_var, bool(args[0]))

    def on_mts_dynamic(self, address, *args):
        if args:
            self.root.after(0, self._set_var_from_osc, self.dynamic_mode_var, bool(args[0]))

    def on_mts_intensity(self, address, *args):
        if args:
            val = float(args[0])
            self.root.after(0, self._set_var_from_osc, self.max_intensity_var, int(val * 100))

    def on_mts_duration(self, address, *args):
        if args:
            min_val = self.client.MIN_DURATION_MS / 1000 / 10.0
            val = min(max(float(args[0]), min_val), 1.0)
            seconds = val * 10.0
            self.root.after(0, self._set_var_from_osc, self.max_duration_var, round(seconds, 1))

    def on_mts_cooldown(self, address, *args):
        if args:
            seconds = min(max(float(args[0]) * 10.0, 1.0), 10.0)
            self.root.after(0, self._set_var_from_osc, self.cooldown_var, round(seconds, 1))

    # ------------------------------------------------------------------
    # Shock triggering
    # ------------------------------------------------------------------
    def evaluate_state(self):
        if self.is_grabbed and self.current_stretch > 0.1:
            if self.dynamic_mode_var.get():
                if not self.is_dynamic_loop_running:
                    threading.Thread(target=self.dynamic_shock_loop, daemon=True).start()
            else:
                self.trigger_shock()

    def trigger_shock(self):
        if not self.client.is_configured:
            return

        with self.lock:
            if not self.is_active:
                return
            current_time = time.time()
            if current_time - self.last_shock_time < self.cooldown_var.get():
                return
            self.last_shock_time = current_time

        self.root.after(0, self._update_cooldown_ui)

        max_i = self.max_intensity_var.get()
        max_d = self.max_duration_var.get()
        action_type = "Vibrate" if self.test_mode_var.get() else "Shock"

        min_d = self.client.MIN_DURATION_MS / 1000
        duration_s = round(random.uniform(min_d, max_d), 2) if max_d > min_d else min_d
        duration_ms = int(duration_s * 1000)
        intensity = random.randint(1, max_i) if max_i > 1 else 1

        if action_type == "Shock":
            self._increment_shock_count()

        self.log_message(f"Triggering Burst: {intensity}% intensity for {duration_s}s ({action_type})")
        threading.Thread(target=self.send_shocker_command, args=(intensity, duration_ms, action_type), daemon=True).start()

    def dynamic_shock_loop(self):
        with self.lock:
            if self.is_dynamic_loop_running:
                return
            self.is_dynamic_loop_running = True

        self.log_message("Physbone Stretch: Started.")

        is_real_shock = not self.test_mode_var.get()
        if is_real_shock:
            self._increment_shock_count()

        accumulated_time = 0.0
        pulse_interval = self.client.DYNAMIC_PULSE_INTERVAL_S
        pulse_duration_ms = self.client.DYNAMIC_PULSE_DURATION_MS
        last_pulse_time = 0.0

        while self.is_active and self.dynamic_mode_var.get() and self.is_grabbed and self.current_stretch > 0.1:
            max_i = self.max_intensity_var.get()

            stretch_clamped = min(max(self.current_stretch, 0.0), 1.0)
            intensity = max(int(stretch_clamped * max_i), 1)

            action_type = "Vibrate" if self.test_mode_var.get() else "Shock"

            now = time.time()
            if now - last_pulse_time >= pulse_interval:
                self.send_shocker_command(intensity, pulse_duration_ms, action_type, log_success=False)
                last_pulse_time = now
            time.sleep(0.2)

            if is_real_shock:
                accumulated_time += 0.2
                if accumulated_time >= 1.0:
                    self._increment_shock_count()
                    accumulated_time -= 1.0

        if self.is_active:
            self.send_shocker_command(0, self.client.MIN_DURATION_MS, "Stop", log_success=False)

        self.log_message("Physbone Stretch: Ended.")

        with self.lock:
            self.is_dynamic_loop_running = False
            self.last_shock_time = time.time()
            self.root.after(0, self._update_cooldown_ui)

    def send_shocker_command(self, intensity, duration_ms, action_type, log_success=True):
        result = self.client.send(intensity, duration_ms, action_type)
        if result is None:
            if log_success and action_type == "Stop" and self.client.is_configured:
                self.log_message(f"{self.client.PROVIDER_LABEL} has no immediate stop command - the in-progress shock/vibrate will finish on its own.")
            return
        success, message = result
        if log_success:
            self.log_message(message)

    def send_halt_command(self):
        self.send_shocker_command(0, self.client.MIN_DURATION_MS, "Stop")

    def _increment_shock_count(self):
        with self.lock:
            self.session_shock_count += 1
            # Persisted immediately (not just at exit) so the count survives a hard
            # kill - SteamVR force-closing us or an OS shutdown never runs our
            # shutdown code at all, so exit-time logging alone can't be relied on.
            update_session_state(self.session_shock_count)
        self.root.after(0, self._update_shock_count_ui)

    # ------------------------------------------------------------------
    # UI state / logging
    # ------------------------------------------------------------------
    def toggle_active(self, from_osc=False):
        self.is_active = not self.is_active
        if self.is_active:
            self.stop_btn.config(text="Disable", bg="red", relief="raised")
            self.status_label.config(text="READY", foreground="green")
            self.log_message("System Enabled.")
        else:
            self.stop_btn.config(text="Enable", bg="green", relief="sunken")
            self.status_label.config(text="DISABLED", foreground="red")
            self.log_message("System Disabled.")
            threading.Thread(target=self.send_halt_command, daemon=True).start()

        if not from_osc:
            self._send_osc_if_user(MTS_ENABLE, self.is_active)

    def _on_dynamic_mode_changed(self, *args):
        if self.dynamic_mode_var.get():
            self.max_duration_slider.config(state=tk.DISABLED)
            self.cooldown_slider.config(state=tk.DISABLED)
            self.max_duration_label.config(foreground="gray")
            self.cooldown_label.config(foreground="gray")
            self.log_message("Physbone Stretch Mode enabled.")
        else:
            self.max_duration_slider.config(state=tk.NORMAL)
            self.cooldown_slider.config(state=tk.NORMAL)
            self.max_duration_label.config(foreground="black")
            self.cooldown_label.config(foreground="black")
            self.log_message("Random Mode enabled.")
        self._send_osc_if_user(MTS_DYNAMIC, self.dynamic_mode_var.get())

    def _update_cooldown_ui(self):
        if not self.is_active or self.dynamic_mode_var.get():
            self.status_label.config(text="READY", foreground="green")
            return

        time_passed = time.time() - self.last_shock_time
        remaining_cooldown = self.cooldown_var.get() - time_passed

        if remaining_cooldown > 0:
            self.status_label.config(text=f"COOLDOWN ({remaining_cooldown:.1f}s)", foreground="orange")
            self.root.after(100, self._update_cooldown_ui)
        else:
            self.status_label.config(text="READY", foreground="green")

    def _update_shock_count_ui(self):
        self.shock_count_label.config(text=f"Shocks This Session: {self.session_shock_count}")

    def log_message(self, message):
        self.root.after(0, self._safe_log, message)

    def _safe_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    # ------------------------------------------------------------------
    # Config menu actions
    # ------------------------------------------------------------------
    def _save_config(self):
        try:
            self.config.save()
        except Exception as e:
            messagebox.showerror("Error", f"Could not write configuration file:\n{e}")

    def _apply_duration_bounds(self):
        min_s = self.client.MIN_DURATION_MS / 1000
        self.max_duration_slider.config(from_=min_s)
        self.max_duration_slider.set_resolution(self.client.DURATION_RESOLUTION_S)
        if self.max_duration_var.get() < min_s:
            self.max_duration_var.set(min_s)
        self.max_duration_label.config(text=f"Maximum Allowed Duration: {self.max_duration_var.get()}s")

    def open_api_config(self):
        modal = APIConfigModal(
            self.root, "API Configuration",
            self.config.provider, self.config.openshock_api_key,
            self.config.pishock_username, self.config.pishock_api_key,
        )
        if modal.result:
            self.config.provider = modal.result["provider"]
            self.config.openshock_api_key = modal.result["openshock_api_key"]
            self.config.pishock_username = modal.result["pishock_username"]
            self.config.pishock_api_key = modal.result["pishock_api_key"]

            self.client = build_client(self.config)
            self._apply_duration_bounds()
            self._save_config()
            self.log_message(f"API configuration saved. Active provider: {self.client.PROVIDER_LABEL}.")

    def open_osc_config(self):
        modal = OSCConfigModal(self.root, "OSC Configuration", self.config.param_grabbed, self.config.param_stretch)
        if modal.result:
            old_grabbed = self.config.param_grabbed
            old_stretch = self.config.param_stretch

            self.config.param_grabbed = modal.result["param_grabbed"] or DEFAULT_PARAM_GRABBED
            self.config.param_stretch = modal.result["param_stretch"] or DEFAULT_PARAM_STRETCH

            self._save_config()
            self.log_message("OSC configuration saved.")

            if old_grabbed != self.config.param_grabbed or old_stretch != self.config.param_stretch:
                self.log_message("OSC Parameters changed. Restarting OSC listener...")
                threading.Thread(target=self._restart_osc_server, daemon=True).start()

    def open_shocker_config(self):
        if self.config.provider == "pishock":
            current_ids, current_mode = self.config.pishock_share_codes, self.config.pishock_shocker_mode
        else:
            current_ids, current_mode = self.config.openshock_shocker_ids, self.config.openshock_shocker_mode

        modal = ShockerConfigModal(
            self.root, "Shocker Configuration", current_ids, current_mode, id_label=self.client.ID_LABEL
        )
        if modal.result:
            if self.config.provider == "pishock":
                self.config.pishock_share_codes = modal.result["shocker_ids"]
                self.config.pishock_shocker_mode = modal.result["shocker_mode"]
                self.client.share_codes = self.config.pishock_share_codes
                self.client.shocker_mode = self.config.pishock_shocker_mode
            else:
                self.config.openshock_shocker_ids = modal.result["shocker_ids"]
                self.config.openshock_shocker_mode = modal.result["shocker_mode"]
                self.client.shocker_ids = self.config.openshock_shocker_ids
                self.client.shocker_mode = self.config.openshock_shocker_mode

            self._save_config()
            self.log_message("Shocker configuration saved.")

    def open_github(self):
        webbrowser.open(GITHUB_URL)

    def open_about(self):
        about_window = tk.Toplevel(self.root)
        about_window.title("About")
        about_window.geometry("300x250")
        about_window.resizable(False, False)
        icon_image = self._load_icon_image()
        if icon_image is not None:
            icon_label = ttk.Label(about_window, image=icon_image)
            icon_label.image = icon_image  # keep a reference alive
            icon_label.pack(pady=(15, 5))
        ttk.Label(about_window, text="Mayu Tail Shocker", font=("Helvetica", 12, "bold")).pack()
        ttk.Label(about_window, text=f"Version {__version__}", font=("Helvetica", 9)).pack()
        ttk.Label(about_window, text="Created by SkyeCA", font=("Helvetica", 10)).pack(pady=(0, 10))
        link_lbl = ttk.Label(about_window, text=ABOUT_URL, font=("Helvetica", 10, "underline"), foreground="blue", cursor="hand2")
        link_lbl.pack()
        link_lbl.bind("<Button-1>", lambda e: webbrowser.open(ABOUT_URL))
        ttk.Button(about_window, text="Close", command=about_window.destroy).pack(pady=15)

    # ------------------------------------------------------------------
    # OSC server lifecycle / app lifecycle
    # ------------------------------------------------------------------
    def _restart_osc_server(self):
        self.osc.restart(self._osc_handlers())
        self.log_message("OSC listener restarted and mapped to new parameters.")

    def save_shock_stats(self):
        # Idempotent: may be invoked twice (e.g. quit_app then atexit on top of it).
        if self._session_finalized:
            return
        self._session_finalized = True
        finalize_session(self.session_shock_count)

    def quit_app(self):
        self.save_shock_stats()
        self.osc.stop()
        self.root.quit()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = TailShockerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.quit_app)
    # Best-effort: Tk maps Windows logoff/shutdown (WM_QUERYENDSESSION) to this protocol.
    root.protocol("WM_SAVE_YOURSELF", app.quit_app)

    # Belt-and-suspenders for exit paths that do run Python code (Ctrl+C, a polite
    # SIGTERM, an uncaught exception, sys.exit). Doesn't help against a hard kill
    # (TerminateProcess) - that's what the incremental session-state persistence
    # in mts/session_log.py is actually for.
    atexit.register(app.save_shock_stats)

    def _on_termination_signal(signum, frame):
        app.quit_app()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _on_termination_signal)
        except (ValueError, OSError):
            pass

    root.mainloop()
