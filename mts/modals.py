import tkinter as tk
from tkinter import simpledialog, ttk


class TtkDialog(simpledialog.Dialog):
    """simpledialog.Dialog with a ttk-styled OK/Cancel button box, so the built-in
    buttons match the rest of the ttk-themed app instead of falling back to classic tk."""

    def buttonbox(self):
        box = ttk.Frame(self)

        w = ttk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        w = ttk.Button(box, text="Cancel", width=10, command=self.cancel)
        w.pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

        box.pack()


class APIConfigModal(TtkDialog):
    def __init__(self, parent, title, provider, openshock_api_key, pishock_username, pishock_api_key):
        self.current_provider = provider
        self.current_openshock_api_key = openshock_api_key
        self.current_pishock_username = pishock_username
        self.current_pishock_api_key = pishock_api_key
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Provider:", anchor="w").pack(fill=tk.X, pady=(5, 2))

        self.provider_var = tk.StringVar(value=self.current_provider)
        provider_frame = ttk.Frame(master)
        provider_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Radiobutton(
            provider_frame, text="OpenShock", variable=self.provider_var, value="openshock",
            command=self._update_visible_fields
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            provider_frame, text="PiShock", variable=self.provider_var, value="pishock",
            command=self._update_visible_fields
        ).pack(side=tk.LEFT, padx=(10, 0))

        ttk.Separator(master, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))

        self.openshock_frame = ttk.Frame(master)
        ttk.Label(self.openshock_frame, text="OpenShock API Key:", anchor="w").pack(fill=tk.X, pady=(0, 2))
        self.openshock_key_entry = ttk.Entry(self.openshock_frame, width=55)
        self.openshock_key_entry.insert(0, self.current_openshock_api_key)
        self.openshock_key_entry.pack(fill=tk.X)

        self.pishock_frame = ttk.Frame(master)
        ttk.Label(self.pishock_frame, text="PiShock Username:", anchor="w").pack(fill=tk.X, pady=(0, 2))
        self.pishock_username_entry = ttk.Entry(self.pishock_frame, width=55)
        self.pishock_username_entry.insert(0, self.current_pishock_username)
        self.pishock_username_entry.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(self.pishock_frame, text="PiShock API Key:", anchor="w").pack(fill=tk.X, pady=(0, 2))
        self.pishock_key_entry = ttk.Entry(self.pishock_frame, width=55)
        self.pishock_key_entry.insert(0, self.current_pishock_api_key)
        self.pishock_key_entry.pack(fill=tk.X)

        self._update_visible_fields()

        return self.openshock_key_entry if self.current_provider == "openshock" else self.pishock_username_entry

    def _update_visible_fields(self):
        if self.provider_var.get() == "pishock":
            self.openshock_frame.pack_forget()
            self.pishock_frame.pack(fill=tk.X, pady=(0, 10))
        else:
            self.pishock_frame.pack_forget()
            self.openshock_frame.pack(fill=tk.X, pady=(0, 10))

    def apply(self):
        self.result = {
            "provider": self.provider_var.get(),
            "openshock_api_key": self.openshock_key_entry.get().strip(),
            "pishock_username": self.pishock_username_entry.get().strip(),
            "pishock_api_key": self.pishock_key_entry.get().strip(),
        }


class OSCConfigModal(TtkDialog):
    def __init__(self, parent, title, param_grabbed, param_stretch):
        self.param_grabbed = param_grabbed
        self.param_stretch = param_stretch
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="VRChat Grab Parameter (Boolean):", anchor="w").pack(fill=tk.X, pady=(5, 2))
        self.grab_entry = ttk.Entry(master, width=55)
        self.grab_entry.insert(0, self.param_grabbed)
        self.grab_entry.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(master, text="VRChat Stretch Parameter (Float):", anchor="w").pack(fill=tk.X, pady=(5, 2))
        self.stretch_entry = ttk.Entry(master, width=55)
        self.stretch_entry.insert(0, self.param_stretch)
        self.stretch_entry.pack(fill=tk.X, pady=(0, 5))

        return self.grab_entry

    def apply(self):
        self.result = {
            "param_grabbed": self.grab_entry.get().strip(),
            "param_stretch": self.stretch_entry.get().strip()
        }


class ShockerConfigModal(TtkDialog):
    def __init__(self, parent, title, current_ids, current_mode, id_label="Shocker ID"):
        self.current_ids = list(current_ids)
        self.current_mode = current_mode
        self.id_label = id_label
        self.result = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Shocker Mode:", anchor="w").pack(fill=tk.X, pady=(5, 2))

        self.mode_var = tk.StringVar(value=self.current_mode)
        self.radio_all = ttk.Radiobutton(master, text="Trigger All Shockers", variable=self.mode_var, value="All")
        self.radio_all.pack(anchor="w")

        self.radio_random = ttk.Radiobutton(master, text="Trigger Random Shocker", variable=self.mode_var, value="Random")
        self.radio_random.pack(anchor="w")

        ttk.Separator(master, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        ttk.Label(master, text=f"{self.id_label}s:", anchor="w").pack(fill=tk.X, pady=(5, 2))

        list_frame = ttk.Frame(master)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(list_frame, height=6)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for sid in self.current_ids:
            self.listbox.insert(tk.END, sid)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        scrollbar.config(command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)

        ctrl_frame = ttk.Frame(master)
        ctrl_frame.pack(fill=tk.X, pady=(5, 10))

        self.new_id_entry = ttk.Entry(ctrl_frame)
        self.new_id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        ttk.Button(ctrl_frame, text="Add", command=self.add_id).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(ctrl_frame, text="Remove Selected", command=self.remove_id).pack(side=tk.LEFT)

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
