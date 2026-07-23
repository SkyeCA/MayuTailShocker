import tkinter as tk
from tkinter import simpledialog


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
