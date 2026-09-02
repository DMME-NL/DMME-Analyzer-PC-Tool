# data_convert.py
from __future__ import annotations
from typing import List, Tuple

import csv
from parsing import Frame, _safe_float

def _dataset_name(frame: Frame) -> str:
    return (frame.dataset or frame.view or "").strip()

def frame_to_xy(frame: Frame) -> Tuple[List[float], List[float], str, str, str]:
    ds = _dataset_name(frame)

    cols = frame.cols
    col_index = {name: i for i, name in enumerate(cols)}

    def get(row: List[str], name: str) -> str:
        i = col_index.get(name, -1)
        if i < 0 or i >= len(row):
            return ""
        return row[i]

    x: List[float] = []
    y: List[float] = []

    if ds in ("sweep", "thd_sweep") or frame.view in ("sweep", "thd_sweep"):
        for r in frame.rows:
            fhz = _safe_float(get(r, "f_hz"))
            ydb = _safe_float(get(r, "y_db"))
            valid = get(r, "valid")
            if valid and valid.strip() == "0":
                continue
            if fhz == fhz and ydb == ydb and fhz > 0:
                x.append(fhz)
                y.append(ydb)
        return x, y, "Frequency (Hz)", "Level (dB / dBu)", "freq_db"

    if ds == "xfer" or frame.view == "xfer":
        for r in frame.rows:
            xv = _safe_float(get(r, "x"))
            ydb = _safe_float(get(r, "y_db"))
            valid = get(r, "valid")
            if valid and valid.strip() == "0":
                continue
            if xv == xv and ydb == ydb:
                x.append(xv)
                y.append(ydb)
        return x, y, "Input (dBu)", "Output (dBu)", "xfer"

    if ds == "fft_bins" or frame.view == "fft_bins":
        pts: List[Tuple[float, float]] = []
        for r in frame.rows:
            fhz = _safe_float(get(r, "f_hz"))
            dbu = _safe_float(get(r, "dbu"))
            if not (fhz == fhz and dbu == dbu):
                continue
            if fhz <= 0:
                continue
            if dbu < -300 or dbu > 200:
                continue
            pts.append((fhz, dbu))
        pts.sort(key=lambda p: p[0])
        return [p[0] for p in pts], [p[1] for p in pts], "Frequency (Hz)", "Level (dBu)", "fft_db"

    if ds == "wave_screen" or frame.view == "wave":
        for r in frame.rows:
            ts = _safe_float(get(r, "t_s"))
            v = _safe_float(get(r, "v"))
            if ts == ts and v == v:
                x.append(ts)
                y.append(v)
        return x, y, "Time (s)", "Voltage (V)", "time"

    for r in frame.rows:
        if len(r) >= 2:
            a = _safe_float(r[0])
            b = _safe_float(r[1])
            if a == a and b == b:
                x.append(a)
                y.append(b)
    return x, y, "X", "Y", "other"
