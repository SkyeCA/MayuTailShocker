import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
from tkinter import font as tkfont
import threading
import time
import random
import requests
import json
from datetime import datetime
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
import sys
import os

# ==========================================
# CONSTANTS & PERSISTENT FILE PATH
# ==========================================
OSC_IP = "127.0.0.1"
OSC_PORT = 9001 
OPENSHOCK_API_URL = "https://api.openshock.app/1/shockers/control"

# Default VRChat Parameter Paths
DEFAULT_PARAM_GRABBED = "/avatar/parameters/Tail/_IsGrabbed"
DEFAULT_PARAM_STRETCH = "/avatar/parameters/Tail/_Stretch"

CONFIG_FILE = os.path.join(os.path.dirname(sys.argv[0]), "config.json")

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def resource_path(relative_path):
    # Handle resources inside PyInstaller tempfolder
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class SettingsModal(simpledialog.Dialog):
    """ Modal dialog window for inputting settings """
    def __init__(self, parent, title, current_key, current_id, param_grabbed, param_stretch):
        self.current_key = current_key
        self.current_id = current_id
        self.param_grabbed = param_grabbed
        self.param_stretch = param_stretch
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        # OpenShock Settings
        tk.Label(master, text="OpenShock API Key:", anchor="w").pack(fill=tk.X, pady=(5, 2))
        self.key_entry = tk.Entry(master, width=55)
        self.key_entry.insert(0, self.current_key)
        self.key_entry.pack(fill=tk.X, pady=(0, 10))

        tk.Label(master, text="Shocker ID:", anchor="w").pack(fill=tk.X, pady=(5, 2))
        self.id_entry = tk.Entry(master, width=55)
        self.id_entry.insert(0, self.current_id)
        self.id_entry.pack(fill=tk.X, pady=(0, 10))
        
        # Visual Divider
        tk.Frame(master, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=10)

        # VRChat Parameter Settings
        tk.Label(master, text="OSC Grab Parameter:", anchor="w").pack(fill=tk.X, pady=(5, 2))
        self.grab_entry = tk.Entry(master, width=55)
        self.grab_entry.insert(0, self.param_grabbed)
        self.grab_entry.pack(fill=tk.X, pady=(0, 10))

        tk.Label(master, text="OSC Stretch Parameter:", anchor="w").pack(fill=tk.X, pady=(5, 2))
        self.stretch_entry = tk.Entry(master, width=55)
        self.stretch_entry.insert(0, self.param_stretch)
        self.stretch_entry.pack(fill=tk.X, pady=(0, 5))
        
        return self.key_entry  # Sets initial keyboard focus

    def apply(self):
        # Store the values when the user clicks 'OK'
        self.result = {
            "api_key": self.key_entry.get().strip(),
            "shocker_id": self.id_entry.get().strip(),
            "param_grabbed": self.grab_entry.get().strip(),
            "param_stretch": self.stretch_entry.get().strip()
        }

