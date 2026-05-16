#!/usr/bin/env python3
"""Native macOS transparent desktop pet with verbose debug output.

Run:
    python3 pixel_person_pet.py

Keys:
    1 idle, 2 walk, 3 drink, 4 typing, Esc quit
"""

from __future__ import annotations

import random
import os
import sys
import time
import traceback
from collections import deque
from pathlib import Path

import objc
from AppKit import (
    NSApp,
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBackingStoreBuffered,
    NSBorderlessWindowMask,
    NSColor,
    NSFloatingWindowLevel,
    NSImage,
    NSImageAlignCenter,
    NSImageScaleProportionallyUpOrDown,
    NSImageView,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSPanel,
    NSScreen,
    NSStatusWindowLevel,
    NSTextField,
    NSView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
)
from Foundation import NSObject, NSTimer
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "assets"
CACHE_ROOT = PROJECT_ROOT / ".pet_cache"
TARGET_HEIGHT = 210
TIMER_LABEL_HEIGHT = 34
FRAME_DELAY_SECONDS = 0.36
REQUIRED_ACTIONS = ("idle", "walk", "drink", "typing")
OPTIONAL_ACTIONS = ("focus", "done")
KEEP_ALIVE = {}
CLICK_SEQUENCE = ("walk", "drink", "typing")
FOCUS_SECONDS = int(os.environ.get("PET_FOCUS_SECONDS", str(60 * 60)))


def debug(message: str) -> None:
    print(message, flush=True)


