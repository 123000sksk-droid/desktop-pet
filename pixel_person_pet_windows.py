#!/usr/bin/env python3
"""Windows desktop pet version.

Run on Windows:
    python pixel_person_pet_windows.py

Package on Windows:
    pyinstaller --noconsole --onefile --add-data "assets;assets" --name PixelPersonPet pixel_person_pet_windows.py
"""

from __future__ import annotations

import os
import random
import sys
import time
import traceback
import tkinter as tk
from collections import deque
from pathlib import Path
from tkinter import Menu

from PIL import Image, ImageTk


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


PROJECT_ROOT = app_root()
SOURCE_ROOT = PROJECT_ROOT / "assets"
TARGET_HEIGHT = 210
FRAME_DELAY_MS = 360
TRANSPARENT_COLOR = "#ff00ff"
REQUIRED_ACTIONS = ("idle", "walk", "drink", "typing")
OPTIONAL_ACTIONS = ("focus", "done")
CLICK_SEQUENCE = ("walk", "drink", "typing")
FOCUS_SECONDS = int(os.environ.get("PET_FOCUS_SECONDS", str(60 * 60)))
LOG_PATH = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop" / "PixelPersonPet-debug.log"


def debug(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as log:
            log.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)


def is_checker_pixel(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    return r > 220 and g > 220 and b > 220 and max(pixel) - min(pixel) <= 12


def remove_edge_checkerboard(image: Image.Image) -> Image.Image:
    if image.mode == "RGBA" and image.getchannel("A").getextrema()[0] < 255:
        rgba = image
        bbox = rgba.getbbox()
        if bbox:
            rgba = rgba.crop(bbox)
        scale = TARGET_HEIGHT / rgba.height
        return rgba.resize((max(1, round(rgba.width * scale)), TARGET_HEIGHT), Image.Resampling.LANCZOS)

    rgb = image.convert("RGB")
    rgba = image.convert("RGBA")
    width, height = rgb.size
    pixels = rgb.load()
    alpha = rgba.load()
    seen: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()

    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        if (x, y) in seen or not (0 <= x < width and 0 <= y < height):
            continue
        seen.add((x, y))
        if not is_checker_pixel(pixels[x, y]):
            continue
        r, g, b, _ = alpha[x, y]
        alpha[x, y] = (r, g, b, 0)
        queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    bbox = rgba.getbbox()
    if bbox:
        left, top, right, bottom = bbox
        padding = 12
        rgba = rgba.crop(
            (
                max(0, left - padding),
                max(0, top - padding),
                min(width, right + padding),
                min(height, bottom + padding),
            )
        )

    scale = TARGET_HEIGHT / rgba.height
    return rgba.resize((max(1, round(rgba.width * scale)), TARGET_HEIGHT), Image.Resampling.LANCZOS)


def action_paths(action: str) -> list[Path]:
    folder = SOURCE_ROOT / action
    if folder.exists():
        if action in OPTIONAL_ACTIONS:
            paths = sorted(folder.glob("*.png"))
        else:
            paths = sorted(folder.glob(f"{action}_*.png"))
        if paths:
            return paths

    # GitHub's web uploader may flatten folders. The workflow used for that
    # case packages the repository root as "assets", so support flat files too.
    if action == "focus":
        return sorted(SOURCE_ROOT.glob("bang*.png")) + sorted(SOURCE_ROOT.glob("focus*.png"))
    if action == "done":
        return sorted(SOURCE_ROOT.glob("good*.png")) + sorted(SOURCE_ROOT.glob("done*.png"))
    return sorted(SOURCE_ROOT.glob(f"{action}_*.png"))


class PixelPersonPet:
    def __init__(self) -> None:
        try:
            if LOG_PATH.exists():
                LOG_PATH.unlink()
        except Exception:
            pass
        debug("Step 0: Starting Windows desktop pet.")
        debug(f"Step 1: Asset folder: {SOURCE_ROOT}")
        self.root = tk.Tk()
        self.root.title("Pixel Person Pet")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)

        self.frames = self.load_frames()
        self.width = max(180, max(frame.width() for frames in self.frames.values() for frame in frames))
        self.image_height = max(frame.height() for frames in self.frames.values() for frame in frames)
        self.height = self.image_height + 34

        self.timer_label = tk.Label(
            self.root,
            text="Pixel Pet started",
            fg="white",
            bg=TRANSPARENT_COLOR,
            font=("Segoe UI", 13, "bold"),
        )
        self.timer_label.pack()

        self.image_label = tk.Label(
            self.root,
            image=self.frames["idle"][0],
            bg=TRANSPARENT_COLOR,
            borderwidth=0,
            highlightthickness=0,
        )
        self.image_label.pack()

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.x = (screen_w - self.width) // 2
        self.y = (screen_h - self.height) // 2
        self.root.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")

        self.action = "idle"
        self.frame_index = 0
        self.action_loops_left = 0
        self.walk_direction = random.choice([-1, 1])
        self.click_index = 0
        self.drag_offset: tuple[int, int] | None = None
        self.focus_active = False
        self.focus_end_time = 0.0
        self.last_countdown_text = ""

        self.menu = Menu(self.root, tearoff=0)
        self.menu.add_command(label="开始专注 1 小时", command=self.start_focus)
        self.menu.add_command(label="取消专注", command=self.cancel_focus)
        self.menu.add_separator()
        self.menu.add_command(label="打字", command=lambda: self.play("typing"))
        self.menu.add_command(label="退出", command=self.root.destroy)

        self.image_label.bind("<ButtonPress-1>", self.on_left_down)
        self.image_label.bind("<B1-Motion>", self.on_drag)
        self.image_label.bind("<ButtonRelease-1>", self.on_left_up)
        self.image_label.bind("<Button-3>", self.show_menu)
        self.timer_label.bind("<Button-3>", self.show_menu)
        self.root.bind("<Key>", self.on_key)
        self.root.focus_force()

        debug("Step 2: Window ready.")
        self.root.after(2000, lambda: self.timer_label.configure(text=""))
        self.animate()

    def load_frames(self) -> dict[str, list[ImageTk.PhotoImage]]:
        frames: dict[str, list[ImageTk.PhotoImage]] = {}
        for action in REQUIRED_ACTIONS + OPTIONAL_ACTIONS:
            paths = action_paths(action)
            debug(f"Step LOAD: {action} has {len(paths)} frame(s).")
            for path in paths:
                debug(f"Step LOAD: {action} path: {path}")
            if not paths:
                if action in OPTIONAL_ACTIONS:
                    continue
                raise FileNotFoundError(f"Missing frames for {action}: {SOURCE_ROOT / action}")
            frames[action] = [
                ImageTk.PhotoImage(remove_edge_checkerboard(Image.open(path)))
                for path in paths
            ]
        return frames

    def play(self, action: str) -> None:
        if action in OPTIONAL_ACTIONS and action not in self.frames:
            action = "idle"
        debug(f"Step ACTION: {action}")
        self.action = action
        self.frame_index = 0
        self.action_loops_left = 12 if action == "walk" else 2
        if action in ("idle", "focus", "done"):
            self.action_loops_left = 0
        if action == "walk":
            self.walk_direction = random.choice([-1, 1])

    def play_next_click_action(self) -> None:
        if self.focus_active:
            debug("Step ACTION: click ignored during focus.")
            return
        action = CLICK_SEQUENCE[self.click_index % len(CLICK_SEQUENCE)]
        self.click_index += 1
        self.play(action)

    def start_focus(self) -> None:
        debug("Step FOCUS: start.")
        self.focus_active = True
        self.focus_end_time = time.time() + FOCUS_SECONDS
        self.last_countdown_text = ""
        self.play("focus")
        self.action_loops_left = 0
        self.update_focus_label()

    def cancel_focus(self) -> None:
        debug("Step FOCUS: cancel.")
        self.focus_active = False
        self.focus_end_time = 0.0
        self.last_countdown_text = ""
        self.timer_label.configure(text="")
        self.play("idle")

    def update_focus_label(self) -> None:
        if not self.focus_active:
            return
        remaining = max(0, int(round(self.focus_end_time - time.time())))
        minutes = remaining // 60
        seconds = remaining % 60
        text = f"Focus {minutes:02d}:{seconds:02d}"
        if text != self.last_countdown_text:
            self.timer_label.configure(text=text)
            self.last_countdown_text = text
        if remaining <= 0:
            debug("Step FOCUS: complete.")
            self.focus_active = False
            self.timer_label.configure(text="Good!")
            self.play("done")

    def animate(self) -> None:
        self.update_focus_label()

        if self.action == "idle":
            self.image_label.configure(image=self.frames["idle"][0])
            self.root.after(FRAME_DELAY_MS, self.animate)
            return
        if self.action in ("focus", "done"):
            self.image_label.configure(image=self.frames.get(self.action, self.frames["idle"])[0])
            self.root.after(FRAME_DELAY_MS, self.animate)
            return

        frames = self.frames[self.action]
        self.image_label.configure(image=frames[self.frame_index % len(frames)])

        if self.action == "walk":
            self.x += self.walk_direction * 10
            if self.x < 40:
                self.x = 40
                self.walk_direction = 1
            elif self.x + self.width > self.root.winfo_screenwidth() - 40:
                self.x = self.root.winfo_screenwidth() - self.width - 40
                self.walk_direction = -1
            self.root.geometry(f"+{self.x}+{self.y}")

        self.frame_index += 1
        if self.frame_index >= len(frames):
            self.frame_index = 0
            self.action_loops_left -= 1
            if self.action_loops_left <= 0:
                self.play("idle")

        self.root.after(FRAME_DELAY_MS, self.animate)

    def on_left_down(self, event: tk.Event) -> None:
        self.drag_offset = (event.x_root - self.x, event.y_root - self.y)
        self.play_next_click_action()

    def on_drag(self, event: tk.Event) -> None:
        if not self.drag_offset:
            return
        offset_x, offset_y = self.drag_offset
        self.x = event.x_root - offset_x
        self.y = event.y_root - offset_y
        self.root.geometry(f"+{self.x}+{self.y}")

    def on_left_up(self, _event: tk.Event) -> None:
        self.drag_offset = None

    def show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def on_key(self, event: tk.Event) -> None:
        key = event.char.lower()
        if key == "1":
            self.play("idle")
        elif key == "2":
            self.play("walk")
        elif key == "3":
            self.play("drink")
        elif key == "4":
            self.play("typing")
        elif key == "f":
            self.start_focus()
        elif key == "c":
            self.cancel_focus()
        elif event.keysym == "Escape":
            self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    try:
        PixelPersonPet().run()
    except Exception:
        debug("Step ERROR: app crashed")
        debug(traceback.format_exc())
        try:
            tk.Tk().withdraw()
            from tkinter import messagebox

            messagebox.showerror(
                "PixelPersonPet error",
                f"程序出错了，日志在桌面：\n{LOG_PATH}",
            )
        except Exception:
            pass
        raise
