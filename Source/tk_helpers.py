# tk_helpers.py
from __future__ import annotations
from typing import Optional
import tkinter as tk

_TK_ROOT: Optional[tk.Tk] = None

def tk_root() -> tk.Tk:
    global _TK_ROOT
    if _TK_ROOT is None:
        _TK_ROOT = tk.Tk()
        _TK_ROOT.withdraw()
        try:
            pass
        except Exception:
            pass
    return _TK_ROOT

def tk_show() -> None:
    r = tk_root()
    try:
        r.deiconify()
        r.lift()
        r.update_idletasks()
        r.withdraw()
    except Exception:
        pass

def tk_destroy_root() -> None:
    global _TK_ROOT
    if _TK_ROOT is not None:
        try:
            _TK_ROOT.destroy()
        except Exception:
            pass
        _TK_ROOT = None