def is_checker_pixel(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    return r > 220 and g > 220 and b > 220 and max(pixel) - min(pixel) <= 12


def remove_edge_checkerboard(image: Image.Image) -> Image.Image:
    debug("Step 8: Removing checkerboard background from one frame...")
    if image.mode == "RGBA" and image.getchannel("A").getextrema()[0] < 255:
        debug("Step 8: Frame already has transparency. Keeping alpha channel.")
        rgba = image
        bbox = rgba.getbbox()
        debug(f"Step 9: Frame visible bounding box: {bbox}")
        if bbox:
            rgba = rgba.crop(bbox)
        scale = TARGET_HEIGHT / rgba.height
        target_size = (max(1, round(rgba.width * scale)), TARGET_HEIGHT)
        debug(f"Step 10: Resizing frame to {target_size}...")
        return rgba.resize(target_size, Image.Resampling.LANCZOS)

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
    debug(f"Step 9: Frame visible bounding box: {bbox}")
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
    target_size = (max(1, round(rgba.width * scale)), TARGET_HEIGHT)
    debug(f"Step 10: Resizing frame to {target_size}...")
    return rgba.resize(target_size, Image.Resampling.LANCZOS)


def prepare_frame_files() -> dict[str, list[Path]]:
    debug(f"Step 4: Checking source folder: {SOURCE_ROOT}")
    if not SOURCE_ROOT.exists():
        raise FileNotFoundError(f"Source folder does not exist: {SOURCE_ROOT}")
    debug("Step 5: Source folder exists.")

    debug(f"Step 6: Creating cache folder: {CACHE_ROOT}")
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    prepared: dict[str, list[Path]] = {}
    for action in REQUIRED_ACTIONS + OPTIONAL_ACTIONS:
        source_folder = SOURCE_ROOT / action
        output_folder = CACHE_ROOT / action
        output_folder.mkdir(parents=True, exist_ok=True)
        if action in OPTIONAL_ACTIONS:
            paths = sorted(source_folder.glob("*.png"))
        else:
            paths = sorted(source_folder.glob(f"{action}_*.png"))
        debug(f"Step 7: Found {len(paths)} frame(s) for action '{action}' in {source_folder}")

        if not paths:
            if action in OPTIONAL_ACTIONS:
                debug(f"Step 7: Optional action '{action}' is missing. Skipping.")
                continue
            raise FileNotFoundError(f"No frames found for action: {action}")

        prepared[action] = []
        for index, path in enumerate(paths, start=1):
            debug(f"Step 7.{index}: Opening image: {path}")
            image = Image.open(path)
            debug(f"Step 7.{index}: Original image mode/size: {image.mode} {image.size}")
            cleaned = remove_edge_checkerboard(image)
            output_path = output_folder / f"{action}_{index}.png"
            cleaned.save(output_path)
            prepared[action].append(output_path)
            debug(f"Step 11.{index}: Transparent frame saved: {output_path}")

    return prepared


def load_ns_images(frame_files: dict[str, list[Path]]) -> dict[str, list[NSImage]]:
    debug("Step 12: Loading transparent PNG files into NSImage objects...")
    images: dict[str, list[NSImage]] = {}
    for action, paths in frame_files.items():
        images[action] = []
        for path in paths:
            image = NSImage.alloc().initWithContentsOfFile_(str(path))
            if image is None:
                raise RuntimeError(f"Could not load NSImage: {path}")
            images[action].append(image)
            debug(f"Step 12: Loaded NSImage for {action}: {path.name}")
    return images


class PetController(NSObject):
    def initWithWindow_imageView_timerLabel_frames_(self, window, image_view, timer_label, frames):
        self = objc.super(PetController, self).init()
        if self is None:
            return None

        debug("Step 18: Initializing PetController state...")
        self.window = window
        self.image_view = image_view
        self.timer_label = timer_label
        self.frames = frames
        self.action = "idle"
        self.frame_index = 0
        self.action_loops_left = 0
        self.walk_direction = random.choice([-1, 1])
        self.tick_count = 0
        self.click_index = 0
        self.timer = None
        self.focus_active = False
        self.focus_finished = False
        self.focus_end_time = 0.0
        self.last_countdown_text = ""
        debug("Step 19: PetController state ready.")
        return self

    def start(self):
        debug("Step 20: Starting animation timer...")
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            FRAME_DELAY_SECONDS,
            self,
            "tick:",
            None,
            True,
        )
        debug("Step 21: Animation timer started.")

    def play_(self, action):
        if action in OPTIONAL_ACTIONS and action not in self.frames:
            debug(f"Step ACTION: Optional frame '{action}' missing. Falling back to idle.")
            action = "idle"
        debug(f"Step ACTION: Switching to action '{action}'.")
        self.action = action
        self.frame_index = 0
        self.action_loops_left = 12 if action == "walk" else 2
        if action in ("idle", "focus", "done"):
            self.action_loops_left = 0
        if action == "walk":
            self.walk_direction = random.choice([-1, 1])
            debug(f"Step ACTION: Walk direction is {self.walk_direction}.")

    def startFocusMode_(self, _sender):
        debug("Step FOCUS: Starting 1-hour focus mode.")
        self.focus_active = True
        self.focus_finished = False
        self.focus_end_time = time.time() + FOCUS_SECONDS
        self.last_countdown_text = ""
        self.play_("focus")
        self.action_loops_left = 0
        self.updateFocusLabel()

    def cancelFocusMode_(self, _sender):
        debug("Step FOCUS: Cancelling focus mode.")
        self.focus_active = False
        self.focus_finished = False
        self.focus_end_time = 0.0
        self.last_countdown_text = ""
        self.timer_label.setStringValue_("")
        self.play_("idle")

    def playTypingFromMenu_(self, _sender):
        debug("Step ACTION: Menu selected typing.")
        self.play_("typing")

    def quitFromMenu_(self, _sender):
        debug("Step EVENT: Menu selected quit.")
        NSApp().terminate_(None)

    def playNextClickAction(self):
        if self.focus_active:
            debug("Step ACTION: Click ignored during focus mode.")
            return
        action = CLICK_SEQUENCE[self.click_index % len(CLICK_SEQUENCE)]
        self.click_index += 1
        debug(f"Step ACTION: Click selected action '{action}'.")
        self.play_(action)

    def updateFocusLabel(self):
        if not self.focus_active:
            return

        remaining = max(0, int(round(self.focus_end_time - time.time())))
        minutes = remaining // 60
        seconds = remaining % 60
        text = f"Focus {minutes:02d}:{seconds:02d}"

        if text != self.last_countdown_text:
            debug(f"Step FOCUS: Countdown {text}")
            self.timer_label.setStringValue_(text)
            self.last_countdown_text = text

        if remaining <= 0:
            debug("Step FOCUS: Focus mode completed.")
            self.focus_active = False
            self.focus_finished = True
            self.timer_label.setStringValue_("Good!")
            self.play_("done")

    def tick_(self, _timer):
        self.tick_count += 1
        self.updateFocusLabel()

        if self.action == "idle":
            self.image_view.setImage_(self.frames["idle"][0])
            return
        if self.action in ("focus", "done"):
            self.image_view.setImage_(self.frames.get(self.action, self.frames["idle"])[0])
            return

        frames = self.frames[self.action]
        image = frames[self.frame_index % len(frames)]
        self.image_view.setImage_(image)

        if self.action == "walk":
            frame = self.window.frame()
            visible = NSScreen.mainScreen().visibleFrame()
            new_x = frame.origin.x + self.walk_direction * 10
            if new_x < visible.origin.x + 40:
                self.walk_direction = 1
                new_x = visible.origin.x + 40
                debug("Step ANIM: Walk hit left edge, turning right.")
            elif new_x + frame.size.width > visible.origin.x + visible.size.width - 40:
                self.walk_direction = -1
                new_x = visible.origin.x + visible.size.width - frame.size.width - 40
                debug("Step ANIM: Walk hit right edge, turning left.")
            debug(f"Step ANIM: Walking. x={new_x}")
            self.window.setFrameOrigin_((new_x, frame.origin.y))

        self.frame_index += 1
        if self.frame_index >= len(frames):
            debug(f"Step ANIM: Completed one loop of '{self.action}'.")
            self.frame_index = 0
            if self.action != "idle":
                self.action_loops_left -= 1
                debug(f"Step ANIM: loops left for '{self.action}': {self.action_loops_left}")
                if self.action_loops_left <= 0:
                    self.play_("idle")


