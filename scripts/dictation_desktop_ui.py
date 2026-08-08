"""Небольшие desktop-окна диктовки: микрофонный HUD и настройки звука."""

from __future__ import annotations

import logging
import platform
import queue
import threading
from typing import Callable, Optional


TRANSPARENT_BG = "#010203"
PANEL_BG = "#171b23"
PANEL_BORDER = "#303746"
TEXT = "#f5f7fb"
MUTED_TEXT = "#9aa4b5"
ACCENT = "#4c8dff"


def active_input_device_name() -> str:
    """Имя фактического дефолтного входа, который откроет sounddevice."""
    try:
        import sounddevice as sd

        device = sd.query_devices(kind="input")
        name = str(device.get("name") or "").strip()
        return name or "Системный микрофон"
    except Exception as exc:
        logging.debug(f"input device name unavailable: {exc}")
        return "Системный микрофон"


def _shorten(text: str, limit: int = 45) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


class DictationDesktopUi:
    """Один Tk-thread для всех окон, вызываемых из hotkey/tray threads."""

    def __init__(self) -> None:
        self._commands: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._ready = threading.Event()
        self._stopped = threading.Event()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="dictation-desktop-ui"
        )
        self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def start(self) -> None:
        self._thread.start()
        self._ready.wait(timeout=2.0)

    def stop(self) -> None:
        self._commands.put(("quit", None))
        self._stopped.wait(timeout=1.0)

    def show_microphone(self, device_name: str, duration_ms: int = 650) -> None:
        self._commands.put(
            ("show_microphone", (_shorten(device_name), max(350, int(duration_ms))))
        )

    def open_audio_settings(
        self,
        enabled: bool,
        reduction_percent: int,
        on_save: Callable[[bool, int], None],
    ) -> None:
        self._commands.put(
            ("audio_settings", (bool(enabled), int(reduction_percent), on_save))
        )

    def _run(self) -> None:
        try:
            import tkinter as tk
            from tkinter import ttk

            self._tk_module = tk
            self._ttk = ttk
            self._tk = tk.Tk()
            self._tk.withdraw()
            self._build_overlay()
            self._settings_window = None
            self._close_settings = None
            self._available = True
            self._ready.set()
            self._tk.after(20, self._poll_commands)
            self._tk.mainloop()
        except Exception as exc:
            logging.error(f"dictation desktop UI unavailable: {exc}", exc_info=True)
            self._ready.set()
        finally:
            self._available = False
            self._stopped.set()

    def _poll_commands(self) -> None:
        try:
            while True:
                command, payload = self._commands.get_nowait()
                if command == "quit":
                    if self._close_settings is not None:
                        self._close_settings()
                    self._tk.quit()
                    return
                if command == "show_microphone":
                    name, duration_ms = payload  # type: ignore[misc]
                    self._show_microphone(name, duration_ms)
                elif command == "audio_settings":
                    enabled, percent, callback = payload  # type: ignore[misc]
                    self._open_audio_settings(enabled, percent, callback)
        except queue.Empty:
            pass
        self._tk.after(20, self._poll_commands)

    def _build_overlay(self) -> None:
        tk = self._tk_module
        width, height = 420, 112
        self._overlay_size = (width, height)
        self._overlay_generation = 0
        self._overlay = tk.Toplevel(self._tk)
        self._overlay.overrideredirect(True)
        self._overlay.attributes("-topmost", True)
        try:
            self._overlay.attributes("-transparentcolor", TRANSPARENT_BG)
        except Exception:
            pass
        try:
            self._overlay.attributes("-disabled", True)
        except Exception:
            pass
        self._overlay.geometry(f"{width}x{height}+0+0")
        self._overlay.withdraw()
        self._overlay_canvas = tk.Canvas(
            self._overlay,
            width=width,
            height=height,
            bg=TRANSPARENT_BG,
            bd=0,
            highlightthickness=0,
        )
        self._overlay_canvas.pack()

    def _show_microphone(self, device_name: str, duration_ms: int) -> None:
        self._overlay_generation += 1
        generation = self._overlay_generation
        width, height = self._overlay_size
        work_area = self._active_monitor_work_area()
        if work_area is None:
            left, top = 0, 0
            right = self._tk.winfo_screenwidth()
            bottom = self._tk.winfo_screenheight()
        else:
            left, top, right, bottom = work_area
        x = int(left + (right - left - width) / 2)
        y = int(top + (bottom - top - height) / 2)

        self._draw_microphone_card(device_name)
        self._overlay.geometry(f"{width}x{height}+{x}+{y}")
        self._overlay.attributes("-alpha", 0.98)
        self._overlay.deiconify()
        self._overlay.lift()
        if platform.system() == "Windows":
            self._make_click_through(self._overlay)

        fade_ms = min(180, max(100, duration_ms // 3))
        hold_ms = max(150, duration_ms - fade_ms)
        self._tk.after(hold_ms, lambda: self._fade_overlay(generation, 0, fade_ms))

    def _fade_overlay(self, generation: int, step: int, fade_ms: int) -> None:
        if generation != self._overlay_generation:
            return
        steps = 7
        if step >= steps:
            self._overlay.withdraw()
            return
        self._overlay.attributes("-alpha", 0.98 * (1.0 - (step + 1) / steps))
        self._tk.after(
            max(15, fade_ms // steps),
            lambda: self._fade_overlay(generation, step + 1, fade_ms),
        )

    def _draw_microphone_card(self, device_name: str) -> None:
        canvas = self._overlay_canvas
        canvas.delete("all")
        self._rounded_rect(canvas, 5, 5, 415, 107, 24, PANEL_BG, PANEL_BORDER)

        # Accent circle and a compact microphone glyph.
        canvas.create_oval(26, 24, 90, 88, fill="#182b49", outline="")
        if "h1" in device_name.lower():
            # Узнаваемый силуэт портативного H1: X/Y-капсюли, экран и корпус.
            canvas.create_line(
                53, 43, 45, 31, fill=ACCENT, width=6, capstyle="round"
            )
            canvas.create_line(
                63, 43, 71, 31, fill=ACCENT, width=6, capstyle="round"
            )
            self._rounded_rect(canvas, 47, 40, 69, 75, 6, ACCENT, "")
            canvas.create_rectangle(51, 47, 65, 58, fill="#0f1726", outline="")
            canvas.create_oval(56, 63, 60, 67, fill="#ffffff", outline="")
        else:
            canvas.create_arc(
                46, 39, 70, 69, start=180, extent=180,
                style="arc", outline=ACCENT, width=3,
            )
            canvas.create_rectangle(51, 34, 65, 62, fill=ACCENT, outline="")
            canvas.create_oval(51, 28, 65, 42, fill=ACCENT, outline="")
            canvas.create_oval(51, 54, 65, 68, fill=ACCENT, outline="")
            canvas.create_line(58, 69, 58, 77, fill=ACCENT, width=3)
            canvas.create_line(50, 77, 66, 77, fill=ACCENT, width=3)

        canvas.create_text(
            112, 39, text="АКТИВНЫЙ МИКРОФОН", anchor="w",
            fill=MUTED_TEXT, font=("Segoe UI Semibold", 9),
        )
        canvas.create_text(
            112, 67, text=device_name, anchor="w",
            fill=TEXT, font=("Segoe UI Semibold", 16),
        )

    @staticmethod
    def _rounded_rect(canvas, x1, y1, x2, y2, radius, fill, outline) -> None:
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        canvas.create_polygon(points, smooth=True, splinesteps=24, fill=fill, outline=outline)

    @staticmethod
    def _make_click_through(window) -> None:
        try:
            import ctypes

            hwnd = window.winfo_id()
            get_style = ctypes.windll.user32.GetWindowLongW
            set_style = ctypes.windll.user32.SetWindowLongW
            ex_style = get_style(hwnd, -20)
            set_style(hwnd, -20, ex_style | 0x20 | 0x80 | 0x08000000)
        except Exception as exc:
            logging.debug(f"overlay click-through unavailable: {exc}")

    @staticmethod
    def _active_monitor_work_area() -> Optional[tuple[int, int, int, int]]:
        """Рабочая область монитора с активным окном, не обязательно основного."""
        if platform.system() != "Windows":
            return None
        try:
            import ctypes
            from ctypes import wintypes

            class Rect(ctypes.Structure):
                _fields_ = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            class MonitorInfo(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", Rect),
                    ("rcWork", Rect),
                    ("dwFlags", wintypes.DWORD),
                ]

            user32 = ctypes.windll.user32
            foreground = user32.GetForegroundWindow()
            monitor = user32.MonitorFromWindow(foreground, 2)
            info = MonitorInfo()
            info.cbSize = ctypes.sizeof(MonitorInfo)
            if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                return None
            work = info.rcWork
            return int(work.left), int(work.top), int(work.right), int(work.bottom)
        except Exception as exc:
            logging.debug(f"active monitor lookup fallback: {exc}")
            return None

    def _open_audio_settings(
        self,
        enabled: bool,
        reduction_percent: int,
        on_save: Callable[[bool, int], None],
    ) -> None:
        tk = self._tk_module
        try:
            if self._settings_window is not None and self._settings_window.winfo_exists():
                self._settings_window.lift()
                self._settings_window.focus_force()
                return
        except Exception:
            pass

        window = tk.Toplevel(self._tk)
        self._settings_window = window
        window.overrideredirect(True)
        window.configure(bg=PANEL_BORDER)
        window.resizable(False, False)
        window.attributes("-topmost", True)
        width, height = 392, 146
        x, y = self._flyout_position(width, height)
        window.geometry(f"{width}x{height}+{x}+{y}")
        panel = tk.Frame(window, bg=PANEL_BG)
        panel.place(x=1, y=1, width=width - 2, height=height - 2)

        enabled_var = tk.BooleanVar(value=enabled)
        percent_var = tk.DoubleVar(value=max(0, min(90, reduction_percent)))
        tk.Label(
            panel,
            text="Приглушать во время записи",
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 11),
            anchor="w",
        ).place(x=18, y=14)
        tk.Label(
            panel,
            text="Музыку, браузер и звонки",
            bg=PANEL_BG,
            fg=MUTED_TEXT,
            font=("Segoe UI", 9),
            anchor="w",
        ).place(x=18, y=39)

        toggle = tk.Canvas(
            panel,
            width=44,
            height=24,
            bg=PANEL_BG,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        toggle.place(x=330, y=18)

        panel_line = tk.Frame(panel, bg="#303746")
        panel_line.place(x=18, y=68, width=354, height=1)

        level_label = tk.Label(
            panel,
            text="Приглушение",
            bg=PANEL_BG,
            fg=TEXT,
            font=("Segoe UI", 10),
            anchor="w",
        )
        level_label.place(x=18, y=78)
        value_label = tk.Label(
            panel,
            text=f"{int(percent_var.get())}%",
            bg=PANEL_BG,
            fg=ACCENT,
            font=("Segoe UI Semibold", 11),
            anchor="e",
        )
        value_label.place(x=320, y=78, width=52)

        slider = tk.Canvas(
            panel,
            width=354,
            height=28,
            bg=PANEL_BG,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
        )
        slider.place(x=18, y=101)
        save_job = None
        last_saved = (bool(enabled), int(round(percent_var.get())))
        closing = False

        def current_value() -> tuple[bool, int]:
            return enabled_var.get(), int(round(percent_var.get()))

        def persist() -> None:
            nonlocal save_job, last_saved
            save_job = None
            value = current_value()
            if value == last_saved:
                return
            on_save(*value)
            last_saved = value

        def schedule_save(delay_ms: int = 160) -> None:
            nonlocal save_job
            if save_job is not None:
                window.after_cancel(save_job)
            save_job = window.after(delay_ms, persist)

        def redraw_toggle() -> None:
            from PIL import Image, ImageDraw, ImageTk

            toggle.delete("all")
            is_enabled = enabled_var.get()
            track = ACCENT if is_enabled else "#4a5260"
            knob_x = 31 if is_enabled else 13
            scale = 4
            image = Image.new("RGB", (44 * scale, 24 * scale), PANEL_BG)
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle(
                (scale, scale, 43 * scale, 23 * scale),
                radius=11 * scale,
                fill=track,
            )
            draw.ellipse(
                (
                    (knob_x - 8) * scale,
                    4 * scale,
                    (knob_x + 8) * scale,
                    20 * scale,
                ),
                fill="#ffffff",
            )
            resample = getattr(Image, "Resampling", Image).LANCZOS
            image = image.resize((44, 24), resample)
            photo = ImageTk.PhotoImage(image)
            toggle.create_image(0, 0, anchor="nw", image=photo)
            toggle._rendered_image = photo

        def redraw_slider() -> None:
            from PIL import Image, ImageDraw, ImageTk

            slider.delete("all")
            percent = int(round(percent_var.get()))
            is_enabled = enabled_var.get()
            x1, x2, y = 8, 346, 14
            thumb_x = x1 + (x2 - x1) * percent / 90
            scale = 4
            image = Image.new("RGB", (354 * scale, 28 * scale), PANEL_BG)
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle(
                (x1 * scale, 12 * scale, x2 * scale, 16 * scale),
                radius=2 * scale,
                fill="#424a58" if is_enabled else "#343a45",
            )
            if is_enabled and thumb_x > x1:
                draw.rounded_rectangle(
                    (x1 * scale, 12 * scale, int(thumb_x * scale), 16 * scale),
                    radius=2 * scale,
                    fill=ACCENT,
                )
            draw.ellipse(
                (
                    int((thumb_x - 7) * scale),
                    (y - 7) * scale,
                    int((thumb_x + 7) * scale),
                    (y + 7) * scale,
                ),
                fill="#ffffff" if is_enabled else "#697384",
                outline=ACCENT if is_enabled else "#697384",
                width=2 * scale,
            )
            resample = getattr(Image, "Resampling", Image).LANCZOS
            image = image.resize((354, 28), resample)
            photo = ImageTk.PhotoImage(image)
            slider.create_image(0, 0, anchor="nw", image=photo)
            slider._rendered_image = photo

        def update_controls() -> None:
            percent = int(round(percent_var.get()))
            value_label.configure(text=f"{percent}%")
            is_enabled = enabled_var.get()
            slider.configure(cursor="hand2" if is_enabled else "arrow")
            level_fg = TEXT if is_enabled else "#697384"
            level_label.configure(fg=level_fg)
            value_label.configure(fg=ACCENT if is_enabled else "#697384")
            redraw_toggle()
            redraw_slider()

        def toggle_enabled(_event=None) -> None:
            enabled_var.set(not enabled_var.get())
            update_controls()
            schedule_save(0)

        def set_percent_from_x(x: int) -> None:
            if not enabled_var.get():
                return
            percent = round(max(0, min(1, (x - 8) / 338)) * 90)
            percent_var.set(percent)
            update_controls()
            schedule_save()

        def slider_changed(event) -> None:
            slider.focus_set()
            set_percent_from_x(event.x)

        def nudge_slider(delta: int):
            def handler(_event):
                if enabled_var.get():
                    percent_var.set(max(0, min(90, round(percent_var.get()) + delta)))
                    update_controls()
                    schedule_save()
                return "break"

            return handler

        toggle.bind("<Button-1>", toggle_enabled)
        slider.bind("<Button-1>", slider_changed)
        slider.bind("<B1-Motion>", slider_changed)
        slider.bind("<Left>", nudge_slider(-1))
        slider.bind("<Right>", nudge_slider(1))
        update_controls()

        def close() -> None:
            nonlocal closing, save_job
            if closing:
                return
            closing = True
            if save_job is not None:
                window.after_cancel(save_job)
                save_job = None
            persist()
            self._settings_window = None
            self._close_settings = None
            window.destroy()

        def dismiss_if_focus_left() -> None:
            try:
                focused = window.focus_get()
                if focused is None or focused.winfo_toplevel() != window:
                    close()
            except Exception:
                close()

        self._close_settings = close
        window.bind("<Escape>", lambda _event: close())
        window.bind(
            "<FocusOut>",
            lambda _event: window.after(60, dismiss_if_focus_left),
            add="+",
        )
        window.protocol("WM_DELETE_WINDOW", close)
        window.update_idletasks()
        self._style_flyout_window(window)
        window.lift()
        window.focus_force()

    def _flyout_position(self, width: int, height: int) -> tuple[int, int]:
        """Рядом с местом клика по tray, но строго внутри рабочей области."""
        screen_w = self._tk.winfo_screenwidth()
        screen_h = self._tk.winfo_screenheight()
        fallback = (screen_w - width - 18, screen_h - height - 64)
        if platform.system() != "Windows":
            return fallback
        try:
            import ctypes
            from ctypes import wintypes

            class Point(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

            class Rect(ctypes.Structure):
                _fields_ = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            class MonitorInfo(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", Rect),
                    ("rcWork", Rect),
                    ("dwFlags", wintypes.DWORD),
                ]

            point = Point()
            if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
                return fallback
            monitor = ctypes.windll.user32.MonitorFromPoint(point, 2)
            info = MonitorInfo()
            info.cbSize = ctypes.sizeof(MonitorInfo)
            if not ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                return fallback

            work = info.rcWork
            x = max(work.left + 8, min(point.x - width + 28, work.right - width - 8))
            y = point.y - height - 12
            if y < work.top + 8:
                y = min(point.y + 12, work.bottom - height - 8)
            return int(x), int(y)
        except Exception as exc:
            logging.debug(f"flyout positioning fallback: {exc}")
            return fallback

    @staticmethod
    def _style_flyout_window(window) -> None:
        """Tool-window без taskbar-кнопки и со скруглением на Windows 11."""
        if platform.system() != "Windows":
            return
        try:
            import ctypes

            client_hwnd = window.winfo_id()
            hwnd = ctypes.windll.user32.GetParent(client_hwnd) or client_hwnd
            get_style = ctypes.windll.user32.GetWindowLongW
            set_style = ctypes.windll.user32.SetWindowLongW
            ex_style = get_style(hwnd, -20)
            set_style(hwnd, -20, ex_style | 0x80)
            corner_preference = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd,
                33,
                ctypes.byref(corner_preference),
                ctypes.sizeof(corner_preference),
            )
        except Exception as exc:
            logging.debug(f"flyout window styling unavailable: {exc}")
