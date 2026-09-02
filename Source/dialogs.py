# dialogs.py
from __future__ import annotations
from typing import Tuple

import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk

from tk_helpers import tk_root
from constants import WINDOWS, DEFAULT_WINDOW, DEFAULT_HARMONICS

def select_serial_port() -> tuple[str, dict]:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        raise RuntimeError("No serial ports found.")

    root = tk_root()
    win = tk.Toplevel(root)
    win.title("Select COM Port")
    win.geometry("400x100")
    win.minsize(400, 100)
    win.resizable(True, False)

    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    w = 420
    h = 170
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 3)
    win.geometry(f"{w}x{h}+{x}+{y}")

    win.attributes("-topmost", True)
    win.after(250, lambda: win.attributes("-topmost", False))
    win.lift()
    win.focus_force()
    win.deiconify()
    win.update()

    selected = tk.StringVar()

    ttk.Label(win, text="Select DMME Analyzer COM Port:").pack(pady=(14, 8), padx=12, anchor="w")
    display = [f"{p.device}  —  {p.description}" for p in ports]

    combo = ttk.Combobox(win, textvariable=selected, values=display, state="readonly", width=60)
    combo.pack(pady=6, padx=12, fill="x")
    combo.current(0)

    result = {"idx": None}

    def on_connect():
        result["idx"] = combo.current()
        win.destroy()

    def on_cancel():
        win.destroy()

    btns = ttk.Frame(win)
    btns.pack(pady=16)

    b_ok = ttk.Button(btns, text="Connect", command=on_connect, width=14)
    b_ok.pack(side="left", padx=8)
    ttk.Button(btns, text="Cancel", command=on_cancel, width=14).pack(side="left", padx=8)

    win.bind("<Return>", lambda _e: on_connect())
    win.bind("<Escape>", lambda _e: on_cancel())
    b_ok.focus_set()

    win.grab_set()
    win.wait_window()

    if result["idx"] is None:
        raise RuntimeError("No port selected.")

    p = ports[result["idx"]]
    match_key = {
        "vid": getattr(p, "vid", None),
        "pid": getattr(p, "pid", None),
        "serial_number": getattr(p, "serial_number", None),
        "location": getattr(p, "location", None),
        "hwid": getattr(p, "hwid", None),
        "description": getattr(p, "description", None),
    }
    return p.device, match_key

def pc_options_dialog(cur_n: int, cur_win: str, cur_h: int) -> Tuple[int, str, int]:
    root = tk_root()
    win = tk.Toplevel(root)
    win.title("PC analysis options")
    win.geometry("360x270")
    win.minsize(360, 270)
    win.resizable(True, True)

    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    w = 360
    h = 270
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 3)
    win.geometry(f"{w}x{h}+{x}+{y}")

    win.attributes("-topmost", True)
    win.after(250, lambda: win.attributes("-topmost", False))
    win.lift()
    win.focus_force()
    win.deiconify()
    win.update()

    n_var = tk.StringVar(value=str(cur_n))
    w_var = tk.StringVar(value=cur_win)
    h_var = tk.StringVar(value=str(cur_h))

    ttk.Label(win, text="FFT points:").pack(anchor="w", padx=12, pady=(10, 4))
    cb_n = ttk.Combobox(win, textvariable=n_var, values=["1024", "2048", "4096"], state="readonly")
    cb_n.pack(fill="x", padx=12, pady=(0, 10))
    cb_n.set(str(cur_n) if str(cur_n) in cb_n["values"] else "4096")

    ttk.Label(win, text="Window:").pack(anchor="w", padx=12, pady=(4, 4))
    cb_w = ttk.Combobox(win, textvariable=w_var, values=list(WINDOWS), state="readonly")
    cb_w.pack(fill="x", padx=12, pady=(0, 10))
    cb_w.set(cur_win if cur_win in WINDOWS else DEFAULT_WINDOW)

    ttk.Label(win, text="Harmonics for THD:").pack(anchor="w", padx=12, pady=(4, 4))
    cb_h = ttk.Combobox(win, textvariable=h_var, values=[str(i) for i in range(1, 21)], state="readonly")
    cb_h.pack(fill="x", padx=12, pady=(0, 14))
    cb_h.set(str(cur_h) if str(cur_h) in cb_h["values"] else str(DEFAULT_HARMONICS))

    out = {"ok": False}

    def ok():
        out["ok"] = True
        win.destroy()

    def cancel():
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", cancel)

    btn = ttk.Frame(win)
    btn.pack(pady=10)

    b_ok = ttk.Button(btn, text="OK", command=ok, width=12)
    b_ok.pack(side="left", padx=10)
    ttk.Button(btn, text="Cancel", command=cancel, width=12).pack(side="left", padx=10)

    win.bind("<Return>", lambda _e: ok())
    win.bind("<Escape>", lambda _e: cancel())
    b_ok.focus_set()

    win.grab_set()
    win.wait_window()

    if not out["ok"]:
        return cur_n, cur_win, cur_h

    try:
        n = int(n_var.get())
    except Exception:
        n = cur_n

    wsel = w_var.get() if w_var.get() in WINDOWS else cur_win

    try:
        hsel = int(h_var.get())
    except Exception:
        hsel = cur_h

    n = max(256, min(n, 262144))
    hsel = max(1, min(hsel, 20))
    return n, wsel, hsel