class PetImageView(NSImageView):
    controller = objc.ivar()
    drag_start = objc.ivar()

    def acceptsFirstResponder(self):
        return True

    def mouseDown_(self, event):
        debug("Step EVENT: mouseDown. Start drag and play one click action.")
        self.drag_start = event.locationInWindow()
        self.controller.playNextClickAction()

    def mouseDragged_(self, event):
        current = event.locationInWindow()
        dx = current.x - self.drag_start.x
        dy = current.y - self.drag_start.y
        frame = self.window().frame()
        self.window().setFrameOrigin_((frame.origin.x + dx, frame.origin.y + dy))
        debug(f"Step EVENT: dragging window by dx={dx}, dy={dy}")

    def rightMouseDown_(self, _event):
        debug("Step EVENT: rightMouseDown. Showing context menu.")
        menu = NSMenu.alloc().initWithTitle_("Pet Menu")

        focus_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "开始专注 1 小时", "startFocusMode:", ""
        )
        focus_item.setTarget_(self.controller)
        menu.addItem_(focus_item)

        cancel_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "取消专注", "cancelFocusMode:", ""
        )
        cancel_item.setTarget_(self.controller)
        menu.addItem_(cancel_item)

        menu.addItem_(NSMenuItem.separatorItem())

        typing_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "打字", "playTypingFromMenu:", ""
        )
        typing_item.setTarget_(self.controller)
        menu.addItem_(typing_item)

        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "退出", "quitFromMenu:", ""
        )
        quit_item.setTarget_(self.controller)
        menu.addItem_(quit_item)

        NSMenu.popUpContextMenu_withEvent_forView_(menu, _event, self)

    def keyDown_(self, event):
        key = event.charactersIgnoringModifiers()
        debug(f"Step EVENT: keyDown '{key}'")
        if key == "1":
            self.controller.play_("idle")
        elif key == "2":
            self.controller.play_("walk")
        elif key == "3":
            self.controller.play_("drink")
        elif key == "4":
            self.controller.play_("typing")
        elif key == "f":
            self.controller.startFocusMode_(None)
        elif key == "c":
            self.controller.cancelFocusMode_(None)
        elif event.keyCode() == 53:
            debug("Step EVENT: Escape pressed. Terminating app.")
            NSApp().terminate_(None)


