import tkinter as tk


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
