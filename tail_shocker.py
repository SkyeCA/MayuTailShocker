import tkinter as tk
from tkinter import scrolledtext
from tkinter import font as tkfont
import threading
import time
import random
import requests
import json
import sys
import os
from datetime import datetime
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

# ==========================================
# CONFIGURATION
# ==========================================
OSC_IP = "127.0.0.1"
OSC_PORT = 9001

# OpenShock Configuration
OPENSHOCK_API_URL = "https://api.openshock.app/1/shockers/control"
OPENSHOCK_API_KEY = "837bdGIHHfMv9ijVeGqMzuDqWJthIdadNb0MaPPKmOXVh92JkdR0klTZyccQV73j"
SHOCKER_ID = "019f6765-ad55-79cb-aaf9-19ebab56b811"

# VRChat Parameter Paths
PARAM_GRABBED = "/avatar/parameters/Tail/_IsGrabbed"
PARAM_STRETCH = "/avatar/parameters/Tail/_Stretch"

# ==========================================
# BUILD HELPERS
# ==========================================
def resource_path(relative_path):
        try:
            # Handle resources inside PyInstaller tempfolder
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

# ==========================================
# MAIN APPLICATION LOGIC
# ==========================================
class TailShockerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mayu Tail Shock Controller")
        icon_image = tk.PhotoImage(file=resource_path("resources/icon.png"))
        self.root.iconphoto(True, icon_image)
        self.root.geometry("500x700") 
        
        self.is_active = True
        self.last_shock_time = 0.0
        self.is_grabbed = False
        self.current_stretch = 0.0
        self.session_shock_count = 0
        
        self.lock = threading.Lock()

        self._build_gui()
        self._start_osc_server()

    def _build_gui(self):
        # Enable/Disable Button
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

        # Safety and Settings Frame
        slider_frame = tk.LabelFrame(self.root, text="Safety Caps & Settings", padx=10, pady=10)
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
        
        # Shock Counter Label
        self.shock_count_label = tk.Label(status_frame, text="Tail Pulls This Session: 0", font=("Helvetica", 10))
        self.shock_count_label.pack(side=tk.RIGHT)

        # Log Text Box
        self.log_area = scrolledtext.ScrolledText(self.root, height=10, state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        self.log_message("System Started. Listening for OSC data...")

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
        self.shock_count_label.config(text=f"Tail Pulls This Session: {self.session_shock_count}")

    def send_halt_command(self):
        self.send_openshock_command(0, 300, "Stop")

    def send_openshock_command(self, intensity, duration_ms, action_type):
        try:
            headers = {
                "accept": "application/json",
                "OpenShockToken": OPENSHOCK_API_KEY,
                "Content-Type": "application/json"
            }
            
            payload = [
                {
                    "id": SHOCKER_ID,
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
                with open("shock_log.txt", "a") as f:
                    f.write(f"[{timestamp}] Session ended. Total tail pulls: {self.session_shock_count}\n")
            except Exception as e:
                pass

    def _start_osc_server(self):
        dispatcher = Dispatcher()
        dispatcher.map(PARAM_GRABBED, self.on_grabbed_update)
        dispatcher.map(PARAM_STRETCH, self.on_stretch_update)

        self.server = BlockingOSCUDPServer((OSC_IP, OSC_PORT), dispatcher)
        
        self.osc_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.osc_thread.start()

def main():
    root = tk.Tk()
    app = TailShockerApp(root)
    
    def on_closing():
        app.save_shock_stats()
        app.server.shutdown()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()