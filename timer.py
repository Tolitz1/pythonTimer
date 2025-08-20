import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import ctypes
from PIL import Image, ImageDraw
import pystray
import threading
import sys
import json
import os
from datetime import datetime
import win32event
import win32api
import winerror
import win32con

# ---------------- Single instance & Event ----------------
mutex_name = "AlvinTimerSingletonMutex"
event_name = "AlvinTimerShowWindowEvent"

mutex = win32event.CreateMutex(None, False, mutex_name)
last_error = win32api.GetLastError()
if last_error == winerror.ERROR_ALREADY_EXISTS:
    # Another instance exists → signal it to show window
    try:
        hEvent = win32event.OpenEvent(win32con.EVENT_MODIFY_STATE, False, event_name)
        if hEvent:
            win32event.SetEvent(hEvent)
    except Exception as e:
        print("Failed to signal existing instance:", e)
    sys.exit(0)

# Create event for this instance
hEvent = win32event.CreateEvent(None, False, False, event_name)

# ---------------- Globals ----------------
countdown_seconds = 0
original_seconds = 0
is_running = False
icon = None
start_timestamp = None  # datetime when timer started or resumed

APP_NAME = "AlvinTimer"
APPDATA_DIR = os.path.join(os.getenv("APPDATA"), APP_NAME)
os.makedirs(APPDATA_DIR, exist_ok=True)
STATE_FILE = os.path.join(APPDATA_DIR, "timer_state.json")

RESET_PASSWORD = "1234"  # Password for reset button

# ---------------- Utility functions ----------------
def sanitize_input(event=None):
    raw = ''.join(filter(str.isdigit, entry.get()))[:6]
    raw = raw.zfill(6)
    h, m, s = raw[:2], raw[2:4], raw[4:6]
    formatted = f"{h}:{m}:{s}"
    entry.delete(0, tk.END)
    entry.insert(0, formatted)

def hms_to_seconds(hms):
    h, m, s = map(int, hms.split(":"))
    return h * 3600 + m * 60 + s