# ==========================================
# MAIN APPLICATION LOGIC
# ==========================================
class TailShockerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mayu Tail Shock Controller")
        
        # Load the PNG icon
        try:
            icon_image = tk.PhotoImage(file=resource_path("resources/icon.png"))
            self.root.iconphoto(True, icon_image) 
        except Exception:
            pass 

        self.root.geometry("500x740") 
        
        # Internal configuration states
        self.api_key = ""
        self.shocker_id = ""
        self.param_grabbed = DEFAULT_PARAM_GRABBED
        self.param_stretch = DEFAULT_PARAM_STRETCH
        
        # State variables
        self.is_active = True
        self.last_shock_time = 0.0
        self.is_grabbed = False
        self.current_stretch = 0.0
        self.session_shock_count = 0
        
        # Threading lock
        self.lock = threading.Lock()

        self._build_gui()
        self._load_config()
        self._start_osc_server()

    def _build_gui(self):
        # Master Stop Button
        button_font = tkfont.Font(size=20, weight="bold")
        self.stop_btn = tk.Label(
            self.root, 
            text="EMERGENCY STOP\n(Click to Disable)", 
            bg="red", 
            fg="white", 
            font=button_font,
            relief="raised",
            borderwidth=5,
            cursor="hand2"
        )
        self.stop_btn.pack(fill=tk.X, padx=10, pady=10, ipady=20)
        self.stop_btn.bind("<Button-1>", lambda event: self.toggle_active())

        # Top Control Buttons Frame (Settings Button)
        control_frame = tk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.settings_btn = tk.Button(
            control_frame, 
            text="⚙ Settings & Configuration", 
            command=self.open_settings,
            font=("Helvetica", 10, "bold")
        )
        self.settings_btn.pack(side=tk.LEFT)

        # Safety Sliders & Settings Frame
        slider_frame = tk.LabelFrame(self.root, text="Safety Caps & Behavior", padx=10, pady=10)
        slider_frame.pack(fill=tk.X, padx=10, pady=5)

        self.max_intensity_var = tk.IntVar(value=30)
        tk.Scale(
            slider_frame, 
            from_=1, to=100, 
            orient=tk.HORIZONTAL, 
            label="Maximum Allowed Intensity (%)", 
            variable=self.max_intensity_var
        ).pack(fill=tk.X)

        self.max_duration_var = tk.DoubleVar(value=1.0)
        tk.Scale(
            slider_frame, 
            from_=0.3, to=3.0, 
            resolution=0.1,
            orient=tk.HORIZONTAL, 
            label="Maximum Allowed Duration (Seconds)", 
            variable=self.max_duration_var
        ).pack(fill=tk.X)

        self.cooldown_var = tk.DoubleVar(value=5.0)
        tk.Scale(
            slider_frame, 
            from_=1.0, to=10.0, 
            resolution=0.5,
            orient=tk.HORIZONTAL, 
            label="Cooldown Between Events (Seconds)", 
            variable=self.cooldown_var
        ).pack(fill=tk.X)

        # Test Mode Checkbox
        self.test_mode_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            slider_frame, 
            text="Test Mode (Vibrate Only)", 
            variable=self.test_mode_var,
            font=("Helvetica", 10, "bold"),
            fg="blue"
        ).pack(anchor="w", pady=(10, 0))

        # Status Indicator Frame
        status_frame = tk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        tk.Label(status_frame, text="System Status:", font=("Helvetica", 12)).pack(side=tk.LEFT)
        self.status_label = tk.Label(status_frame, text="READY", fg="green", font=("Helvetica", 12, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self.shock_count_label = tk.Label(status_frame, text="Shocks This Session: 0", font=("Helvetica", 10))
        self.shock_count_label.pack(side=tk.RIGHT)

        # Log Text Box
        self.log_area = scrolledtext.ScrolledText(self.root, height=10, state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        self.log_message("System Started. Listening for OSC data...")

    def _load_config(self):
        """ Read settings from configuration file if it exists """
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.api_key = data.get("api_key", "")
                    self.shocker_id = data.get("shocker_id", "")
                    # Fallback to default if the config field exists but is empty
                    self.param_grabbed = data.get("param_grabbed") or DEFAULT_PARAM_GRABBED
                    self.param_stretch = data.get("param_stretch") or DEFAULT_PARAM_STRETCH
                    
                if self.api_key and self.shocker_id:
                    self.log_message("Configuration loaded successfully.")
                    return
            except Exception:
                self.log_message("Warning: Error reading config.json.")
        
        self.log_message("SETUP REQUIRED: Click 'Settings & Configuration' to add your API Key and Shocker ID.")

    def open_settings(self):
        """ Open modal and handle setting adjustments """
        modal = SettingsModal(
            self.root, 
            "Configuration", 
            self.api_key, 
            self.shocker_id, 
            self.param_grabbed, 
            self.param_stretch
        )
        
        if modal.result:
            old_grabbed = self.param_grabbed
            old_stretch = self.param_stretch

            self.api_key = modal.result["api_key"]
            self.shocker_id = modal.result["shocker_id"]
            
            # If the user clears the entry entirely, force the fallback to default
            self.param_grabbed = modal.result["param_grabbed"] or DEFAULT_PARAM_GRABBED
            self.param_stretch = modal.result["param_stretch"] or DEFAULT_PARAM_STRETCH
            
            try:
                with open(CONFIG_FILE, 'w') as f:
                    json.dump({
                        "api_key": self.api_key, 
                        "shocker_id": self.shocker_id,
                        "param_grabbed": self.param_grabbed,
                        "param_stretch": self.param_stretch
                    }, f, indent=4)
                self.log_message("Configuration saved and updated.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not write configuration file:\n{e}")

            # If OSC parameters were changed, safely restart the server in the background
            if old_grabbed != self.param_grabbed or old_stretch != self.param_stretch:
                self.log_message("OSC Parameters changed. Restarting OSC listener...")
                threading.Thread(target=self._restart_osc_server, daemon=True).start()

    def toggle_active(self):
        self.is_active = not self.is_active
        if self.is_active:
            self.stop_btn.config(text="Disable", bg="red", relief="raised")
            self.status_label.config(text="READY", fg="green")
            self.log_message("System ENABLED.")
        else:
            self.stop_btn.config(text="Enable", bg="green", relief="sunken")
            self.status_label.config(text="DISABLED", fg="red")
            self.log_message("System DISABLED. Sending stop command...")
            
            threading.Thread(target=self.send_halt_command, daemon=True).start()

    def log_message(self, message):
        self.root.after(0, self._safe_log, message)

    def _safe_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def trigger_shock(self):
        if not self.api_key or not self.shocker_id:
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

        self.log_message(f"Triggering: {intensity}% intensity for {duration_s}s ({action_type})")
        
        threading.Thread(
            target=self.send_openshock_command, 
            args=(intensity, duration_ms, action_type), 
            daemon=True
        ).start()

    def _update_cooldown_ui(self):
        if not self.is_active:
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

    def send_openshock_command(self, intensity, duration_ms, action_type):
        if not self.api_key or not self.shocker_id:
            return

        try:
            headers = {
                "accept": "application/json",
                "OpenShockToken": self.api_key,
                "Content-Type": "application/json"
            }
            
            payload = [
                {
                    "id": self.shocker_id,
                    "type": action_type,
                    "intensity": intensity,
                    "duration": duration_ms
                }
            ]

            response = requests.post(
                OPENSHOCK_API_URL, 
                headers=headers, 
                data=json.dumps(payload),
                timeout=2.0 
            )
            
            if response.status_code == 200:
                self.log_message(f"SUCCESS: {action_type} command sent.")
                if action_type == "Shock":
                    self.session_shock_count += 1
                    self.root.after(0, self._update_shock_count_ui)
            else:
                error_msg = f"ERROR: API returned {response.status_code}"
                if response.text:
                    error_msg += f" - Details: {response.text.strip()}"
                self.log_message(error_msg)
                
        except Exception:
            self.log_message(f"FAIL SAFE TRIGGERED: Could not send {action_type} command.")

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
            self.trigger_shock()

    def save_shock_stats(self):
        if self.session_shock_count > 0:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                log_file_path = os.path.join(os.path.dirname(sys.argv[0]), "shock_log.txt")
                with open(log_file_path, "a") as f:
                    f.write(f"[{timestamp}] Session ended. Total shocks sent: {self.session_shock_count}\n")
            except Exception:
                pass

    def _start_osc_server(self):
        dispatcher = Dispatcher()
        dispatcher.map(self.param_grabbed, self.on_grabbed_update)
        dispatcher.map(self.param_stretch, self.on_stretch_update)

        self.server = BlockingOSCUDPServer((OSC_IP, OSC_PORT), dispatcher)
        
        self.osc_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.osc_thread.start()
        
    def _restart_osc_server(self):
        """ Shut down the running server safely and start a new one with updated mappings """
        try:
            self.server.shutdown()
        except Exception:
            pass
        self._start_osc_server()
        self.log_message("OSC listener restarted and mapped to new parameters.")

def main():
    root = tk.Tk()
    app = TailShockerApp(root)
    
    def on_closing():
        app.save_shock_stats()
        # Shutdown server gracefully before exiting to free the socket port
        try:
            app.server.shutdown()
        except Exception:
            pass
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()