def create_window(frames: dict[str, list[NSImage]]) -> None:
    debug("Step 13: Creating native macOS app/window...")
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    app.finishLaunching()
    app.activateIgnoringOtherApps_(True)
    debug("Step 13b: NSApplication finished launching and activated as accessory app.")

    width = max(round(image.size().width) for action_frames in frames.values() for image in action_frames)
    image_height = max(round(image.size().height) for action_frames in frames.values() for image in action_frames)
    height = image_height + TIMER_LABEL_HEIGHT
    debug(f"Step 14: Window size will be {width}x{height}.")

    screen = NSScreen.mainScreen()
    visible = screen.visibleFrame() if screen is not None else NSMakeRect(0, 0, 1440, 900)
    start_x = visible.origin.x + (visible.size.width - width) / 2
    start_y = visible.origin.y + (visible.size.height - height) / 2
    debug(f"Step 14b: Main screen visible frame is {visible}.")
    debug(f"Step 14c: Window start position will be x={start_x}, y={start_y}.")

    window = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(start_x, start_y, width, height),
        NSBorderlessWindowMask,
        NSBackingStoreBuffered,
        False,
    )
    KEEP_ALIVE["app"] = app
    KEEP_ALIVE["window"] = window
    window.setOpaque_(False)
    window.setBackgroundColor_(NSColor.clearColor())
    window.setHasShadow_(False)
    window.setLevel_(NSStatusWindowLevel)
    window.setIgnoresMouseEvents_(False)
    window.setMovableByWindowBackground_(True)
    window.setReleasedWhenClosed_(False)
    window.setCanHide_(False)
    window.setHidesOnDeactivate_(False)
    window.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces
        | NSWindowCollectionBehaviorFullScreenAuxiliary
    )
    debug("Step 15: Transparent floating NSPanel configured.")

    content_view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
    content_view.setWantsLayer_(True)
    content_view.layer().setBackgroundColor_(NSColor.clearColor().CGColor())

    timer_label = NSTextField.alloc().initWithFrame_(
        NSMakeRect(0, image_height, width, TIMER_LABEL_HEIGHT)
    )
    timer_label.setStringValue_("")
    timer_label.setBezeled_(False)
    timer_label.setDrawsBackground_(False)
    timer_label.setEditable_(False)
    timer_label.setSelectable_(False)
    timer_label.setTextColor_(NSColor.whiteColor())
    timer_label.setAlignment_(1)

    image_view = PetImageView.alloc().initWithFrame_(NSMakeRect(0, 0, width, image_height))
    image_view.setImage_(frames["idle"][0])
    image_view.setImageScaling_(NSImageScaleProportionallyUpOrDown)
    image_view.setImageAlignment_(NSImageAlignCenter)
    image_view.setWantsLayer_(True)
    content_view.addSubview_(image_view)
    content_view.addSubview_(timer_label)
    window.setContentView_(content_view)
    KEEP_ALIVE["content_view"] = content_view
    KEEP_ALIVE["image_view"] = image_view
    KEEP_ALIVE["timer_label"] = timer_label
    window.display()
    window.makeKeyAndOrderFront_(None)
    window.orderFrontRegardless()
    debug("Step 16: Image view installed and window shown.")

    controller = PetController.alloc().initWithWindow_imageView_timerLabel_frames_(
        window, image_view, timer_label, frames
    )
    image_view.controller = controller
    window.makeFirstResponder_(image_view)
    controller.start()

    KEEP_ALIVE["controller"] = controller
    debug(f"Step 21b: Window visible? {window.isVisible()} frame={window.frame()}")
    debug("Step 22: Entering AppKit event loop. This keeps running until Esc or Cmd+Q.")
    app.run()


def main() -> int:
    debug("Step 0: Script started.")
    debug(f"Step 0: Python executable: {sys.executable}")
    debug(f"Step 0: Python version: {sys.version}")
    debug(f"Step 0: Current working directory: {Path.cwd()}")
    debug(f"Step 0: Platform: {sys.platform}")

    try:
        if sys.platform != "darwin":
            raise RuntimeError("This native transparent version is for macOS only.")

        debug("Step 1: Importing AppKit/PyObjC succeeded.")
        frame_files = prepare_frame_files()
        frames = load_ns_images(frame_files)
        create_window(frames)
        return 0
    except KeyboardInterrupt:
        debug("Step ERROR: KeyboardInterrupt received. Exiting.")
        return 130
    except Exception:
        debug("Step ERROR: The program crashed. Full traceback below:")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
