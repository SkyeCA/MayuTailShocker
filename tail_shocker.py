import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
from tkinter import font as tkfont
import threading
import time
import random
import json
import webbrowser
from datetime import datetime
import requests 
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient
import sys
import os

# ==========================================
# CONSTANTS
# ==========================================
OSC_IP = "127.0.0.1"
OSC_PORT = 9001 
OSC_SEND_PORT = 9000

# Legacy Avatar Parameters
DEFAULT_PARAM_GRABBED = "/avatar/parameters/Tail/_IsGrabbed"
DEFAULT_PARAM_STRETCH = "/avatar/parameters/Tail/_Stretch"

# In Game Control Parameters
MTS_ENABLE = "/avatar/parameters/MTS_Enable"
MTS_VIBRATE = "/avatar/parameters/MTS_VibrateMode"
MTS_DYNAMIC = "/avatar/parameters/MTS_DynamicMode"
MTS_INTENSITY = "/avatar/parameters/MTS_MaxIntensity"
MTS_DURATION = "/avatar/parameters/MTS_MaxDuration"
MTS_COOLDOWN = "/avatar/parameters/MTS_Cooldown"

CONFIG_FILE = os.path.join(os.path.dirname(sys.argv[0]), "config.json")
USER_AGENT = "MayuTailShocker/1.0 (skye@vore.my)"

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ==========================================
# UI MODALS
# ==========================================
class APIConfigModal(simpledialog.Dialog):
    def __init__(self, parent, title, current_key):
        self.current_key = current_key
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        tk.Label(master, text="OpenShock API Key:", anchor="w").pack(fill=tk.X, pady=(5, 2))
        self.key_entry = tk.Entry(master, width=55)
        self.key_entry.insert(0, self.current_key)
        self.key_entry.pack(fill=tk.X, pady=(0, 10))
        
        return self.key_entry 

    def apply(self):
        self.result = {
            "api_key": self.key_entry.get().strip()
        }

class OSCConfigModal(simpledialog.Dialog):
    def __init__(self, parent, title, param_grabbed, param_stretch):
        self.param_grabbed = param_grabbed
        self.param_stretch = param_stretch
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        tk.Label(master, text="VRChat Grab Parameter (Boolean):", anchor="w").pack(fill=tk.X, pady=(5, 2))
        self.grab_entry = tk.Entry(master, width=55)
        self.grab_entry.insert(0, self.param_grabbed)
        self.grab_entry.pack(fill=tk.X, pady=(0, 10))

        tk.Label(master, text="VRChat Stretch Parameter (Float):", anchor="w").pack(fill=tk.X, pady=(5, 2))
        self.stretch_entry = tk.Entry(master, width=55)
        self.stretch_entry.insert(0, self.param_stretch)
        self.stretch_entry.pack(fill=tk.X, pady=(0, 5))
        
        return self.grab_entry 

    def apply(self):
        self.result = {
            "param_grabbed": self.grab_entry.get().strip(),
            "param_stretch": self.stretch_entry.get().strip()
        }

