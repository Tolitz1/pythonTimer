import tkinter as tk
from tkinter import ttk
import ctypes
from PIL import Image, ImageDraw
import pystray
import threading
import sys

# Globals
countdown_seconds = 0
original_seconds = 0
is_running = False
icon = None  # pystray icon reference

def sanitize_input(event=None):
    raw = ''.join(filter(str.isdigit, entry.get()))[:6]  # Only digits, max 6
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

def start_timer():
    global countdown_seconds, original_seconds, is_running

    countdown_seconds = hms_to_seconds(entry.get())
    original_seconds = countdown_seconds
    if countdown_seconds <= 0:
        label.config(text="Enter time")
        return

    entry.pack_forget()
    start_btn.pack_forget()
    plus_frame.pack_forget()
    back_btn.pack_forget()  # Just in case

    label.config(text=seconds_to_hms(countdown_seconds))
    update_progress()
    is_running = True
    update_timer()

def update_timer():
    global countdown_seconds, is_running
    if is_running and countdown_seconds >= 0:
        label.config(text=seconds_to_hms(countdown_seconds))
        update_progress()
        if countdown_seconds == 0:
            label.config(text="Time's up!")
            lock_windows()
            is_running = False
            back_btn.pack(pady=10)  # Show Back button when done
        else:
            countdown_seconds -= 1
            root.after(1000, update_timer)

def add_time(seconds):
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
    global countdown_seconds, original_seconds, is_running
    countdown_seconds = 0
    original_seconds = 0
    is_running = False

    label.config(text="")
    back_btn.pack_forget()

    entry.delete(0, tk.END)
    entry.insert(0, "00:00:00")
    entry.pack(pady=10)
    start_btn.pack(pady=5)
    plus_frame.pack(pady=10)
    progress_bar['value'] = 0


# ========== System Tray Integration ==========

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
    root.after(0, root.destroy)

def show_window(icon, item):
    icon.visible = False
    icon.stop()
    root.after(0, root.deiconify)

def minimize_to_tray():
    root.withdraw()
    image = create_image()
    menu = pystray.Menu(
        pystray.MenuItem('Open Timer', show_window),
        pystray.MenuItem('Quit', on_quit)
    )
    global icon
    icon = pystray.Icon("timer_app", image, "Smart Countdown Timer", menu)
    icon.run()

def on_closing():
    threading.Thread(target=minimize_to_tray, daemon=False).start()

# ========== Main Window Setup ==========

root = tk.Tk()
root.title("Alvin Timer")
root.geometry("400x330")
root.resizable(False, False)

# Entry field
entry = tk.Entry(root, font=("Courier", 24), justify="center", width=10)
entry.insert(0, "00:00:00")
entry.pack(pady=10)
entry.bind("<KeyRelease>", sanitize_input)
entry.bind("<Return>", lambda e: start_timer())

# Start button
start_btn = tk.Button(root, text="Start", font=("Arial", 14), command=start_timer)
start_btn.pack(pady=5)

# Countdown label
label = tk.Label(root, text="", font=("Arial", 28))
label.pack(pady=10)

# Progress bar
progress_bar = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
progress_bar.pack(pady=5)

# Add-time buttons
plus_frame = tk.Frame(root)
plus_frame.pack(pady=10)

tk.Button(plus_frame, text="+5 Min", width=10, command=lambda: add_time(5 * 60)).grid(row=0, column=0, padx=5)
tk.Button(plus_frame, text="+30 Min", width=10, command=lambda: add_time(30 * 60)).grid(row=0, column=1, padx=5)
tk.Button(plus_frame, text="+1 Hour", width=10, command=lambda: add_time(60 * 60)).grid(row=0, column=2, padx=5)

# Lock PC Button (disabled)
lock_btn = tk.Button(root, text="🔒 Lock PC (Disabled)", font=("Arial", 12), state="disabled", command=lock_windows)
lock_btn.pack(pady=10)

# Back button (hidden initially)
back_btn = tk.Button(root, text="← Back", font=("Arial", 14), command=back_to_setup)

# Override window close to minimize to tray
root.protocol("WM_DELETE_WINDOW", on_closing)

# Start app
# root.iconbitmap("timer.ico")
root.mainloop()
