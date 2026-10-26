from tkinter import messagebox

import customtkinter as ctk

from .config import APPEARANCE_MODES
from .constants import DEFAULT_PARAM_GRABBED, DEFAULT_PARAM_STRETCH, OPENSHOCK_API_TOKENS_URL
from .theme import MUTED_TEXT, SEGMENTED, body_font, heading_font, link_label, title_font
from .windowing import center_window

MODE_LABELS = {"All": "All shockers", "Random": "One at random"}
PAGES = ("OpenShock", "Shockers", "OSC", "Appearance")


class SettingsWindow(ctk.CTkToplevel):
    """One window for everything in config.json, with a category sidebar on the left
    and the selected category's options on the right. Only sections that actually
    changed are handed to the engine, so e.g. the OSC listener restarts only when
    needed."""

    def __init__(self, parent, engine, on_saved=None):
        super().__init__(parent)
        self.engine = engine
        self.on_saved = on_saved
        config = engine.config
        self.shocker_ids = list(config.shocker_ids)
        self._original_appearance = config.appearance_mode

        self.title("Settings")
        self.geometry("640x460")
        self.minsize(580, 440)
        self.transient(parent)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        builders = {
            "OpenShock": self._build_openshock_page,
            "Shockers": self._build_shockers_page,
            "OSC": self._build_osc_page,
            "Appearance": self._build_appearance_page,
        }
        self.pages = {}
        for name in PAGES:
            page = ctk.CTkFrame(self, fg_color="transparent")
            ctk.CTkLabel(page, text=name, font=title_font(18), anchor="w").pack(fill="x", pady=(0, 4))
            builders[name](page, config)
            self.pages[name] = page

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=1, column=1, sticky="ew", padx=20, pady=16)
        ctk.CTkButton(buttons, text="Save", width=100, command=self.save).pack(side="right")
        ctk.CTkButton(
            buttons, text="Cancel", width=100, fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"), command=self.cancel,
        ).pack(side="right", padx=(0, 8))

        if not config.api_key:
            self.show_page("OpenShock")
        elif not config.shocker_ids:
            self.show_page("Shockers")
        else:
            self.show_page(PAGES[0])

        center_window(self, parent)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda e: self.cancel())
        # grab_set fails if the window isn't viewable yet.
        self.after(100, self._make_modal)

    def _make_modal(self):
        try:
            self.grab_set()
        except Exception:
            pass
        self.lift()
        self.focus_force()

    def _field_label(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=heading_font(), anchor="w").pack(fill="x", pady=(8, 2))

    def _hint(self, parent, text):
        ctk.CTkLabel(
            parent, text=text, font=body_font(12), text_color=MUTED_TEXT,
            anchor="w", justify="left", wraplength=400,
        ).pack(fill="x", pady=(2, 0))

    # ------------------------------------------------------------------
    # Sidebar navigation
    # ------------------------------------------------------------------
    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=160, corner_radius=0)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsw")
        sidebar.grid_propagate(False)

        self.nav_buttons = {}
        for name in PAGES:
            button = ctk.CTkButton(
                sidebar, text=name, anchor="w", height=34, font=body_font(14),
                hover_color=("gray78", "gray28"), command=lambda n=name: self.show_page(n),
            )
            button.pack(fill="x", padx=10, pady=(12 if not self.nav_buttons else 2, 0))
            self.nav_buttons[name] = button

    def show_page(self, name):
        theme = ctk.ThemeManager.theme["CTkButton"]
        for page_name, page in self.pages.items():
            button = self.nav_buttons[page_name]
            if page_name == name:
                page.grid(row=0, column=1, sticky="nsew", padx=20, pady=(16, 0))
                button.configure(fg_color=theme["fg_color"], text_color=theme["text_color"])
            else:
                page.grid_remove()
                button.configure(fg_color="transparent", text_color=("gray10", "gray90"))

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------
    def _build_openshock_page(self, page, config):
        self._field_label(page, "API token")
        row = ctk.CTkFrame(page, fg_color="transparent")
        row.pack(fill="x")
        self.api_key_entry = ctk.CTkEntry(row, show="•")
        self.api_key_entry.insert(0, config.api_key)
        self.api_key_entry.pack(side="left", fill="x", expand=True)
        self.show_key_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            row, text="Show", width=60, variable=self.show_key_var,
            command=lambda: self.api_key_entry.configure(show="" if self.show_key_var.get() else "•"),
        ).pack(side="left", padx=(8, 0))
        hint = ctk.CTkFrame(page, fg_color="transparent")
        hint.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(
            hint, text="Create a token in the OpenShock dashboard under ", font=body_font(12), text_color=MUTED_TEXT,
        ).pack(side="left")
        link_label(hint, "API Tokens", OPENSHOCK_API_TOKENS_URL, size=12).pack(side="left")
        ctk.CTkLabel(hint, text=".", font=body_font(12), text_color=MUTED_TEXT).pack(side="left")

    def _build_shockers_page(self, page, config):
        self._field_label(page, "When the tail is pulled, trigger")
        self.mode_button = ctk.CTkSegmentedButton(page, values=list(MODE_LABELS.values()), **SEGMENTED)
        self.mode_button.set(MODE_LABELS.get(config.shocker_mode, MODE_LABELS["All"]))
        self.mode_button.pack(fill="x")

        self._field_label(page, "Shocker IDs")
        self.id_list = ctk.CTkScrollableFrame(page, height=110)
        self.id_list.pack(fill="both", expand=True)

        add_row = ctk.CTkFrame(page, fg_color="transparent")
        add_row.pack(fill="x", pady=(8, 0))
        self.new_id_entry = ctk.CTkEntry(add_row, placeholder_text="Paste a shocker ID")
        self.new_id_entry.pack(side="left", fill="x", expand=True)
        self.new_id_entry.bind("<Return>", lambda e: self.add_id())
        ctk.CTkButton(add_row, text="Add", width=70, command=self.add_id).pack(side="left", padx=(8, 0))

        self._render_ids()

    def _build_osc_page(self, page, config):
        self._field_label(page, "Grab parameter (bool)")
        self.grab_entry = ctk.CTkEntry(page)
        self.grab_entry.insert(0, config.param_grabbed)
        self.grab_entry.pack(fill="x")

        self._field_label(page, "Stretch parameter (float)")
        self.stretch_entry = ctk.CTkEntry(page)
        self.stretch_entry.insert(0, config.param_stretch)
        self.stretch_entry.pack(fill="x")

        self._hint(page, "The OSC addresses of your tail PhysBone's _IsGrabbed and _Stretch.")
        ctk.CTkButton(
            page, text="Reset to defaults", width=140, fg_color="transparent", border_width=1,
            text_color=("gray10", "gray90"), command=self._reset_osc_params,
        ).pack(anchor="e", pady=(12, 0))

    def _build_appearance_page(self, page, config):
        self._field_label(page, "Theme")
        self.appearance_button = ctk.CTkSegmentedButton(
            page, values=list(APPEARANCE_MODES), command=ctk.set_appearance_mode, **SEGMENTED,
        )
        self.appearance_button.set(config.appearance_mode)
        self.appearance_button.pack(fill="x")

    # ------------------------------------------------------------------
    # Shocker ID list
    # ------------------------------------------------------------------
    def _render_ids(self):
        for child in self.id_list.winfo_children():
            child.destroy()

        if not self.shocker_ids:
            ctk.CTkLabel(self.id_list, text="No shockers added yet.", text_color=MUTED_TEXT).pack(pady=8)

        for sid in self.shocker_ids:
            row = ctk.CTkFrame(self.id_list, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=sid, anchor="w", font=body_font(12)).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(
                row, text="Remove", width=70, height=24, fg_color="transparent", border_width=1,
                text_color=("gray10", "gray90"), command=lambda s=sid: self.remove_id(s),
            ).pack(side="right")

        # Choosing between shockers only makes sense with more than one.
        if len(self.shocker_ids) <= 1:
            self.mode_button.set(MODE_LABELS["All"])
            self.mode_button.configure(state="disabled")
        else:
            self.mode_button.configure(state="normal")

    def add_id(self):
        new_id = self.new_id_entry.get().strip()
        if new_id and new_id not in self.shocker_ids:
            self.shocker_ids.append(new_id)
            self.new_id_entry.delete(0, "end")
            self._render_ids()

    def remove_id(self, sid):
        self.shocker_ids.remove(sid)
        self._render_ids()

    def _reset_osc_params(self):
        if not messagebox.askyesno(
            "Reset to defaults",
            "Replace both OSC parameters with the defaults? Nothing changes until you press Save.",
            parent=self,
        ):
            return
        for entry, value in ((self.grab_entry, DEFAULT_PARAM_GRABBED), (self.stretch_entry, DEFAULT_PARAM_STRETCH)):
            entry.delete(0, "end")
            entry.insert(0, value)

    # ------------------------------------------------------------------
    # Save / cancel
    # ------------------------------------------------------------------
    def cancel(self):
        # Undo the live theme preview.
        ctk.set_appearance_mode(self._original_appearance)
        self.destroy()

    def save(self):
        config = self.engine.config
        api_key = self.api_key_entry.get().strip()
        mode = next(key for key, label in MODE_LABELS.items() if label == self.mode_button.get())
        param_grabbed = self.grab_entry.get().strip() or DEFAULT_PARAM_GRABBED
        param_stretch = self.stretch_entry.get().strip() or DEFAULT_PARAM_STRETCH
        appearance = self.appearance_button.get()

        try:
            if api_key != config.api_key:
                self.engine.set_api_key(api_key)
            if self.shocker_ids != config.shocker_ids or mode != config.shocker_mode:
                self.engine.set_shockers(list(self.shocker_ids), mode)
            if (param_grabbed, param_stretch) != (config.param_grabbed, config.param_stretch):
                self.engine.set_osc_params(param_grabbed, param_stretch)
            if appearance != config.appearance_mode:
                config.appearance_mode = appearance
                config.save()
        except Exception as e:
            messagebox.showerror("Error", f"Could not write configuration file:\n{e}", parent=self)
            return

        if self.on_saved:
            self.on_saved()
        self.destroy()
