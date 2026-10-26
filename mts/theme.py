import webbrowser

import customtkinter as ctk

# Colours are (light mode, dark mode) pairs, as CustomTkinter expects.
SUCCESS = ("#2e9e5b", "#2fa866")
WARNING = ("#c97a1e", "#e39b3a")
DANGER = ("#c0392b", "#d64545")
DANGER_HOVER = ("#a93226", "#b83b3b")
MUTED_TEXT = ("gray40", "gray60")
ACCENT_TEXT = ("#1f6aa5", "#5aa9e6")  # the theme's blue, readable as text
LINK = ACCENT_TEXT
BANNER = ("#fbeedd", "#3a2c1a")
SWITCH_KNOB = ("gray98", "#D5D9DE")
SWITCH_KNOB_HOVER = ("gray88", "gray100")

# The stock light-mode segmented button puts white text on light grey; darken the
# unselected segments so they stay readable.
SEGMENTED = dict(
    fg_color=("gray45", "#4A4D50"),
    unselected_color=("gray45", "#4A4D50"),
    unselected_hover_color=("gray38", "#696969"),
)


# Fonts can only be created once the root window exists, hence functions.
def title_font(size=20):
    return ctk.CTkFont(size=size, weight="bold")


def heading_font(size=13):
    return ctk.CTkFont(size=size, weight="bold")


def body_font(size=13):
    return ctk.CTkFont(size=size)


def mono_font(size=12):
    return ctk.CTkFont(family="Consolas", size=size)


def link_label(parent, text, url, size=13):
    """Underlined text that opens url in the browser - reads as a web link, unlike a button."""
    label = ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=size, underline=True), text_color=LINK, cursor="hand2")
    label.bind("<Button-1>", lambda e: webbrowser.open(url))
    return label
