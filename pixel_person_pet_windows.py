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


def resize_without_magenta_fringe(image: Image.Image) -> Image.Image:
    scale = TARGET_HEIGHT / image.height
    target_size = (max(1, round(image.width * scale)), TARGET_HEIGHT)
    resized = image.resize(target_size, Image.Resampling.LANCZOS).convert("RGBA")
    pixels = resized.load()
    width, height = resized.size

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < 150:
                pixels[x, y] = (0, 0, 0, 0)
            else:
                pixels[x, y] = (r, g, b, 255)

    return resized


def remove_edge_checkerboard(image: Image.Image) -> Image.Image:
    if image.mode == "RGBA" and image.getchannel("A").getextrema()[0] < 255:
        rgba = image
        bbox = rgba.getbbox()
        if bbox:
            rgba = rgba.crop(bbox)
        return resize_without_magenta_fringe(rgba)

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