def seconds_to_hms(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

# ---------------- Timer functions ----------------
def start_timer():
    global countdown_seconds, original_seconds, is_running, start_timestamp

    countdown_seconds = hms_to_seconds(entry.get())
    original_seconds = countdown_seconds
    if countdown_seconds <= 0:
        label.config(text="Enter time")
        return

    entry.pack_forget()
    start_btn.pack_forget()
    plus_frame.pack_forget()
    back_btn.pack_forget()
    reset_btn.pack_forget()
    show_reset_btn.pack(pady=5)

    label.config(text=seconds_to_hms(countdown_seconds))
    update_progress()
    is_running = True
    start_timestamp = datetime.now()
    update_timer()

def update_timer():
    global countdown_seconds, is_running, start_timestamp

    if not is_running:
        return

    elapsed = int((datetime.now() - start_timestamp).total_seconds())
    remaining = original_seconds - elapsed
    if remaining < 0:
        remaining = 0

    countdown_seconds = remaining

    label.config(text=seconds_to_hms(countdown_seconds))
    update_progress()
    save_state()

    if countdown_seconds == 0:
        label.config(text="Time's up!")
        lock_windows()
        is_running = False
        show_reset_btn.pack_forget()
        reset_btn.pack_forget()
        back_btn.pack(pady=10)
        delete_state()
    else:
        root.after(1000, update_timer)

def add_time(seconds):
    global countdown_seconds, original_seconds, start_timestamp

    if is_running:
        elapsed = int((datetime.now() - start_timestamp).total_seconds())
        countdown_seconds = original_seconds - elapsed + seconds
        if countdown_seconds < 0:
            countdown_seconds = 0
        original_seconds = countdown_seconds
        start_timestamp = datetime.now()
        label.config(text=seconds_to_hms(countdown_seconds))
        update_progress()
    else:
        current_seconds = hms_to_seconds(entry.get())
        new_seconds = current_seconds + seconds
        entry.delete(0, tk.END)
        entry.insert(0, seconds_to_hms(new_seconds))

def update_progress():
    if original_seconds > 0:
        elapsed = original_seconds - countdown_seconds
        progress = (elapsed / original_seconds) * 100
        progress_bar['value'] = min(progress, 100)
    else:
        progress_bar['value'] = 0

def lock_windows():
    try:
        ctypes.windll.user32.LockWorkStation()
    except Exception as e:
        print("Error locking workstation:", e)

def back_to_setup():
    global countdown_seconds, original_seconds, is_running, start_timestamp
    countdown_seconds = 0
    original_seconds = 0
    is_running = False
    start_timestamp = None

    label.config(text="")
    back_btn.pack_forget()
    reset_btn.pack_forget()
    show_reset_btn.pack_forget()

    entry.delete(0, tk.END)
    entry.insert(0, "00:00:00")
    entry.pack(pady=10)
    start_btn.pack(pady=5)
    plus_frame.pack(pady=10)
    progress_bar['value'] = 0
    delete_state()

def prompt_password_and_show_reset():
    pw = simpledialog.askstring("Password Required", "Enter password to enable Reset:", show="*")
    if pw == RESET_PASSWORD:
        messagebox.showinfo("Access Granted", "Reset enabled.")
        show_reset_btn.pack_forget()
        reset_btn.pack(pady=5)
    elif pw is None:
        pass
    else:
        messagebox.showerror("Access Denied", "Incorrect password.")

# ---------------- System Tray ----------------
def create_image():
    image = Image.new('RGB', (64, 64), color='black')
    dc = ImageDraw.Draw(image)
    dc.ellipse((16, 16, 48, 48), fill='white')
    dc.line((32, 32, 32, 20), fill='black', width=3)
    dc.line((32, 32, 44, 32), fill='black', width=3)
    return image

def on_quit(icon, item):
    icon.visible = False
    icon.stop()
    root.after(0, root.quit)  # clean exit

def show_window(icon, item):
    root.after(0, root.deiconify)

def minimize_to_tray():
    save_state()
    root.withdraw()
    if icon is not None:
        icon.visible = True

def tray_loop():
    global icon
    image = create_image()
    menu = pystray.Menu(
        pystray.MenuItem('Open Timer', show_window),
        pystray.MenuItem('Quit', on_quit)
    )
    icon = pystray.Icon("timer_app", image, "Smart Countdown Timer", menu)
    icon.run()

def on_closing():
    minimize_to_tray()

# ---------------- Save/load state ----------------
def save_state():
    if not is_running:
        delete_state()
        return

    state = {
        "original_seconds": original_seconds,
        "start_timestamp": start_timestamp.isoformat() if start_timestamp else None,
        "is_running": is_running
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        print("Failed to save state:", e)

def load_state():
    global countdown_seconds, original_seconds, is_running, start_timestamp
    if not os.path.exists(STATE_FILE):
        return

    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)

        if not state.get("is_running", False):
            return

        original_seconds = state.get("original_seconds", 0)
        start_timestamp_str = state.get("start_timestamp", None)
        if not start_timestamp_str:
            return

        start_timestamp = datetime.fromisoformat(start_timestamp_str)
        elapsed = (datetime.now() - start_timestamp).total_seconds()
        remaining = original_seconds - int(elapsed)

        if remaining <= 0:
            delete_state()
            return

        countdown_seconds = remaining
        is_running = True

        entry.pack_forget()
        start_btn.pack_forget()
        plus_frame.pack_forget()
        back_btn.pack_forget()
        reset_btn.pack_forget()
        show_reset_btn.pack(pady=5)

        label.config(text=seconds_to_hms(countdown_seconds))
        update_progress()
        root.after(1000, update_timer)

    except Exception as e:
        print("Failed to load timer state:", e)

def delete_state():
    if os.path.exists(STATE_FILE):
        try:
            os.remove(STATE_FILE)
        except Exception as e:
            print("Failed to delete state:", e)

# ---------------- UI Setup ----------------
root = tk.Tk()
root.title("Alvin Timer")
root.geometry("400x330")
root.resizable(False, False)

entry = tk.Entry(root, font=("Courier", 24), justify="center", width=10)
entry.insert(0, "00:00:00")
entry.pack(pady=10)
entry.bind("<KeyRelease>", sanitize_input)
entry.bind("<Return>", lambda e: start_timer())

start_btn = tk.Button(root, text="Start", font=("Arial", 14), command=start_timer)
start_btn.pack(pady=5)

show_reset_btn = tk.Button(root, text="Show Reset", font=("Arial", 14), command=prompt_password_and_show_reset)
reset_btn = tk.Button(root, text="Reset Timer", font=("Arial", 14), command=back_to_setup)

label = tk.Label(root, text="", font=("Arial", 28))
label.pack(pady=10)

progress_bar = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
progress_bar.pack(pady=5)

plus_frame = tk.Frame(root)
plus_frame.pack(pady=10)

tk.Button(plus_frame, text="+5 Min", width=10, command=lambda: add_time(5 * 60)).grid(row=0, column=0, padx=5)
tk.Button(plus_frame, text="+30 Min", width=10, command=lambda: add_time(30 * 60)).grid(row=0, column=1, padx=5)
tk.Button(plus_frame, text="+1 Hour", width=10, command=lambda: add_time(60 * 60)).grid(row=0, column=2, padx=5)

lock_btn = tk.Button(root, text="🔒 Lock PC (Disabled)", font=("Arial", 12), state="disabled", command=lock_windows)
lock_btn.pack(pady=10)

back_btn = tk.Button(root, text="← Back", font=("Arial", 14), command=back_to_setup)

root.protocol("WM_DELETE_WINDOW", on_closing)

# Start tray once
threading.Thread(target=tray_loop, daemon=True).start()

# Listen for "show window" event from second instance
def listen_for_show_event():
    while True:
        win32event.WaitForSingleObject(hEvent, win32event.INFINITE)
        root.after(0, root.deiconify)

threading.Thread(target=listen_for_show_event, daemon=True).start()

load_state()

root.mainloop()

# Release mutex on exit
win32event.ReleaseMutex(mutex)
