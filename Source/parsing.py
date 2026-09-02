# parsing.py
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class Frame:
    view: str
    frame_id: int
    t_us: int
    cfg: Dict[str, str] = field(default_factory=dict)
    dataset: str = ""
    meta: Dict[str, str] = field(default_factory=dict)
    cols: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)

def _parse_kv_csv(line: str, prefix: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    parts = line.strip().split(",")
    if not parts or parts[0] != prefix:
        return out
    for tok in parts[1:]:
        if not tok or "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        out[k.strip()] = v.strip()
    return out

def _safe_int(s: str, default: int = 0) -> int:
    try:
        return int(s)
    except Exception:
        return default

def _safe_float(s: str, default: float = float("nan")) -> float:
    try:
        return float(s)
    except Exception:
        return default

class FrameParser:
    """Streaming, line-based parser for BEGIN/CFG/DATA/META/COLS/END frames."""
    def __init__(self) -> None:
        self.cur: Optional[Frame] = None

    def feed_line(self, line: str) -> Optional[Frame]:
        line = line.strip()
        if not line:
            return None

        if line.startswith("BEGIN,"):
            parts = line.split(",")
            if len(parts) >= 4:
                view = parts[1].strip()
                frame_id = _safe_int(parts[2].strip(), 0)
                t_us = _safe_int(parts[3].strip(), 0)
                self.cur = Frame(view=view, frame_id=frame_id, t_us=t_us)
            else:
                self.cur = None
            return None

        if self.cur is None:
            return None

        if line == "END":
            done = self.cur
            self.cur = None
            return done

        if line.startswith("CFG,"):
            self.cur.cfg.update(_parse_kv_csv(line, "CFG"))
            return None

        if line.startswith("DATA,"):
            parts = line.split(",", 1)
            self.cur.dataset = parts[1].strip() if len(parts) > 1 else ""
            return None

        if line.startswith("META,"):
            self.cur.meta.update(_parse_kv_csv(line, "META"))
            return None

        if line.startswith("COLS,"):
            self.cur.cols = [c.strip() for c in line.split(",")[1:]]
            return None

        try:
            row = next(csv.reader([line]))
        except Exception:
            return None

        if row:
            self.cur.rows.append(row)
        return None
