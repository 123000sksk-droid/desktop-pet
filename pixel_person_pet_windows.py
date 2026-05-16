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


def debug(message: str) -> None:
    print(message, flush=True)


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
