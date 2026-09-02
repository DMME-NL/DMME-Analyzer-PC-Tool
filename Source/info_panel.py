# info_panel.py
from __future__ import annotations
from typing import List, Tuple

from parsing import Frame, _safe_float, _safe_int
from constants import VIEW_TITLES
from data_convert import _dataset_name

def _fmt_float(val: str, ndp: int = 3) -> str:
    f = _safe_float(val, float("nan"))
    if f != f:
        return ""
    if abs(f) < 0.5 * (10 ** -ndp):
        f = 0.0
    return f"{f:.{ndp}f}"

def _fmt_int(val: str) -> str:
    if val == "":
        return ""
    return str(_safe_int(val, 0))

def _build_info_groups(frame: Frame) -> List[Tuple[str, List[Tuple[str, str, str]]]]:
    cfg = frame.cfg
    def g(k: str) -> str:
        return cfg.get(k, "")

    view = frame.view
    ds = _dataset_name(frame)

    groups: List[Tuple[str, List[Tuple[str, str, str]]]] = []

    session_rows = [
        ("View", VIEW_TITLES.get(view, view), ""),
        ("Dataset", ds, ""),
        ("Frame", str(frame.frame_id), ""),
        ("t_us", str(frame.t_us), "us"),
        ("Version", g("ver"), ""),
    ]
    if g("pc_src"):
        session_rows.append(("PC src", g("pc_src"), ""))
        session_rows.append(("PC FFT N", g("pc_fft_n"), ""))
        session_rows.append(("PC win", g("pc_window"), ""))
        session_rows.append(("PC harm", g("pc_harm"), ""))

    groups.append(("Session", session_rows))

    groups.append(("Acquisition", [
        ("Fs", _fmt_int(g("fs_hz")), "Hz"),
        ("Analyze N", _fmt_int(g("analyze_n")), "samples"),
        ("Fmin", _fmt_int(g("min_hz")), "Hz"),
        ("Fmax", _fmt_int(g("max_hz")), "Hz"),
        ("Harmonics", _fmt_int(g("harm")), ""),
        ("Input range", g("in_range"), ""),
        ("Output range", g("out_range"), ""),
        ("Termination", g("term"), ""),
    ]))

    groups.append(("Generator / Measurement", [
        ("Gen freq", _fmt_float(g("gen_f_hz"), 3), "Hz"),
        ("Gen level", _fmt_float(g("gen_lvl_dbu"), 2), "dBu"),
        ("Measured", _fmt_float(g("meas_dbu"), 3), "dBu"),
        ("f0", _fmt_float(g("f0_hz"), 3), "Hz"),
    ]))

    groups.append(("Distortion / Noise", [
        ("THD", _fmt_float(g("thd_db"), 3), "dB"),
        ("THD", _fmt_float(g("thd_pct"), 4), "%"),
        ("THD+N", _fmt_float(g("thdn_db"), 3), "dB"),
        ("THD+N", _fmt_float(g("thdn_pct"), 4), "%"),
        ("Noise", _fmt_float(g("noise_dbu"), 3), "dBu"),
        ("SNR", _fmt_float(g("snr_db"), 3), "dB"),
        ("SINAD", _fmt_float(g("sinad_db"), 3), "dB"),
    ]))

    return groups

def _render_info_panel(ax, frame: Frame) -> None:
    ax.clear()
    ax.set_axis_off()

    groups = _build_info_groups(frame)

    def rows_to_draw():
        out = []
        for gtitle, rows in groups:
            rr = [(n, v, u) for (n, v, u) in rows if v != ""]
            if not rr:
                continue
            out.append(("__HEADER__", gtitle, "", ""))
            for n, v, u in rr:
                out.append(("__ROW__", n, v, u))
            out.append(("__SPACE__", "", "", ""))
        return out

    lines = rows_to_draw()
    if not lines:
        return

    left = 0.04
    right = 0.98
    top = 0.99
    bottom = 0.01

    x_name = left
    x_val = 0.60
    x_unit = 0.90

    n_lines = len(lines) + 2
    dy = (top - bottom) / n_lines
    dy = min(dy, 0.040)
    dy = max(dy, 0.018)

    y = top
    ax.text(x_name, y, "Name", ha="left", va="top", fontsize=9, weight="bold", transform=ax.transAxes)
    ax.text(x_val,  y, "Value", ha="left", va="top", fontsize=9, weight="bold", transform=ax.transAxes)
    ax.text(x_unit, y, "Unit", ha="left", va="top", fontsize=9, weight="bold", transform=ax.transAxes)
    y -= dy
    ax.plot([left, right], [y, y], transform=ax.transAxes, linewidth=1)
    y -= dy * 0.6

    for kind, a, b, c in lines:
        if y < bottom:
            break
        if kind == "__HEADER__":
            ax.text(left, y, a, ha="left", va="top", fontsize=10, weight="bold", transform=ax.transAxes)
            y -= dy
        elif kind == "__ROW__":
            ax.text(x_name, y, a, ha="left", va="top", fontsize=9, transform=ax.transAxes)
            ax.text(x_val,  y, b, ha="left", va="top", fontsize=9, transform=ax.transAxes)
            ax.text(x_unit, y, c, ha="left", va="top", fontsize=9, transform=ax.transAxes)
            y -= dy
        else:
            y -= dy * 0.35
