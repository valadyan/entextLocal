import tkinter as tk
from tkinter import ttk
import threading
import time

# Optional: requires Pillow for GIF support. Install with: pip install Pillow
try:
    from PIL import Image, ImageTk, ImageSequence
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class WaitingWindow:
    def __init__(self, parent, title="Please Wait", message="Loading...",
                 gif_path=None):
        self.parent = parent
        self.result = None
        self._frames = []
        self._frame_index = 0
        self._animation_job = None
        self.is_gif = False

        # Create child window
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.resizable(False, False)

        # Make it modal
        self.window.transient(parent)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", lambda: None)

        # Message label
        self.label = tk.Label(self.window, text=message, font=("Arial", 11))
        self.label.pack(pady=(15, 5))

        if gif_path:
            self.gif_label = tk.Label(self.window, bd=0)
            self.gif_label.pack(pady=(5, 15))
            self.load_gif(gif_path)
            self.is_gif = True
        else:
            # Progress bar
            self.progress = ttk.Progressbar(
                self.window, mode='indeterminate', length=250
            )
            self.progress.pack(pady=5)
            self.progress.start(10)
            
        # Size window based on content
        self._fit_and_center(300, 80)
        self.window.after(50, lambda: self._fit_and_center(300, 80))

    # ------------------------------------------------------------------ #
    def load_gif(self, gif_path):
        """Load and start animating the GIF."""
        if not PIL_AVAILABLE:
            self.gif_label.config(text="Pillow not installed\npip install Pillow")
            return

        try:
            image = Image.open(gif_path)
        except Exception as e:
            self.gif_label.config(text=f"Failed to load GIF:\n{e}")
            return

        # Extract all frames (with durations)
        self._frames = []
        self._durations = []
        for frame in ImageSequence.Iterator(image):
            frame = frame.convert("RGBA")
            self._frames.append(ImageTk.PhotoImage(frame))
            self._durations.append(frame.info.get("duration", 100))

        if self._frames:
            self.gif_label.config(image=self._frames[0])
            self._animate_gif()

    def _animate_gif(self):
        """Cycle through GIF frames."""
        if not self._frames:
            return
        frame = self._frames[self._frame_index % len(self._frames)]
        self.gif_label.config(image=frame)
        delay = self._durations[self._frame_index % len(self._durations)]
        self._frame_index += 1
        self._animation_job = self.window.after(delay, self._animate_gif)

    # ------------------------------------------------------------------ #
    def _fit_and_center(self, min_w, min_h):
        """Resize window to fit contents and center over parent."""
        self.window.update_idletasks()

        req_w = max(min_w, self.window.winfo_reqwidth())
        req_h = max(min_h, self.window.winfo_reqheight())

        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()

        x = parent_x + (parent_w - req_w) // 2
        y = parent_y + (parent_h - req_h) // 2

        self.window.geometry(f"{req_w}x{req_h}+{x}+{y}")

    def update_message(self, message):
        self.label.config(text=message)
        self.window.update_idletasks()

    def close(self):
        """Stop animation and close window."""
        if self._animation_job is not None:
            try:
                self.window.after_cancel(self._animation_job)
            except Exception:
                pass
            self._animation_job = None
        if not self.is_gif:
            self.progress.stop()
        self.window.grab_release()
        self.window.destroy()

