#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, messagebox
import time
import threading

try:
    import winsound
    HAS_WINSOUND = True
except Exception:
    HAS_WINSOUND = False

FOCUS_MINUTES = 26
SHORT_BREAK_MINUTES = 5
LONG_BREAK_MINUTES = 15
ALERT_MARKS = [8, 16, 24]  # minutes elapsed during focus

class PomodoroTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("Pomodoro Timer (26/5, long break on 4th)")
        self.root.resizable(False, False)

        # State
        self.cycle = 1  # 1..4 then repeat
        self.is_running = False
        self.is_focus = True  # focus vs break
        self.remaining = FOCUS_MINUTES * 60  # seconds
        self.elapsed_focus_minutes = 0  # for alert marks
        self.paused = False

        # UI
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        header = ttk.Label(self.root, text="Pomodoro Focus Cycles", font=("Segoe UI", 14, "bold"))
        header.grid(row=0, column=0, columnspan=4, pady=(10,4), padx=10)

        self.status_var = tk.StringVar(value=self._status_text())
        status = ttk.Label(self.root, textvariable=self.status_var, font=("Segoe UI", 10))
        status.grid(row=1, column=0, columnspan=4, pady=(0,8))

        self.time_var = tk.StringVar(value=self._fmt(self.remaining))
        time_label = ttk.Label(self.root, textvariable=self.time_var, font=("Segoe UI", 36, "bold"))
        time_label.grid(row=2, column=0, columnspan=4, pady=(0,10))

        self.progress = ttk.Progressbar(self.root, length=320, mode="determinate", maximum=FOCUS_MINUTES*60)
        self.progress.grid(row=3, column=0, columnspan=4, padx=10, pady=(0,10))
        self._update_progress()

        self.sound_var = tk.BooleanVar(value=True)
        sound_chk = ttk.Checkbutton(self.root, text="Sound alerts", variable=self.sound_var)
        sound_chk.grid(row=4, column=0, padx=10, sticky="w")

        self.popup_var = tk.BooleanVar(value=True)
        popup_chk = ttk.Checkbutton(self.root, text="Popup alerts", variable=self.popup_var)
        popup_chk.grid(row=4, column=1, padx=10, sticky="w")

        self.auto_var = tk.BooleanVar(value=True)
        auto_chk = ttk.Checkbutton(self.root, text="Auto-advance cycles", variable=self.auto_var)
        auto_chk.grid(row=4, column=2, padx=10, sticky="w")

        self.start_btn = ttk.Button(self.root, text="Start", command=self.start)
        self.start_btn.grid(row=5, column=0, padx=10, pady=10, sticky="ew")

        self.pause_btn = ttk.Button(self.root, text="Pause", command=self.pause, state="disabled")
        self.pause_btn.grid(row=5, column=1, padx=10, pady=10, sticky="ew")

        self.reset_btn = ttk.Button(self.root, text="Reset", command=self.reset_session)
        self.reset_btn.grid(row=5, column=2, padx=10, pady=10, sticky="ew")

        self.skip_btn = ttk.Button(self.root, text="Skip ↦", command=self.skip)
        self.skip_btn.grid(row=5, column=3, padx=10, pady=10, sticky="ew")

        self.root.bind("<space>", lambda e: self.toggle())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Timer loop
        self._tick_job = None

    def _fmt(self, secs):
        m, s = divmod(int(secs), 60)
        return f"{m:02d}:{s:02d}"

    def _status_text(self):
        phase = "FOCUS" if self.is_focus else ("BREAK (Long)" if self._current_break_minutes()==LONG_BREAK_MINUTES else "BREAK (Short)")
        return f"Cycle {self.cycle} of 4  •  Phase: {phase}"

    def _current_break_minutes(self):
        return LONG_BREAK_MINUTES if self.cycle == 4 else SHORT_BREAK_MINUTES

    def _update_progress(self):
        if self.is_focus:
            total = FOCUS_MINUTES * 60
        else:
            total = self._current_break_minutes() * 60
        self.progress.configure(maximum=total)
        self.progress['value'] = total - self.remaining

    def _alert(self, title, msg):
        if self.sound_var.get() and HAS_WINSOUND:
            try:
                winsound.Beep(880, 200)
                winsound.Beep(988, 200)
                winsound.Beep(1047, 200)
            except Exception:
                pass
        if self.popup_var.get():
            # Use a short-lived async messagebox to avoid blocking timer too long
            def _show():
                messagebox.showinfo(title, msg)
            # Run in separate thread to avoid blocking Tk's after queue
            threading.Thread(target=_show, daemon=True).start()

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.paused = False
            self.start_btn.configure(state="disabled")
            self.pause_btn.configure(state="normal")
            self._schedule_tick()

    def pause(self):
        self.paused = not self.paused
        if self.paused:
            self.pause_btn.configure(text="Resume")
        else:
            self.pause_btn.configure(text="Pause")

    def toggle(self):
        if self.is_running and not self.paused:
            self.pause()
        elif self.is_running and self.paused:
            self.pause()
        else:
            self.start()

    def reset_session(self):
        if self.is_focus:
            self.remaining = FOCUS_MINUTES * 60
            self.elapsed_focus_minutes = 0
        else:
            self.remaining = self._current_break_minutes() * 60
        self.time_var.set(self._fmt(self.remaining))
        self._update_progress()

    def skip(self):
        # Jump to next phase
        if self.is_focus:
            self._end_focus()
        else:
            self._end_break()

    def _schedule_tick(self):
        if self._tick_job is None:
            self._tick_job = self.root.after(1000, self._tick)

    def _tick(self):
        self._tick_job = None
        if self.is_running and not self.paused:
            if self.remaining > 0:
                self.remaining -= 1
                self.time_var.set(self._fmt(self.remaining))
                self._update_progress()

                if self.is_focus:
                    # Compute minutes elapsed (floor). Trigger alert when hitting 8,16,24 elapsed.
                    elapsed_minutes = FOCUS_MINUTES - int((self.remaining + 59) // 60)  # rounds up seconds to minutes
                    # fire on first time we cross a mark
                    while self.elapsed_focus_minutes < elapsed_minutes:
                        self.elapsed_focus_minutes += 1
                        if self.elapsed_focus_minutes in ALERT_MARKS:
                            self._alert("Focus checkpoint", f"{self.elapsed_focus_minutes} minutes elapsed. Stay on task!")
                # Continue ticking
                self._schedule_tick()
            else:
                # Phase complete
                if self.is_focus:
                    self._end_focus()
                else:
                    self._end_break()
        else:
            # Paused or not running; just reschedule to keep UI responsive
            self._schedule_tick()

    def _end_focus(self):
        self._alert("Focus complete", "26-minute focus block finished. Take a break.")
        self.is_focus = False
        self.elapsed_focus_minutes = 0
        self.remaining = self._current_break_minutes() * 60
        self.status_var.set(self._status_text())
        self.time_var.set(self._fmt(self.remaining))
        self._update_progress()
        if self.auto_var.get():
            # auto-continue
            pass
        else:
            self.is_running = False
            self.start_btn.configure(state="normal")
            self.pause_btn.configure(state="disabled")

    def _end_break(self):
        break_len = self._current_break_minutes()
        self._alert("Break complete", f"{break_len}-minute break finished. Back to focus.")
        self.is_focus = True
        self.remaining = FOCUS_MINUTES * 60
        if self.cycle == 4:
            self.cycle = 1
        else:
            self.cycle += 1
        self.status_var.set(self._status_text())
        self.time_var.set(self._fmt(self.remaining))
        self._update_progress()
        if self.auto_var.get():
            # auto-continue
            pass
        else:
            self.is_running = False
            self.start_btn.configure(state="normal")
            self.pause_btn.configure(state="disabled")

    def on_close(self):
        # Safely cancel timers
        if self._tick_job is not None:
            try:
                self.root.after_cancel(self._tick_job)
            except Exception:
                pass
        self.root.destroy()

def main():
    root = tk.Tk()
    app = PomodoroTimer(root)
    root.mainloop()

if __name__ == "__main__":
    main()
