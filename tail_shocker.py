import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
from tkinter import font as tkfont
import threading
import time
import random
import json
import webbrowser
from datetime import datetime
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
import websocket  # Requires: pip install websocket-client
import requests
import sys
import os

# ==========================================
# CONSTANTS & PERSISTENT FILE PATH
# ==========================================
OSC_IP = "127.0.0.1"
OSC_PORT = 9001 

# OpenShock Live Control Gateway Base URL
OPENSHOCK_WS_GW = "wss://de1-gateway.openshock.app"

DEFAULT_PARAM_GRABBED = "/avatar/parameters/Tail/_IsGrabbed"
DEFAULT_PARAM_STRETCH = "/avatar/parameters/Tail/_Stretch"

CONFIG_FILE = os.path.join(os.path.dirname(sys.argv[0]), "config.json")

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class SettingsModal(simpledialog.Dialog):
    def __init__(self, parent, title, current_key, current_id, param_grabbed, param_stretch):
        self.current_key = current_key
        self.current_id = current_id
        self.param_grabbed = param_grabbed
        self.param_stretch = param_stretch
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        tk.Label(master, text="OpenShock API Key:", anchor="w").pack(fill=tk.X, pady=(5, 2))
        self.key_entry = tk.Entry(master, width=55)
        self.key_entry.insert(0, self.current_key)
        self.key_entry.pack(fill=tk.X, pady=(0, 10))

        tk.Label(master, text="Shocker ID:", anchor="w").pack(fill=tk.X, pady=(5, 2))
        self.id_entry = tk.Entry(master, width=55)
        self.id_entry.insert(0, self.current_id)
        self.id_entry.pack(fill=tk.X, pady=(0, 10))
        
        tk.Frame(master, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=10)

        tk.Label(master, text="VRChat Grab Parameter (Boolean):", anchor="w").pack(fill=tk.X, pady=(5, 2))
        self.grab_entry = tk.Entry(master, width=55)
        self.grab_entry.insert(0, self.param_grabbed)
        self.grab_entry.pack(fill=tk.X, pady=(0, 10))

        tk.Label(master, text="VRChat Stretch Parameter (Float):", anchor="w").pack(fill=tk.X, pady=(5, 2))
        self.stretch_entry = tk.Entry(master, width=55)
        self.stretch_entry.insert(0, self.param_stretch)
        self.stretch_entry.pack(fill=tk.X, pady=(0, 5))
        
        return self.key_entry 

    def apply(self):
        self.result = {
            "api_key": self.key_entry.get().strip(),
            "shocker_id": self.id_entry.get().strip(),
            "param_grabbed": self.grab_entry.get().strip(),
            "param_stretch": self.stretch_entry.get().strip()
        }

class TailShockerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mayu Tail Shock Controller")
        
        try:
            icon_image = tk.PhotoImage(file=resource_path("resources/icon.png"))
            self.root.iconphoto(True, icon_image) 
        except Exception:
            pass 

        self.root.geometry("500x740") 
        
        self.api_key = ""
        self.shocker_id = ""
        self.param_grabbed = DEFAULT_PARAM_GRABBED
        self.param_stretch = DEFAULT_PARAM_STRETCH
        
        self.is_active = True
        self.last_shock_time = 0.0
        self.is_grabbed = False
        self.current_stretch = 0.0
        self.session_shock_count = 0
        self.is_dynamic_loop_running = False
        
        self.ws = None
        self.ws_connected = False
        self.lock = threading.Lock()

        self._build_menu()
        self._build_gui()
        self._load_config()
        self._start_osc_server()
        
        # Start the WebSocket connection manager
        threading.Thread(target=self._websocket_thread_loop, daemon=True).start()

    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Settings", command=self.open_settings)
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
            self.root, 
            text="Disable", 
            bg="red", 
            fg="white", 
            font=button_font,
            relief="raised",
            borderwidth=5,
            cursor="hand2"
        )
        self.stop_btn.pack(fill=tk.X, padx=10, pady=10, ipady=20)
        self.stop_btn.bind("<Button-1>", lambda event: self.toggle_active())

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
        self.max_duration_slider = tk.Scale(
            slider_frame, 
            from_=0.3, to=3.0, 
            resolution=0.1,
            orient=tk.HORIZONTAL, 
            label="Maximum Allowed Duration (Seconds)", 
            variable=self.max_duration_var
        )
        self.max_duration_slider.pack(fill=tk.X)

        self.cooldown_var = tk.DoubleVar(value=5.0)
        self.cooldown_slider = tk.Scale(
            slider_frame, 
            from_=1.0, to=10.0, 
            resolution=0.5,
            orient=tk.HORIZONTAL, 
            label="Cooldown Between Triggers (Seconds)", 
            variable=self.cooldown_var
        )
        self.cooldown_slider.pack(fill=tk.X)

        self.test_mode_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            slider_frame, 
            text="Test Mode (Send VIBRATIONS instead of Shocks)", 
            variable=self.test_mode_var,
            font=("Helvetica", 10, "bold"),
            fg="blue"
        ).pack(anchor="w", pady=(10, 0))

        tk.Frame(slider_frame, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, pady=10)

        self.dynamic_mode_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            slider_frame, 
            text="Dynamic Stretch Mode (Intensity scales with pull, continuous)", 
            variable=self.dynamic_mode_var,
            font=("Helvetica", 10, "bold"),
            fg="purple",
            command=self.toggle_dynamic_mode
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
        
        self.log_message("System Started. Listening for OSC data...")

    # ==========================================
    # WEBSOCKET MANAGEMENT
    # ==========================================
    def _websocket_thread_loop(self):
        """ Keeps the websocket connected, reconnects on failure, and automates API discovery """
        while True:
            if self.api_key and self.shocker_id and self.is_active:
                
                # Standard Headers for HTTP Discovery
                http_headers = {
                    "accept": "application/json",
                    "OpenShockToken": self.api_key,
                    "User-Agent": "MayuTailShocker/1.0 (skey@vore.my)"
                }

                try:
                    # --- DISCOVERY STEP 1: Get the parent Device/Hub ID ---
                    self.log_message("Discovery: Fetching parent Hub ID...")
                    shocker_res = requests.get(
                        f"https://api.openshock.app/1/shockers/{self.shocker_id}", 
                        headers=http_headers, 
                        timeout=5.0
                    )
                    
                    if shocker_res.status_code != 200:
                        self.log_message(f"Discovery Error: Could not verify Shocker (HTTP {shocker_res.status_code})")
                        time.sleep(5)
                        continue
                        
                    hub_id = shocker_res.json().get("data", {}).get("device")
                    if not hub_id:
                        self.log_message("Discovery Error: Shocker is not linked to a Hub.")
                        time.sleep(5)
                        continue

                    # --- DISCOVERY STEP 2: Get the Regional Gateway ---
                    self.log_message("Discovery: Fetching Regional Gateway...")
                    lcg_res = requests.get(
                        f"https://api.openshock.app/2/devices/{hub_id}/lcg", 
                        headers=http_headers, 
                        timeout=5.0
                    )
                    
                    if lcg_res.status_code != 200:
                        self.log_message(f"Discovery Error: Hub is offline or missing (HTTP {lcg_res.status_code})")
                        time.sleep(5)
                        continue
                        
                    host = lcg_res.json().get("host")
                    if not host:
                        self.log_message("Discovery Error: No gateway host returned.")
                        time.sleep(5)
                        continue

                    # --- WEBSOCKET CONNECTION ---
                    # Build the secure URL using the discovered Host and Hub ID
                    ws_url = f"wss://{host}/1/ws/live/{hub_id}"
                    
                    # WebSocket specific headers (List of strings, not a dict)
                    ws_headers = [
                        f"OpenShockToken: {self.api_key}",
                        "User-Agent: MayuTailShocker/1.0 (Python)"
                    ]
                    
                    self.log_message(f"Connecting WebSocket to: {host}")
                    
                    self.ws = websocket.WebSocketApp(
                        ws_url,
                        header=ws_headers,
                        on_open=self._on_ws_open,
                        on_message=self._on_ws_message,
                        on_error=self._on_ws_error,
                        on_close=self._on_ws_close
                    )
                    
                    # Run with Ping/Pong intervals to prevent silent idle disconnects
                    self.ws.run_forever(ping_interval=30, ping_timeout=10)

                except Exception as e:
                    self.log_message(f"Connection Manager Error: {e}")
            
            self.ws_connected = False
            # Wait 3 seconds before retrying the entire discovery/connection pipeline
            time.sleep(3)

    def _on_ws_open(self, ws):
        self.ws_connected = True
        self.log_message("WebSocket Connected Successfully to Live Gateway.")

    def _on_ws_message(self, ws, message):
        pass 

    def _on_ws_error(self, ws, error):
        self.log_message(f"WebSocket Error: {error}")

    def _on_ws_close(self, ws, close_status_code, close_msg):
        self.ws_connected = False
        self.log_message("WebSocket Disconnected. Attempting to reconnect...")

    def send_openshock_command(self, intensity, duration_ms, action_type, log_success=True):
        if not self.ws_connected or not self.ws:
            if log_success:
                self.log_message("Failed to send command: WebSocket not connected.")
            return

        payload = {
            "action": "control", 
            "data": [
                {
                    "id": self.shocker_id,
                    "type": action_type,
                    "intensity": intensity,
                    "duration": duration_ms
                }
            ]
        }

        try:
            self.ws.send(json.dumps(payload))
            if log_success:
                self.log_message(f"SUCCESS (WS): {action_type} command sent.")
            
            if action_type == "Shock":
                self.session_shock_count += 1
                self.root.after(0, self._update_shock_count_ui)
        except Exception as e:
            if log_success:
                self.log_message(f"FAIL SAFE TRIGGERED: Could not send {action_type} command over WS.")

    # ==========================================
    # CONFIG & UI LOGIC
    # ==========================================
    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.api_key = data.get("api_key", "")
                    self.shocker_id = data.get("shocker_id", "")
                    self.param_grabbed = data.get("param_grabbed") or DEFAULT_PARAM_GRABBED
                    self.param_stretch = data.get("param_stretch") or DEFAULT_PARAM_STRETCH
                    
                if self.api_key and self.shocker_id:
                    self.log_message("Configuration loaded successfully.")
                    return
            except Exception:
                self.log_message("Warning: Error reading config.json.")
        
        self.log_message("SETUP REQUIRED: Go to File > Settings to add your API Key and Shocker ID.")

    def open_settings(self):
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
            old_key = self.api_key
            old_id = self.shocker_id

            self.api_key = modal.result["api_key"]
            self.shocker_id = modal.result["shocker_id"]
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

            if old_grabbed != self.param_grabbed or old_stretch != self.param_stretch:
                self.log_message("OSC Parameters changed. Restarting OSC listener...")
                threading.Thread(target=self._restart_osc_server, daemon=True).start()
                
            # If the API key OR Shocker ID changes, force the websocket to drop and reconnect with the new URL
            if (old_key != self.api_key or old_id != self.shocker_id) and self.ws:
                self.ws.close()

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
            
        tk.Label(about_window, text="Mayu Tail Shock Controller", font=("Helvetica", 12, "bold")).pack()
        tk.Label(about_window, text="Created by SkyeCA", font=("Helvetica", 10)).pack(pady=(0, 10))
        
        link_lbl = tk.Label(about_window, text="https://vore.my", font=("Helvetica", 10, "underline"), fg="blue", cursor="hand2")
        link_lbl.pack()
        link_lbl.bind("<Button-1>", lambda e: webbrowser.open("https://vore.my"))
        
        tk.Button(about_window, text="Close", command=about_window.destroy).pack(pady=15)

    def toggle_dynamic_mode(self):
        if self.dynamic_mode_var.get():
            self.max_duration_slider.config(state=tk.DISABLED, fg="gray")
            self.cooldown_slider.config(state=tk.DISABLED, fg="gray")
            self.log_message("MODE SWITCH: Dynamic Stretch Mode enabled.")
        else:
            self.max_duration_slider.config(state=tk.NORMAL, fg="black")
            self.cooldown_slider.config(state=tk.NORMAL, fg="black")
            self.log_message("MODE SWITCH: Random Burst Mode enabled.")

    def toggle_active(self):
        self.is_active = not self.is_active
        if self.is_active:
            self.stop_btn.config(text="Disable", bg="red", relief="raised")
            self.status_label.config(text="READY", fg="green")
            self.log_message("System ARMED.")
            if not self.ws_connected and self.ws:
                self.ws.close() 
        else:
            self.stop_btn.config(text="Enable", bg="green", relief="sunken")
            self.status_label.config(text="DISABLED", fg="red")
            self.log_message("System DISARMED. Sending Active Halt command...")
            threading.Thread(target=self.send_halt_command, daemon=True).start()
            if self.ws:
                self.ws.close()

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

        self.log_message(f"Triggering Burst: {intensity}% intensity for {duration_s}s ({action_type})")
        threading.Thread(target=self.send_openshock_command, args=(intensity, duration_ms, action_type), daemon=True).start()

    def dynamic_shock_loop(self):
        with self.lock:
            if self.is_dynamic_loop_running:
                return
            self.is_dynamic_loop_running = True
            
        self.log_message("Dynamic Stretch Interaction: STARTED.")

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
            
        if self.is_active:
            self.send_openshock_command(0, 300, "Stop", log_success=False)
            
        self.log_message("Dynamic Stretch Interaction: ENDED.")

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
        if self.ws:
            self.ws.close()
        self.root.quit()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = TailShockerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.quit_app)
    root.mainloop()

if __name__ == "__main__":
    main()