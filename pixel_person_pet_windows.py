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
