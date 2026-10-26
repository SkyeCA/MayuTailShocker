import atexit
import logging
import signal
import tkinter as tk
from collections import deque
from datetime import datetime

import customtkinter as ctk
from PIL import Image

from . import app_log
from .config import load_config
from .constants import (
    ABOUT_URL,
    GITHUB_URL,
    OSC_IP,
    OSC_PORT,
    OSC_SEND_PORT,
    resource_path,
)
from .controls import Dial
from .engine import STRETCH_THRESHOLD, EngineListener, ShockEngine
from .openshock_api import OpenShockClient
from .osc_bridge import OSCBridge
from .settings_window import SettingsWindow
from .theme import (
    ACCENT_TEXT,
    BANNER,
    DANGER,
    DANGER_HOVER,
    MUTED_TEXT,
    SEGMENTED,
    SUCCESS,
    SWITCH_KNOB,
    SWITCH_KNOB_HOVER,
    WARNING,
    body_font,
    heading_font,
    link_label,
    mono_font,
    title_font,
)
from .version import __version__
from .windowing import center_window

OUTPUT_VIBRATE, OUTPUT_SHOCK = "Vibrate", "Shock"
MODE_RANDOM, MODE_STRETCH = "Random", "Stretch"

MODE_HINTS = {
    MODE_RANDOM: "Randomizes value when your tail is pulled and waits for cooldown.",
    MODE_STRETCH: "Sends continuous values based on how far your tail is being stretched.",
}

# setting name, caption, from, to, step, value format
DIALS = (
    ("max_intensity", "Intensity", 1, 100, 1, "{}%"),
    ("max_duration", "Duration", 0.3, 10.0, 0.1, "{:.1f} s"),
    ("cooldown", "Cooldown", 1.0, 10.0, 0.1, "{:.1f} s"),
)

LOG_HISTORY = 1000  # lines kept for the Logs window

SETUP_MESSAGE = "SETUP REQUIRED: Open Settings to add your OpenShock API token and shocker IDs."

logger = logging.getLogger(__name__)