class ShockerConfigModal(simpledialog.Dialog):
    def __init__(self, parent, title, current_ids, current_mode):
        self.current_ids = list(current_ids)
        self.current_mode = current_mode
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        tk.Label(master, text="Shocker Mode:", anchor="w").pack(fill=tk.X, pady=(5, 2))
        
        self.mode_var = tk.StringVar(value=self.current_mode)
        self.radio_all = tk.Radiobutton(master, text="Trigger All Shockers", variable=self.mode_var, value="All")
        self.radio_all.pack(anchor="w")
        
        self.radio_random = tk.Radiobutton(master, text="Trigger Random Shocker", variable=self.mode_var, value="Random")
        self.radio_random.pack(anchor="w")

        tk.Frame(master, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=10)

        tk.Label(master, text="Shocker IDs:", anchor="w").pack(fill=tk.X, pady=(5, 2))
        
        list_frame = tk.Frame(master)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.listbox = tk.Listbox(list_frame, height=6)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for sid in self.current_ids:
            self.listbox.insert(tk.END, sid)
            
        scrollbar = tk.Scrollbar(list_frame, orient="vertical")
        scrollbar.config(command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        ctrl_frame = tk.Frame(master)
        ctrl_frame.pack(fill=tk.X, pady=(5, 10))
        
        self.new_id_entry = tk.Entry(ctrl_frame)
        self.new_id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        tk.Button(ctrl_frame, text="Add", command=self.add_id).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(ctrl_frame, text="Remove Selected", command=self.remove_id).pack(side=tk.LEFT)
        
        self._update_radio_states()
        
        return self.new_id_entry

    def add_id(self):
        new_id = self.new_id_entry.get().strip()
        if new_id and new_id not in self.listbox.get(0, tk.END):
            self.listbox.insert(tk.END, new_id)
            self.new_id_entry.delete(0, tk.END)
            self._update_radio_states()

    def remove_id(self):
        selected = self.listbox.curselection()
        if selected:
            self.listbox.delete(selected[0])
            self._update_radio_states()
            
    def _update_radio_states(self):
        if self.listbox.size() <= 1:
            self.mode_var.set("All")
            self.radio_all.config(state=tk.DISABLED)
            self.radio_random.config(state=tk.DISABLED)
        else:
            self.radio_all.config(state=tk.NORMAL)
            self.radio_random.config(state=tk.NORMAL)

    def apply(self):
        self.result = {
            "shocker_ids": list(self.listbox.get(0, tk.END)),
            "shocker_mode": self.mode_var.get()
        }

# ==========================================
# Main Logic
# ==========================================
class TailShockerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mayu Tail Shocker")
        
        try:
            icon_image = tk.PhotoImage(file=resource_path("resources/icon.png"))
            self.root.iconphoto(True, icon_image) 
        except Exception:
            pass 

        self.root.geometry("500x740") 
        
        self.api_key = ""
        self.shocker_ids = []
        self.shocker_mode = "All"
        self.param_grabbed = DEFAULT_PARAM_GRABBED
        self.param_stretch = DEFAULT_PARAM_STRETCH
        
        self.is_active = True
        self.last_shock_time = 0.0
        self.is_grabbed = False
        self.current_stretch = 0.0
        self.session_shock_count = 0
        self.is_dynamic_loop_running = False
        self.lock = threading.Lock()
        
        self.osc_client = SimpleUDPClient(OSC_IP, OSC_SEND_PORT)
        self._updating_from_osc = False 

        self._build_menu()
        self._build_gui()
        self._load_config()
        self._start_osc_server()
        
        self._sync_all_osc()
        self.log_message("System Started.")

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
        button_font = tkfont.Font(size=20, weight="bold")
        self.stop_btn = tk.Label(
            self.root, text="Disable", bg="red", fg="white", font=button_font,
            relief="raised", borderwidth=5, cursor="hand2"
        )
        self.stop_btn.pack(fill=tk.X, padx=10, pady=10, ipady=20)
        self.stop_btn.bind("<Button-1>", lambda event: self.toggle_active())

        slider_frame = tk.LabelFrame(self.root, text="Shocker Settings", padx=10, pady=10)
        slider_frame.pack(fill=tk.X, padx=10, pady=5)

        self.max_intensity_var = tk.IntVar(value=30)
        tk.Scale(
            slider_frame, from_=1, to=100, orient=tk.HORIZONTAL, 
            label="Maximum Allowed Intensity (%)", variable=self.max_intensity_var
        ).pack(fill=tk.X)

        self.max_duration_var = tk.DoubleVar(value=1.0)
        self.max_duration_slider = tk.Scale(
            slider_frame, from_=0.3, to=10.0, resolution=0.1, orient=tk.HORIZONTAL, 
            label="Maximum Allowed Duration (Seconds)", variable=self.max_duration_var
        ).pack(fill=tk.X)

        self.cooldown_var = tk.DoubleVar(value=5.0)
        self.cooldown_slider = tk.Scale(
            slider_frame, from_=1.0, to=10.0, resolution=0.5, orient=tk.HORIZONTAL, 
            label="Cooldown Between Shocks (Seconds)", variable=self.cooldown_var
        ).pack(fill=tk.X)

        self.test_mode_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            slider_frame, text="Vibrate Mode", 
            variable=self.test_mode_var, font=("Helvetica", 10, "bold"), fg="blue"
        ).pack(anchor="w", pady=(10, 0))

        tk.Frame(slider_frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=10)

        self.dynamic_mode_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            slider_frame, text="Physbone Stretch Mode", 
            variable=self.dynamic_mode_var, font=("Helvetica", 10, "bold"), fg="purple"
        ).pack(anchor="w", pady=(0, 5))

        status_frame = tk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        tk.Label(status_frame, text="System Status:", font=("Helvetica", 12)).pack(side=tk.LEFT)
        self.status_label = tk.Label(status_frame, text="READY", fg="green", font=("Helvetica", 12, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self.shock_count_label = tk.Label(status_frame, text="Shocks This Session: 0", font=("Helvetica", 10))
        self.shock_count_label.pack(side=tk.RIGHT)

        self.log_area = scrolledtext.ScrolledText(self.root, height=10, state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        self.max_intensity_var.trace_add("write", lambda *_: self._send_osc_if_user(MTS_INTENSITY, self.max_intensity_var.get() / 100.0))
        self.max_duration_var.trace_add("write", lambda *_: self._send_osc_if_user(MTS_DURATION, self.max_duration_var.get() / 10.0))
        self.cooldown_var.trace_add("write", lambda *_: self._send_osc_if_user(MTS_COOLDOWN, self.cooldown_var.get() / 10.0))
        self.test_mode_var.trace_add("write", lambda *_: self._send_osc_if_user(MTS_VIBRATE, self.test_mode_var.get()))
        self.dynamic_mode_var.trace_add("write", self._on_dynamic_mode_changed)

    def _send_osc_if_user(self, address, value):
        if not self._updating_from_osc:
            try:
                self.osc_client.send_message(address, value)
            except Exception:
                pass
                
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
        
    def _on_dynamic_mode_changed(self, *args):
        if self.dynamic_mode_var.get():
            self.max_duration_slider.config(state=tk.DISABLED, fg="gray")
            self.cooldown_slider.config(state=tk.DISABLED, fg="gray")
            self.log_message("Physbone Stretch Mode enabled.")
        else:
            self.max_duration_slider.config(state=tk.NORMAL, fg="black")
            self.cooldown_slider.config(state=tk.NORMAL, fg="black")
            self.log_message("Random Mode enabled.")
        self._send_osc_if_user(MTS_DYNAMIC, self.dynamic_mode_var.get())

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
            val = float(args[0])
            if val < 0.03: 
                val = 0.03
            seconds = val * 10.0
            self.root.after(0, self._set_var_from_osc, self.max_duration_var, round(seconds, 1))

    def on_mts_cooldown(self, address, *args):
        if args:
            val = float(args[0])
            seconds = val * 10.0
            if seconds < 1.0: 
                seconds = 1.0 
            self.root.after(0, self._set_var_from_osc, self.cooldown_var, round(seconds, 1))

    def send_openshock_command(self, intensity, duration_ms, action_type, log_success=True):
        if not self.api_key or not self.shocker_ids:
            return

        url = "https://api.openshock.app/2/shockers/control"
        
        action_map = {"Stop": 0, "Shock": 1, "Vibrate": 2, "Sound": 3}
        action_int = action_map.get(action_type, 2)

        target_ids = self.shocker_ids
        if self.shocker_mode == "Random" and len(self.shocker_ids) > 1:
            target_ids = [random.choice(self.shocker_ids)]

        shocks_payload = []
        for sid in target_ids:
            shocks_payload.append({
                "id": sid,
                "type": action_int,
                "intensity": intensity,
                "duration": duration_ms
            })

        payload = {
            "shocks": shocks_payload,
            "customName": "MayuTail"
        }

        headers = {
            "OpenShockToken": self.api_key,
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=2.0)
            if response.status_code == 200:
                if log_success:
                    self.log_message(f"SUCCESS (HTTP): {action_type} command sent.")
            else:
                if log_success:
                    self.log_message(f"HTTP Error: Received {response.status_code} from OpenShock API")
        except Exception:
            if log_success:
                self.log_message("FAIL SAFE: Could not send command (HTTP Timeout/Error).")

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.api_key = data.get("api_key", "")
                    self.shocker_ids = data.get("shocker_ids", [])
                    self.shocker_mode = data.get("shocker_mode", "All")
                    self.param_grabbed = data.get("param_grabbed") or DEFAULT_PARAM_GRABBED
                    self.param_stretch = data.get("param_stretch") or DEFAULT_PARAM_STRETCH
                    
                    # Convert old single shocker config
                    if "shocker_id" in data and data["shocker_id"]:
                        if data["shocker_id"] not in self.shocker_ids:
                            self.shocker_ids.append(data["shocker_id"])
                        self._save_config()
                    
                    if len(self.shocker_ids) <= 1:
                        self.shocker_mode = "All"
                        
                if self.api_key and self.shocker_ids:
                    self.log_message("Configuration loaded successfully.")
                    return
            except Exception:
                self.log_message("Warning: Error reading config.json.")
                
        self.log_message("SETUP REQUIRED: Go to File > API Config to add your API Key, then File > Shocker Config to add Shockers.")

    def _save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump({
                    "api_key": self.api_key, 
                    "shocker_ids": self.shocker_ids,
                    "shocker_mode": self.shocker_mode,
                    "param_grabbed": self.param_grabbed,
                    "param_stretch": self.param_stretch
                }, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Could not write configuration file:\n{e}")

    def open_api_config(self):
        modal = APIConfigModal(self.root, "API Configuration", self.api_key)
        if modal.result:
            self.api_key = modal.result["api_key"]
            self._save_config()
            self.log_message("API configuration saved.")

    def open_osc_config(self):
        modal = OSCConfigModal(self.root, "OSC Configuration", self.param_grabbed, self.param_stretch)
        if modal.result:
            old_grabbed = self.param_grabbed
            old_stretch = self.param_stretch

            self.param_grabbed = modal.result["param_grabbed"] or DEFAULT_PARAM_GRABBED
            self.param_stretch = modal.result["param_stretch"] or DEFAULT_PARAM_STRETCH
            
            self._save_config()
            self.log_message("OSC configuration saved.")

            if old_grabbed != self.param_grabbed or old_stretch != self.param_stretch:
                self.log_message("OSC Parameters changed. Restarting OSC listener...")
                threading.Thread(target=self._restart_osc_server, daemon=True).start()

    def open_shocker_config(self):
        modal = ShockerConfigModal(self.root, "Shocker Configuration", self.shocker_ids, self.shocker_mode)
        if modal.result:
            self.shocker_ids = modal.result["shocker_ids"]
            self.shocker_mode = modal.result["shocker_mode"]
            
            self._save_config()
            self.log_message("Shocker configuration saved.")

    def open_github(self):
        webbrowser.open("https://github.com/SkyeCA/MayuTailShocker")

    def open_about(self):
        about_window = tk.Toplevel(self.root)
        about_window.title("About")
        about_window.geometry("300x250")
        about_window.resizable(False, False)
        try:
            icon_image = tk.PhotoImage(file=resource_path("resources/icon.png"))
            icon_label = tk.Label(about_window, image=icon_image)
            icon_label.image = icon_image
            icon_label.pack(pady=(15, 5))
        except Exception:
            pass
        tk.Label(about_window, text="Mayu Tail Shocker", font=("Helvetica", 12, "bold")).pack()
        tk.Label(about_window, text="Created by SkyeCA", font=("Helvetica", 10)).pack(pady=(0, 10))
        link_lbl = tk.Label(about_window, text="https://vore.my", font=("Helvetica", 10, "underline"), fg="blue", cursor="hand2")
        link_lbl.pack()
        link_lbl.bind("<Button-1>", lambda e: webbrowser.open("https://vore.my"))
        tk.Button(about_window, text="Close", command=about_window.destroy).pack(pady=15)

    def toggle_active(self, from_osc=False):
        self.is_active = not self.is_active
        if self.is_active:
            self.stop_btn.config(text="Disable", bg="red", relief="raised")
            self.status_label.config(text="READY", fg="green")
            self.log_message("System Enabled.")
        else:
            self.stop_btn.config(text="Enable", bg="green", relief="sunken")
            self.status_label.config(text="DISABLED", fg="red")
            self.log_message("System Disabled.")
            threading.Thread(target=self.send_halt_command, daemon=True).start()
            
        if not from_osc:
            self._send_osc_if_user(MTS_ENABLE, self.is_active)

    def log_message(self, message):
        self.root.after(0, self._safe_log, message)

    def _safe_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def trigger_shock(self):
        if not self.api_key or not self.shocker_ids:
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
        
        duration_s = round(random.uniform(0.3, max_d), 2) if max_d > 0.3 else 0.3
        duration_ms = int(duration_s * 1000)
        intensity = random.randint(1, max_i) if max_i > 1 else 1

        if action_type == "Shock":
            self.session_shock_count += 1
            self.root.after(0, self._update_shock_count_ui)

        self.log_message(f"Triggering Burst: {intensity}% intensity for {duration_s}s ({action_type})")
        threading.Thread(target=self.send_openshock_command, args=(intensity, duration_ms, action_type), daemon=True).start()

    def dynamic_shock_loop(self):
        with self.lock:
            if self.is_dynamic_loop_running:
                return
            self.is_dynamic_loop_running = True
            
        self.log_message("Physbone Stretch: Started.")

        is_real_shock = not self.test_mode_var.get()
        if is_real_shock:
            self.session_shock_count += 1
            self.root.after(0, self._update_shock_count_ui)
            
        accumulated_time = 0.0

        while self.is_active and self.dynamic_mode_var.get() and self.is_grabbed and self.current_stretch > 0.1:
            max_i = self.max_intensity_var.get()
            
            stretch_clamped = min(max(self.current_stretch, 0.0), 1.0)
            intensity = int(stretch_clamped * max_i)
            if intensity < 1:
                intensity = 1
                
            action_type = "Vibrate" if self.test_mode_var.get() else "Shock"
            
            duration_ms = 400 
            self.send_openshock_command(intensity, duration_ms, action_type, log_success=False) 
            
            time.sleep(0.2)
            
            if is_real_shock:
                accumulated_time += 0.2
                if accumulated_time >= 1.0:
                    self.session_shock_count += 1
                    self.root.after(0, self._update_shock_count_ui)
                    accumulated_time -= 1.0
            
        if self.is_active:
            self.send_openshock_command(0, 300, "Stop", log_success=False)
            
        self.log_message("Physbone Stretch: Ended.")

        with self.lock:
            self.is_dynamic_loop_running = False
            self.last_shock_time = time.time()
            self.root.after(0, self._update_cooldown_ui)

    def _update_cooldown_ui(self):
        if not self.is_active or self.dynamic_mode_var.get():
            self.status_label.config(text="READY", fg="green")
            return 

        time_passed = time.time() - self.last_shock_time
        remaining_cooldown = self.cooldown_var.get() - time_passed
        
        if remaining_cooldown > 0:
            self.status_label.config(text=f"COOLDOWN ({remaining_cooldown:.1f}s)", fg="orange")
            self.root.after(100, self._update_cooldown_ui)
        else:
            self.status_label.config(text="READY", fg="green")

    def _update_shock_count_ui(self):
        self.shock_count_label.config(text=f"Shocks This Session: {self.session_shock_count}")

    def send_halt_command(self):
        self.send_openshock_command(0, 300, "Stop")

    def on_grabbed_update(self, address, *args):
        if args:
            self.is_grabbed = bool(args[0])
            self.evaluate_state()

    def on_stretch_update(self, address, *args):
        if args:
            self.current_stretch = float(args[0])
            self.evaluate_state()

    def evaluate_state(self):
        if self.is_grabbed and self.current_stretch > 0.1:
            if self.dynamic_mode_var.get():
                if not self.is_dynamic_loop_running:
                    threading.Thread(target=self.dynamic_shock_loop, daemon=True).start()
            else:
                self.trigger_shock()

    def save_shock_stats(self):
        if self.session_shock_count > 0:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                log_file_path = os.path.join(os.path.dirname(sys.argv[0]), "shock_log.txt")
                with open(log_file_path, "a") as f:
                    f.write(f"[{timestamp}] Session ended. Total shocks sent/scaled: {self.session_shock_count}\n")
            except Exception:
                pass

    def _start_osc_server(self):
        dispatcher = Dispatcher()
        dispatcher.map(self.param_grabbed, self.on_grabbed_update)
        dispatcher.map(self.param_stretch, self.on_stretch_update)
        dispatcher.map(MTS_ENABLE, self.on_mts_enable)
        dispatcher.map(MTS_VIBRATE, self.on_mts_vibrate)
        dispatcher.map(MTS_DYNAMIC, self.on_mts_dynamic)
        dispatcher.map(MTS_INTENSITY, self.on_mts_intensity)
        dispatcher.map(MTS_DURATION, self.on_mts_duration)
        dispatcher.map(MTS_COOLDOWN, self.on_mts_cooldown)

        self.server = BlockingOSCUDPServer((OSC_IP, OSC_PORT), dispatcher)
        
        self.osc_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.osc_thread.start()
        
    def _restart_osc_server(self):
        try:
            self.server.shutdown()
        except Exception:
            pass
        self._start_osc_server()
        self.log_message("OSC listener restarted and mapped to new parameters.")

    def quit_app(self):
        self.save_shock_stats()
        try:
            self.server.shutdown()
        except Exception:
            pass
        self.root.quit()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = TailShockerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.quit_app)
    root.mainloop()

if __name__ == "__main__":
    main()