import tkinter as tk

import customtkinter as ctk


class DialogWindow(ctk.CTkToplevel):
    """A CTkToplevel kept in front of parent (transient).

    On Windows, CustomTkinter recolours title bars on a theme change by hiding each
    window, then restoring the state it had beforehand. The main window goes first,
    and hiding it also hides its transient windows, so a dialog's "state beforehand"
    reads as withdrawn and it never came back - a modal one (Settings) keeping its
    grab, which locked up the app. These dialogs are never withdrawn on purpose, so
    showing a withdrawn one again before CustomTkinter looks is always right."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.transient(parent)

    def _windows_set_titlebar_color(self, color_mode):
        if self.state() == "withdrawn":
            self.deiconify()
        super()._windows_set_titlebar_color(color_mode)


def center_window(window, parent=None):
    """Moves window to the centre of parent, or of the screen if parent is None.
    Call once the window's contents (and any explicit size) are set up.

    Works in physical pixels throughout: that's what Tk reports, and the position is
    set through Tk directly so CustomTkinter doesn't apply DPI scaling to it."""
    window.update_idletasks()
    min_width, min_height = tk.Wm.wm_minsize(window)
    width = max(window.winfo_width(), window.winfo_reqwidth(), min_width)
    height = max(window.winfo_height(), window.winfo_reqheight(), min_height)

    if parent is None:
        center_x, center_y = window.winfo_screenwidth() / 2, window.winfo_screenheight() / 2
        frame_x = frame_y = 0
    else:
        center_x = parent.winfo_rootx() + parent.winfo_width() / 2
        center_y = parent.winfo_rooty() + parent.winfo_height() / 2
        # A dialog is positioned by its outer frame, but the sizes above are for the
        # area inside its title bar and border, so subtract those. (Not done for the
        # main window at startup: before it's first shown the offset isn't applied.)
        frame_x = window.winfo_rootx() - window.winfo_x()
        frame_y = window.winfo_rooty() - window.winfo_y()

    # Keep the title bar on screen; x isn't clamped since monitors left of the
    # primary one have negative coordinates.
    x = round(center_x - width / 2 - frame_x)
    y = max(round(center_y - height / 2 - frame_y), 0)
    tk.Wm.wm_geometry(window, f"+{x}+{y}")