class TailShockerApp(EngineListener):
    """CustomTkinter front end. All shock/OSC behaviour lives in ShockEngine; this
    class only renders engine state and forwards user input to it."""

    def __init__(self, root):
        self.root = root
        self.root.title("Mayu Tail Shocker")
        # Sized to its content (which changes with the setup banner), at least 500 wide.
        self.root.minsize(500, 0)
        self.root.resizable(False, False)

        self._icon_photo = self._load_icon_photo()
        self._apply_window_icon(self.root)

        config, config_error = load_config()
        ctk.set_appearance_mode(config.appearance_mode)
        client = OpenShockClient(config.api_key, config.shocker_ids, config.shocker_mode)
        osc = OSCBridge(OSC_IP, OSC_PORT, OSC_SEND_PORT)
        self.engine = ShockEngine(config, client, osc, listener=self)

        self._status_job = None
        self._last_tail = None
        self._dials = {}
        self._log_lines = deque(maxlen=LOG_HISTORY)
        self._log_window = None
        self._settings_window = None
        self._about_window = None

        self._build_gui()
        self._apply_settings(self.engine.settings)
        self._render_active(self.engine.is_active)
        self._render_setup_banner()
        center_window(self.root)
        self._log_config_status(config_error)
        try:
            self.engine.start()
        except OSError as e:
            self._show_osc_port_error(e)
            return
        self._poll_tail()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def _load_icon_photo(self):
        try:
            return tk.PhotoImage(file=resource_path("resources/icon.png"))
        except Exception:
            return None

    def _apply_window_icon(self, window):
        if self._icon_photo is None:
            return
        window.iconphoto(False, self._icon_photo)
        # On Windows, CustomTkinter swaps in its own icon ~200ms after a window is
        # created, so put ours back once it has.
        window.after(250, lambda: window.iconphoto(False, self._icon_photo))

    def _icon_image(self, size):
        try:
            image = Image.open(resource_path("resources/icon.png"))
        except Exception:
            return None
        return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))

    def _log_config_status(self, config_error):
        if config_error == "parse_error":
            self.log_message("Warning: Error reading config.json.")
            self.log_message(SETUP_MESSAGE)
        elif self.engine.config.is_complete:
            self.log_message("Configuration loaded successfully.")
        else:
            self.log_message(SETUP_MESSAGE)

    def _card(self, parent, **pack):
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.pack(fill="x", padx=16, **pack)
        return card

    def _secondary_button(self, parent, text, command, width=90):
        return ctk.CTkButton(
            parent, text=text, width=width, height=28, fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"), command=command,
        )

    def _build_gui(self):
        self._build_header()
        self._build_setup_banner()
        self._build_power_card()
        self._build_settings_card()

    def _build_header(self):
        self.header = ctk.CTkFrame(self.root, fg_color="transparent")
        self.header.pack(fill="x", padx=16, pady=(14, 10))

        ctk.CTkLabel(
            self.header, text="  Mayu Tail Shocker", image=self._icon_image(28), compound="left",
            font=title_font(),
        ).pack(side="left")
        self._secondary_button(self.header, "About", self.open_about, width=70).pack(side="right")
        self._secondary_button(self.header, "Logs", self.open_logs, width=60).pack(side="right", padx=(0, 8))
        self._secondary_button(self.header, "Settings", self.open_settings).pack(side="right", padx=(0, 8))

    def _build_setup_banner(self):
        self.setup_banner = ctk.CTkFrame(self.root, corner_radius=12, fg_color=BANNER, border_width=1, border_color=WARNING)
        ctk.CTkLabel(
            self.setup_banner, text="Add your OpenShock API token and shocker IDs to get started.",
            font=body_font(), anchor="w", justify="left", wraplength=250,
        ).pack(side="left", fill="x", expand=True, padx=14, pady=12)
        ctk.CTkButton(self.setup_banner, text="Open Settings", width=110, command=self.open_settings).pack(side="right", padx=14)

    def _build_power_card(self):
        card = self._card(self.root, pady=(0, 10))

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 0))
        self.power_title = ctk.CTkLabel(top, text="", font=title_font(22), anchor="w")
        self.power_title.pack(side="left")

        self.power_switch = ctk.CTkSwitch(
            top, text="", width=60, switch_width=56, switch_height=28,
            progress_color=SUCCESS, button_color=SWITCH_KNOB, button_hover_color=SWITCH_KNOB_HOVER,
            command=self._on_power_switch,
        )
        self.power_switch.pack(side="right")

        stats = ctk.CTkFrame(card, fg_color="transparent")
        stats.pack(fill="x", padx=16, pady=(14, 0))
        stats.grid_columnconfigure((0, 1, 2), weight=1, uniform="stats")
        self.status_value = self._stat(stats, 0, "Status")
        self.count_value = self._stat(stats, 1, "Shocks this session")
        self.tail_value = self._stat(stats, 2, "Tail")
        self.count_value.configure(text="0")

        self.tail_bar = ctk.CTkProgressBar(card, height=8)
        self.tail_bar.set(0)
        self.tail_bar.pack(fill="x", padx=16, pady=(10, 16))
        self._tail_bar_colors = (self.tail_bar.cget("fg_color"), self.tail_bar.cget("progress_color"))

    def _stat(self, parent, column, caption):
        ctk.CTkLabel(parent, text=caption, font=body_font(12), text_color=MUTED_TEXT, anchor="w").grid(row=0, column=column, sticky="w")
        value = ctk.CTkLabel(parent, text="", font=heading_font(15), anchor="w")
        value.grid(row=1, column=column, sticky="w")
        return value

    def _build_settings_card(self):
        card = self._card(self.root, pady=(0, 16))
        ctk.CTkLabel(card, text="Shocker Settings", font=heading_font(15), anchor="w").pack(fill="x", padx=16, pady=(12, 4))

        toggles = ctk.CTkFrame(card, fg_color="transparent")
        toggles.pack(fill="x", padx=16)
        toggles.grid_columnconfigure((0, 1), weight=1, uniform="toggles")

        ctk.CTkLabel(toggles, text="Output", font=body_font(12), text_color=MUTED_TEXT).grid(row=0, column=0, sticky="w")
        self.output_button = ctk.CTkSegmentedButton(toggles, values=[OUTPUT_VIBRATE, OUTPUT_SHOCK], command=self._on_output_changed, **SEGMENTED)
        self.output_button.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        self._output_colors = (self.output_button.cget("selected_color"), self.output_button.cget("selected_hover_color"))

        ctk.CTkLabel(toggles, text="Mode", font=body_font(12), text_color=MUTED_TEXT).grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.mode_button = ctk.CTkSegmentedButton(toggles, values=[MODE_RANDOM, MODE_STRETCH], command=self._on_mode_changed, **SEGMENTED)
        self.mode_button.grid(row=1, column=1, sticky="ew", padx=(6, 0))

        self.mode_hint = ctk.CTkLabel(
            card, text="", font=body_font(12), text_color=MUTED_TEXT,
            anchor="w", justify="left", wraplength=436,  # the card's full inner width
        )
        self.mode_hint.pack(fill="x", padx=16, pady=(6, 4))

        dial_row = ctk.CTkFrame(card, fg_color="transparent")
        dial_row.pack(fill="x")
        for column, (name, caption, from_, to, step, value_fmt) in enumerate(DIALS):
            command = lambda value, name=name: self.engine.update_settings(**{name: value})
            dial = Dial(dial_row, caption, from_, to, step, value_fmt, command)
            dial.grid(row=0, column=column, pady=(8, 0))
            dial_row.grid_columnconfigure(column, weight=1, uniform="dials")
            self._dials[name] = dial
        ctk.CTkFrame(card, fg_color="transparent", height=6).pack()

    # ------------------------------------------------------------------
    # User input -> engine
    # ------------------------------------------------------------------
    def _on_power_switch(self):
        self.engine.set_active(bool(self.power_switch.get()))

    def _on_output_changed(self, value):
        self.engine.update_settings(vibrate=value == OUTPUT_VIBRATE)
        self._render_output(value)

    def _on_mode_changed(self, value):
        self.engine.update_settings(dynamic=value == MODE_STRETCH)
        self._render_mode(value)

    # ------------------------------------------------------------------
    # EngineListener (called from any thread - marshal onto the Tk thread)
    # ------------------------------------------------------------------
    def on_log(self, message):
        self.log_message(message)

    def on_active_changed(self, is_active):
        self.root.after(0, self._render_active, is_active)

    def on_settings_changed(self, settings):
        self.root.after(0, self._apply_settings, settings)

    def on_shock_count_changed(self, count):
        self.root.after(0, lambda: self.count_value.configure(text=str(count)))

    def on_status_changed(self):
        self.root.after(0, self._render_status)

    # ------------------------------------------------------------------
    # Rendering engine state
    # ------------------------------------------------------------------
    # Setting CTk widgets from code doesn't fire their commands, so none of this
    # feeds back into the engine.
    def _apply_settings(self, settings):
        for name, dial in self._dials.items():
            dial.set(getattr(settings, name))

        output = OUTPUT_VIBRATE if settings.vibrate else OUTPUT_SHOCK
        self.output_button.set(output)
        self._render_output(output)

        mode = MODE_STRETCH if settings.dynamic else MODE_RANDOM
        self.mode_button.set(mode)
        self._render_mode(mode)

    def _render_output(self, output):
        if output == OUTPUT_SHOCK:
            self.output_button.configure(selected_color=DANGER, selected_hover_color=DANGER_HOVER)
        else:
            color, hover = self._output_colors
            self.output_button.configure(selected_color=color, selected_hover_color=hover)

    def _render_mode(self, mode):
        self.mode_hint.configure(text=MODE_HINTS[mode])
        # Duration and cooldown only apply to Random mode.
        for name in ("max_duration", "cooldown"):
            self._dials[name].set_enabled(mode != MODE_STRETCH)
        self._render_status()

    def _render_active(self, is_active):
        if is_active:
            self.power_switch.select()
            self.power_title.configure(text="Active", text_color=SUCCESS)
        else:
            self.power_switch.deselect()
            self.power_title.configure(text="Disabled", text_color=MUTED_TEXT)
        self._render_status()

    def _render_status(self):
        if self._status_job is not None:
            self.root.after_cancel(self._status_job)
            self._status_job = None

        if not self.engine.is_active:
            self.status_value.configure(text="Disabled", text_color=MUTED_TEXT)
            return
        if not self.engine.config.is_complete:
            self.status_value.configure(text="Setup needed", text_color=WARNING)
            return

        output = self.engine.current_output()
        remaining_cooldown = self.engine.cooldown_remaining()
        if output == OUTPUT_SHOCK:
            self.status_value.configure(text="Shocking", text_color=DANGER)
            self._status_job = self.root.after(100, self._render_status)
        elif output == OUTPUT_VIBRATE:
            self.status_value.configure(text="Vibrating", text_color=ACCENT_TEXT)
            self._status_job = self.root.after(100, self._render_status)
        elif remaining_cooldown > 0:
            self.status_value.configure(text=f"Cooldown {remaining_cooldown:.1f}s", text_color=WARNING)
            self._status_job = self.root.after(100, self._render_status)
        else:
            self.status_value.configure(text="Ready", text_color=SUCCESS)

    def _poll_tail(self):
        # Stretch updates arrive at OSC rate; sampling them here keeps redraws cheap.
        tail = (self.engine.is_grabbed, round(self.engine.current_stretch, 2))
        if tail != self._last_tail:
            self._last_tail = tail
            is_grabbed, stretch = tail
            pulled = is_grabbed and stretch > STRETCH_THRESHOLD
            if pulled:
                self.tail_value.configure(text=f"Pulled {stretch:.0%}", text_color=WARNING)
            elif is_grabbed:
                self.tail_value.configure(text="Grabbed", text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
            else:
                self.tail_value.configure(text="Idle", text_color=MUTED_TEXT)
            # An empty CTkProgressBar still draws a dot, so hide it while idle.
            empty_color, grabbed_color = self._tail_bar_colors
            self.tail_bar.set(min(max(stretch, 0.0), 1.0) if is_grabbed else 0)
            self.tail_bar.configure(progress_color=WARNING if pulled else grabbed_color if is_grabbed else empty_color)
        self.root.after(100, self._poll_tail)

    def _on_settings_saved(self):
        self._render_setup_banner()
        self._render_status()

    def _render_setup_banner(self):
        if self.engine.config.is_complete:
            self.setup_banner.pack_forget()
        else:
            self.setup_banner.pack(fill="x", padx=16, pady=(0, 10), after=self.header)

    def log_message(self, message):
        logger.info(message)
        self.root.after(0, self._safe_log, message)

    def _safe_log(self, message):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n"
        self._log_lines.append(line)
        if self._log_window is not None:
            self._append_to_log_view(line)

    def _append_to_log_view(self, text):
        view = self._log_view
        at_bottom = view.yview()[1] >= 0.999
        view.configure(state="normal")
        view.insert("end", text)
        view.configure(state="disabled")
        if at_bottom:  # follow new lines, unless the user has scrolled up to read
            view.see("end")

    # ------------------------------------------------------------------
    # Windows
    # ------------------------------------------------------------------
    def _raise_existing(self, window):
        """Brings window to the front and returns True if it's still open."""
        if window is None or not window.winfo_exists():
            return False
        window.lift()
        window.focus_force()
        return True

    def open_settings(self):
        if self._raise_existing(self._settings_window):
            return
        self._settings_window = SettingsWindow(self.root, self.engine, on_saved=self._on_settings_saved)
        self._apply_window_icon(self._settings_window)

    def open_logs(self):
        if self._raise_existing(self._log_window):
            return

        window = ctk.CTkToplevel(self.root)
        window.title("Logs")
        window.geometry("600x380")
        window.minsize(400, 200)
        window.transient(self.root)
        self._apply_window_icon(window)

        def close():
            self._log_window = None
            window.destroy()

        # Packed first so the log view, which expands, can't squeeze it out.
        ctk.CTkButton(window, text="Close", width=100, command=close).pack(side="bottom", anchor="e", padx=12, pady=(0, 12))
        self._log_view = ctk.CTkTextbox(window, font=mono_font(), wrap="word", state="disabled")
        self._log_view.pack(fill="both", expand=True, padx=12, pady=12)
        self._log_window = window
        self._append_to_log_view("".join(self._log_lines))
        self._log_view.see("end")
        center_window(window, self.root)

        window.protocol("WM_DELETE_WINDOW", close)
        window.bind("<Escape>", lambda e: close())
        window.after(100, window.lift)

    def open_about(self):
        if self._raise_existing(self._about_window):
            return
        window = self._about_window = ctk.CTkToplevel(self.root)
        window.title("About")
        # Height follows the content, so there's no empty space under the links.
        window.minsize(300, 0)
        window.resizable(False, False)
        window.transient(self.root)
        self._apply_window_icon(window)

        icon = self._icon_image(64)
        if icon is not None:
            ctk.CTkLabel(window, text="", image=icon).pack(pady=(20, 8))
        ctk.CTkLabel(window, text="Mayu Tail Shocker", font=heading_font(16)).pack()
        ctk.CTkLabel(window, text=f"Version {__version__}", font=body_font(12), text_color=MUTED_TEXT).pack()
        ctk.CTkLabel(window, text="Created by SkyeCA", font=body_font()).pack(pady=(6, 8))

        links = ctk.CTkFrame(window, fg_color="transparent")
        links.pack(pady=(0, 20))
        link_label(links, ABOUT_URL.split("//")[-1], ABOUT_URL).pack(side="left")
        ctk.CTkLabel(links, text="  ·  ", text_color=MUTED_TEXT).pack(side="left")
        link_label(links, "GitHub", GITHUB_URL).pack(side="left")
        center_window(window, self.root)

        window.bind("<Escape>", lambda e: window.destroy())
        window.after(100, window.lift)

    def _show_osc_port_error(self, error):
        """Without the OSC port the app can't hear VRChat at all, so this replaces the
        main window with an explanation and a way out."""
        logger.error("Could not listen for OSC on port %s: %s", OSC_PORT, error)
        self.root.withdraw()

        window = ctk.CTkToplevel(self.root)
        window.title("Mayu Tail Shocker")
        window.minsize(360, 0)
        window.resizable(False, False)
        self._apply_window_icon(window)

        ctk.CTkLabel(window, text="Can't connect to VRChat", font=heading_font(16), anchor="w").pack(fill="x", padx=20, pady=(18, 6))
        ctk.CTkLabel(
            window, font=body_font(), anchor="w", justify="left", wraplength=360,
            text=f"OSC port {OSC_PORT} couldn't be opened. Usually another copy of Mayu Tail Shocker, "
                 "or another OSC app, is already using it. Close it, then start Mayu Tail Shocker again.",
        ).pack(fill="x", padx=20)
        ctk.CTkLabel(
            window, text=str(error), font=body_font(12), text_color=MUTED_TEXT, anchor="w", justify="left", wraplength=360,
        ).pack(fill="x", padx=20, pady=(8, 0))
        ctk.CTkButton(window, text="Exit", width=100, command=self.root.destroy).pack(anchor="e", padx=20, pady=16)
        center_window(window)

        window.protocol("WM_DELETE_WINDOW", self.root.destroy)
        window.bind("<Escape>", lambda e: self.root.destroy())
        window.after(100, window.lift)

    # ------------------------------------------------------------------
    # App lifecycle
    # ------------------------------------------------------------------
    def quit_app(self):
        self.engine.shutdown()
        self.root.quit()
        self.root.destroy()


def main():
    app_log.setup()
    logger.info("Mayu Tail Shocker %s starting", __version__)
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    app_log.log_tk_errors(root)
    app = TailShockerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.quit_app)
    # Best-effort: Tk maps Windows logoff/shutdown (WM_QUERYENDSESSION) to this protocol.
    root.protocol("WM_SAVE_YOURSELF", app.quit_app)

    # Belt-and-suspenders for exit paths that do run Python code (Ctrl+C, a polite
    # SIGTERM, an uncaught exception, sys.exit). Doesn't help against a hard kill
    # (TerminateProcess) - that's what the incremental session-state persistence
    # in mts/session_log.py is actually for.
    atexit.register(app.engine.save_shock_stats)

    def _on_termination_signal(signum, frame):
        app.quit_app()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _on_termination_signal)
        except (ValueError, OSError):
            pass

    root.mainloop()
