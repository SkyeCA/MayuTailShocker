import tkinter as tk
from tkinter import scrolledtext
from tkinter import font as tkfont
import threading
import time
import random
import requests
import json
from datetime import datetime
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

# ==========================================
# CONFIGURATION
# ==========================================
OSC_IP = "127.0.0.1"
OSC_PORT = 9001 # Default VRChat OSC Receive Port

# OpenShock Configuration
OPENSHOCK_API_URL = "https://api.openshock.app/1/shockers/control"
OPENSHOCK_API_KEY = "YOUR_API_KEY_HERE"
SHOCKER_ID = "YOUR_SHOCKER_ID_HERE"

# VRChat Parameter Paths (Update these when you expand the full paths)
PARAM_GRABBED = "/avatar/parameters/Tail/_IsGrabbed"
PARAM_STRETCH = "/avatar/parameters/Tail/_Stretch"
# ==========================================

class TailShockerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mayu Tail Shock Controller")
        self.root.geometry("500x620") # Slightly taller to fit the new slider
        
        # State variables
        self.is_active = True
        self.last_shock_time = 0.0
        
        self.current_grabbed = 0.0
        self.current_stretch = 0.0
        
        # Threading lock to prevent race conditions during API calls
        self.lock = threading.Lock()

        self._build_gui()
        self._start_osc_server()

    def _build_gui(self):
        # Master Stop Button (Using a Label to bypass macOS Button color limits)
        button_font = tkfont.Font(size=20, weight="bold")
        self.stop_btn = tk.Label(
            self.root, 
            text="Disable", 
            bg="red", 
            fg="white", 
            font=button_font,
            relief="raised",      # Makes it look 3D like a button
            borderwidth=5,
            cursor="hand2"        # Changes cursor to a hand on hover
        )
        self.stop_btn.pack(fill=tk.X, padx=10, pady=10, ipady=20)
        
        # Bind left mouse click to the toggle function
        self.stop_btn.bind("<Button-1>", lambda event: self.toggle_active())

        # Safety Sliders Frame
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

        # New Cooldown Slider
        self.cooldown_var = tk.DoubleVar(value=5.0)
        tk.Scale(
            slider_frame, 
            from_=1.0, to=10.0, 
            resolution=0.5,
            orient=tk.HORIZONTAL, 
            label="Cooldown (Seconds)", 
            variable=self.cooldown_var
        ).pack(fill=tk.X)

        # Log Text Box
        tk.Label(self.root, text="Action Log:").pack(anchor="w", padx=10, pady=(10, 0))
        self.log_area = scrolledtext.ScrolledText(self.root, height=10, state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.log_message("System Started. Listening for OSC data...")

    def toggle_active(self):
        self.is_active = not self.is_active
        if self.is_active:
            self.stop_btn.config(text="Disable", bg="red", relief="raised")
            self.log_message("System ENABLED.")
        else:
            self.stop_btn.config(text="Enable", bg="green", relief="sunken")
            self.log_message("System DISABLED. Sending Active Halt command...")
            
            # Fire an immediate halt command in a background thread
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
            
            # Use the UI slider value for cooldown calculation
            if current_time - self.last_shock_time < self.cooldown_var.get():
                return 
                
            self.last_shock_time = current_time

        # Retrieve hard caps from the UI
        max_i = self.max_intensity_var.get()
        max_d = self.max_duration_var.get()

        # Generate bounded random values
        duration_s = round(random.uniform(0.3, max_d), 2) if max_d > 0.3 else 0.3
        duration_ms = int(duration_s * 1000)
        intensity = random.randint(1, max_i) if max_i > 1 else 1

        self.log_message(f"Triggering: {intensity}% intensity for {duration_s}s")
        
        threading.Thread(
            target=self.send_openshock_command, 
            args=(intensity, duration_ms, "Shock"), 
            daemon=True
        ).start()

    def send_halt_command(self):
        # Sends an explicit Stop command to the API
        self.send_openshock_command(0, 0, "Stop")

    def send_openshock_command(self, intensity, duration_ms, action_type):
        try:
            headers = {
                "accept": "application/json",
                "OpenShockToken": OPENSHOCK_API_KEY,
                "Content-Type": "application/json"
            }
            
            payload = {
                "shocks": [
                    {
                        "id": SHOCKER_ID,
                        "intensity": intensity,
                        "duration": duration_ms,
                        "type": action_type
                    }
                ],
                "customName": f"VRChat Tail Pull ({action_type})"
            }

            response = requests.post(
                OPENSHOCK_API_URL, 
                headers=headers, 
                data=json.dumps(payload),
                timeout=2.0 
            )
            
            if response.status_code == 200:
                self.log_message(f"SUCCESS: {action_type} command sent.")
            else:
                self.log_message(f"ERROR: API returned {response.status_code}")
                
        except Exception:
            self.log_message(f"FAIL SAFE TRIGGERED: Could not send {action_type} command.")

    def on_grabbed_update(self, address, *args):
        if args:
            self.current_grabbed = float(args[0])
            self.evaluate_state()

    def on_stretch_update(self, address, *args):
        if args:
            self.current_stretch = float(args[0])
            self.evaluate_state()

    def evaluate_state(self):
        if self.current_grabbed > 0 and self.current_stretch > 0.1:
            self.trigger_shock()

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
        app.server.shutdown()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()