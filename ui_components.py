"""Small vector-drawn Tk widgets. No additional UI dependencies."""
import tkinter as tk
from tkinter import font as tkfont

BG = "#0c1220"
PANEL = "#141e30"
BORDER = "#253249"
TEXT = "#edf3ff"
MUTED = "#889bb8"
ACCENT = "#67ddbe"
BLUE = "#7aa5ff"
ORANGE = "#f7b76e"


def rounded(canvas, x0, y0, x1, y1, radius=14, **kw):
    radius = min(radius, (x1 - x0) / 2, (y1 - y0) / 2)
    points = [x0 + radius, y0, x1 - radius, y0, x1, y0, x1, y0 + radius,
              x1, y1 - radius, x1, y1, x1 - radius, y1, x0 + radius, y1,
              x0, y1, x0, y1 - radius, x0, y0 + radius, x0, y0]
    return canvas.create_polygon(points, smooth=True, splinesteps=24, **kw)


class Button(tk.Canvas):
    def __init__(self, master, text, command, primary=False, small=False, **kw):
        self.text, self.command = text, command
        self.primary = primary
        self.hover = False
        self.pressed = False
        self.font = tkfont.Font(family="Segoe UI", size=9 if small else 10, weight="bold" if primary else "normal")
        background = kw.pop("bg", BG)
        super().__init__(master, bg=background, width=self.font.measure(text) + 30,
                         height=34 if small else 40, highlightthickness=0, cursor="hand2", takefocus=True, **kw)
        self.bind("<Configure>", lambda _: self.draw())
        self.bind("<Enter>", lambda _: self.set_hover(True))
        self.bind("<Leave>", lambda _: self.set_hover(False))
        self.bind("<ButtonPress-1>", lambda _: self.press())
        self.bind("<ButtonRelease-1>", self.release)
        self.bind("<Return>", lambda _: self.command())
        self.bind("<space>", lambda _: self.command())
        self.bind("<FocusIn>", lambda _: self.draw())
        self.bind("<FocusOut>", lambda _: self.draw())

    def set_hover(self, value):
        self.hover, self.pressed = value, False
        self.draw()

    def press(self):
        self.focus_set()
        self.pressed = True
        self.draw()

    def release(self, event):
        run = self.pressed and 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        self.pressed = False
        self.draw()
        if run:
            self.command()

    def draw(self):
        self.delete("all")
        fill = "#9aeacf" if self.hover else ACCENT
        if not self.primary:
            fill = "#273650" if self.hover else "#1c2940"
        if self.pressed:
            fill = "#50bda0" if self.primary else "#304362"
        rounded(self, 1, 1, self.winfo_width() - 1, self.winfo_height() - 1, 10,
                fill=fill, outline=BLUE if self.focus_get() is self else (fill if self.primary else BORDER))
        self.create_text(self.winfo_width() / 2, self.winfo_height() / 2,
                         text=self.text, font=self.font, fill=BG if self.primary else TEXT)


class MetricCard(tk.Canvas):
    def __init__(self, master, title, detail, color, symbol):
        super().__init__(master, bg=BG, height=88, width=210, highlightthickness=0)
        self.title, self.detail, self.color, self.symbol = title, detail, color, symbol
        self.value = "—"
        self.bind("<Configure>", lambda _: self.draw())

    def configure(self, cnf=None, **kw):
        if "text" in kw:
            self.value = kw.pop("text")
            self.draw()
        if cnf is not None or kw:
            return super().configure(cnf, **kw)

    config = configure

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        rounded(self, 1, 1, w - 1, h - 1, 14, fill=PANEL, outline=BORDER)
        self.create_text(17, 20, text=self.title, anchor="w", fill=MUTED, font=("Segoe UI", 9))
        rounded(self, w - 43, 13, w - 15, 41, 9, fill="#22314a", outline="")
        if self.symbol == "clock":
            self.create_oval(w - 36, 20, w - 22, 34, outline=self.color, width=1.5)
            self.create_line(w - 29, 22, w - 29, 27, w - 25, 29, fill=self.color, width=1.5)
        else:
            self.create_text(w - 29, 27, text=self.symbol, fill=self.color, font=("Segoe UI", 12, "bold"))
        size = 20 if len(self.value) < 13 else 16
        self.create_text(17, 49, text=self.value, anchor="w", fill=TEXT, font=("Segoe UI", size, "bold"))
        self.create_oval(17, 73, 22, 78, fill=self.color, outline="")
        self.create_text(29, 75, text=self.detail, anchor="w", fill=MUTED, font=("Segoe UI", 8))


class ProgressStrip(tk.Canvas):
    def __init__(self, master):
        super().__init__(master, height=4, width=200, bg=BG, highlightthickness=0)
        self.maximum, self.value = 100, 0
        self.bind("<Configure>", lambda _: self.draw())

    def configure(self, cnf=None, **kw):
        for name in ("maximum", "value"):
            if name in kw:
                setattr(self, name, kw.pop(name))
        if cnf is not None or kw:
            super().configure(cnf, **kw)
        self.draw()

    config = configure

    def draw(self):
        self.delete("all")
        w = self.winfo_width()
        self.create_rectangle(0, 0, w, 4, fill="#23314a", outline="")
        self.create_rectangle(0, 0, w * min(1, self.value / max(1, self.maximum)), 4, fill=ACCENT, outline="")
