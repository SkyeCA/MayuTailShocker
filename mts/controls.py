import math
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFilter, ImageTk

from .theme import MUTED_TEXT, body_font


def _snap(value, from_, to, step, integer):
    value = min(max(value, from_), to)
    value = round(round(value / step) * step, 6)
    return int(value) if integer else value


class Dial(ctk.CTkFrame):
    """A rounded radial control: a 270 degree arc with a draggable knob and the value
    in the middle. Also responds to the mouse wheel and arrow keys for exact steps.

    Tk's canvas doesn't anti-alias on Windows, so the dial is drawn with Pillow at
    SUPERSAMPLE x size and scaled down."""

    START = 135  # degrees clockwise from 3 o'clock, i.e. bottom-left
    SWEEP = 270
    SUPERSAMPLE = 4

    # Pillow needs hex colours; (light, dark) pairs like the rest of the theme.
    TRACK = ("#bcc0c4", "#3d3f41")
    PROGRESS = ("#3b8ed0", "#1f6aa5")
    PROGRESS_DISABLED = ("#a6a6a6", "#5e6063")
    KNOB = ("#ffffff", "#e6e6e6")
    KNOB_OUTLINE = ("#a8a8a8", "#55585b")

    def __init__(self, master, caption, from_, to, step, value_fmt, command, size=124):
        super().__init__(master, fg_color="transparent")
        self._from, self._to, self._step = from_, to, step
        self._integer = all(isinstance(v, int) for v in (from_, to, step))
        self._value_fmt = value_fmt
        self._command = command
        self._size = size
        self._value = from_
        self._enabled = True
        self._font_family = ctk.CTkFont().cget("family")

        self._dial_canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, takefocus=1, cursor="hand2")
        self._dial_canvas.pack()
        self._caption = ctk.CTkLabel(self, text=caption, font=body_font(), text_color=MUTED_TEXT)
        self._caption.pack()

        self._dial_canvas.bind("<Button-1>", self._on_press)
        self._dial_canvas.bind("<B1-Motion>", self._on_drag)
        self._dial_canvas.bind("<MouseWheel>", self._on_wheel)
        self._dial_canvas.bind("<Button-4>", lambda e: self._nudge(1))  # X11 wheel
        self._dial_canvas.bind("<Button-5>", lambda e: self._nudge(-1))
        for key, direction in (("<Up>", 1), ("<Right>", 1), ("<Down>", -1), ("<Left>", -1)):
            self._dial_canvas.bind(key, lambda e, d=direction: self._nudge(d))

        self._ready = True
        self._render()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set(self, value):
        # Show the value exactly, not snapped to step: the avatar menu can set values
        # between steps (e.g. a 3.3 s cooldown), and the dial must match what's in effect.
        self._value = min(max(value, self._from), self._to)
        self._render()

    def get(self):
        return self._value

    def set_enabled(self, enabled):
        self._enabled = enabled
        self._dial_canvas.configure(cursor="hand2" if enabled else "arrow", takefocus=1 if enabled else 0)
        self._render()

    # ------------------------------------------------------------------
    # CustomTkinter hooks: redraw for theme and DPI changes
    # ------------------------------------------------------------------
    def _set_appearance_mode(self, mode_string):
        super()._set_appearance_mode(mode_string)
        self._render()

    def _set_scaling(self, new_widget_scaling, new_window_scaling):
        super()._set_scaling(new_widget_scaling, new_window_scaling)
        self._render()

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------
    def _fraction(self):
        return (self._value - self._from) / (self._to - self._from)

    def _set_from_user(self, value):
        value = _snap(value, self._from, self._to, self._step, self._integer)
        if value != self._value:
            self._value = value
            self._render()
            self._command(value)

    def _on_press(self, event):
        if self._enabled:
            self._dial_canvas.focus_set()
            self._point_at(event, is_drag=False)

    def _on_drag(self, event):
        self._point_at(event, is_drag=True)

    def _point_at(self, event, is_drag):
        if not self._enabled:
            return
        center = int(self._dial_canvas.cget("width")) / 2
        dx, dy = event.x - center, event.y - center
        if math.hypot(dx, dy) < center * 0.2:
            return  # too close to the middle to tell which way the user means
        angle = (math.degrees(math.atan2(dy, dx)) - self.START) % 360
        if angle > self.SWEEP:
            # In the gap at the bottom: stick to whichever end the knob is nearer,
            # rather than jumping between min and max.
            angle = self.SWEEP if self._fraction() > 0.5 else 0
        value = self._from + angle / self.SWEEP * (self._to - self._from)
        # A drag that carries on past one end, through the gap, comes out at the other
        # end - e.g. 1% straight to 100%. A real drag never moves that far in one step,
        # so hold the value until the pointer comes back round.
        if is_drag and abs(value - self._value) > (self._to - self._from) / 2:
            return
        self._set_from_user(value)

    def _on_wheel(self, event):
        if event.delta:
            self._nudge(1 if event.delta > 0 else -1)

    def _nudge(self, direction):
        if self._enabled:
            self._set_from_user(self._value + direction * self._step)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def _point(self, center, radius, angle):
        rad = math.radians(angle)
        return center + radius * math.cos(rad), center + radius * math.sin(rad)

    def _arc(self, draw, center, radius, stroke, start, end, color):
        box = [center - radius - stroke / 2, center - radius - stroke / 2,
               center + radius + stroke / 2, center + radius + stroke / 2]
        draw.arc(box, start, end, fill=color, width=round(stroke))
        for angle in (start, end):  # round caps
            x, y = self._point(center, radius, angle)
            draw.ellipse([x - stroke / 2, y - stroke / 2, x + stroke / 2, y + stroke / 2], fill=color)

    def _render(self):
        if not getattr(self, "_ready", False):
            return
        mode = self._apply_appearance_mode
        size = round(self._apply_widget_scaling(self._size))
        big = size * self.SUPERSAMPLE
        center = big / 2
        stroke = big * 0.13
        knob_radius = stroke * 0.8
        radius = center - knob_radius - big * 0.03

        image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        self._arc(draw, center, radius, stroke, self.START, self.START + self.SWEEP, mode(self.TRACK))

        knob_angle = self.START + self.SWEEP * self._fraction()
        if self._fraction() > 0:
            progress = self.PROGRESS if self._enabled else self.PROGRESS_DISABLED
            self._arc(draw, center, radius, stroke, self.START, knob_angle, mode(progress))

        kx, ky = self._point(center, radius, knob_angle)
        shadow = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        offset = big * 0.012
        ImageDraw.Draw(shadow).ellipse(
            [kx - knob_radius, ky - knob_radius + offset, kx + knob_radius, ky + knob_radius + offset], fill=(0, 0, 0, 90),
        )
        image = Image.alpha_composite(image, shadow.filter(ImageFilter.GaussianBlur(big * 0.015)))
        ImageDraw.Draw(image).ellipse(
            [kx - knob_radius, ky - knob_radius, kx + knob_radius, ky + knob_radius],
            fill=mode(self.KNOB), outline=mode(self.KNOB_OUTLINE), width=round(big * 0.01),
        )

        self._photo = ImageTk.PhotoImage(image.resize((size, size), Image.LANCZOS))
        text_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"] if self._enabled else MUTED_TEXT
        # Negative size = pixels, so it scales with the dial rather than the system font size.
        value_font = (self._font_family, -round(self._apply_widget_scaling(self._size * 0.16)), "bold")
        # The open bottom of the arc is empty space; stop just below the lowest the knob can sit.
        lowest = center + radius * math.sin(math.radians(self.START)) + knob_radius + big * 0.05
        canvas = self._dial_canvas
        canvas.configure(width=size, height=math.ceil(lowest / self.SUPERSAMPLE), bg=mode(self._bg_color))
        canvas.delete("all")
        canvas.create_image(0, 0, image=self._photo, anchor="nw")
        canvas.create_text(size / 2, size / 2, text=self._value_fmt.format(self._value), fill=mode(text_color), font=value_font)
