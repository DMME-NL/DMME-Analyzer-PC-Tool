# export_csv.py
from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from tkinter import filedialog

from parsing import Frame
from tk_helpers import tk_root
from data_convert import frame_to_xy
from fft_avg import FFTAverager

@dataclass
class Trace:
    view: str
    frame_id: int
    t_us: int
    x: List[float]
    y: List[float]
    xlabel: str
    ylabel: str
    plot_kind: str
    cfg: Dict[str, str]
    meta: Dict[str, str]
    label: str = ""

def make_trace_from_frame(fr: Frame) -> Optional[Trace]:
    x, y, xlabel, ylabel, plot_kind = frame_to_xy(fr)
    if not x or not y:
        return None
    return Trace(
        view=fr.view,
        frame_id=fr.frame_id,
        t_us=fr.t_us,
        x=x,
        y=y,
        xlabel=xlabel,
        ylabel=ylabel,
        plot_kind=plot_kind,
        cfg=dict(fr.cfg),
        meta=dict(fr.meta),
        label="",
    )

def export_all_csv(
    latest: Dict[str, Frame],
    history: Dict[str, List[Trace]],
    fft_avg: FFTAverager,
    pc_fft_frame: Optional[Frame],
    pc_enable: bool,
) -> None:
    root = tk_root()
    fn = filedialog.asksaveasfilename(
        parent=root,
        title="Export ALL views CSV (wide)",
        defaultextension=".csv",
        filetypes=[("CSV", "*.csv")],
        initialfile="all_views_wide.csv",
    )
    if not fn:
        return

    def cur_trace_for(view: str) -> Optional[Trace]:
        fr: Optional[Frame]
        if pc_enable and view == "fft_bins" and pc_fft_frame is not None:
            fr = pc_fft_frame
        else:
            fr = latest.get(view)

        if fr is None:
            return None

        tr = make_trace_from_frame(fr)
        if tr is None:
            return None

        if tr.view == "fft_bins" and fft_avg.n > 1:
            x2, y2 = fft_avg.push(tr.x, tr.y)
            tr.x, tr.y = x2, y2
        tr.label = "current"
        return tr

    def _same_x(a: List[float], b: List[float]) -> bool:
        if len(a) != len(b):
            return False
        if not a:
            return True
        for idx in (0, len(a) // 2, len(a) - 1):
            if abs(a[idx] - b[idx]) > 1e-12 * max(1.0, abs(a[idx]), abs(b[idx])):
                return False
        return True

    def write_view_wide(w: csv.writer, view: str) -> None:
        hist = list(history.get(view, []))
        cur = cur_trace_for(view)

        traces: List[Trace] = []
        traces.extend(hist)
        if cur is not None:
            traces.append(cur)
        if not traces:
            return

        x_ref = (cur.x if cur is not None else traces[0].x)
        n = len(x_ref)

        kept: List[Tuple[str, Trace]] = []
        skipped: List[Tuple[str, Trace]] = []

        for i, tr in enumerate(hist):
            name = (tr.label or f"history_{i+1}").strip()
            (kept if _same_x(tr.x, x_ref) else skipped).append((name, tr))
        if cur is not None:
            name = (cur.label or "current").strip()
            (kept if _same_x(cur.x, x_ref) else skipped).append((name, cur))

        w.writerow(["VIEW", view])
        w.writerow(["xlabel", traces[-1].xlabel, "ylabel", traces[-1].ylabel, "plot_kind", traces[-1].plot_kind])
        w.writerow(["#FORMAT", "wide: x, history..., current"])
        if skipped:
            w.writerow(["#WARNING", "skipped traces due to x mismatch"])
            for name, tr in skipped:
                w.writerow(["#SKIPPED", name, "len", len(tr.x), "frame_id", tr.frame_id])

        ref_cfg = (cur.cfg if cur is not None else kept[-1][1].cfg)
        ref_meta = (cur.meta if cur is not None else kept[-1][1].meta)

        w.writerow(["#CFG"])
        for k in sorted(ref_cfg.keys()):
            w.writerow([k, ref_cfg[k]])
        w.writerow(["#META"])
        for k in sorted(ref_meta.keys()):
            w.writerow([k, ref_meta[k]])
        w.writerow([])

        col_names = ["x"] + [name for (name, _tr) in kept]
        w.writerow(["COLS"] + col_names)

        y_cols = [tr.y for (_name, tr) in kept]
        for i in range(n):
            row = [f"{x_ref[i]:.12g}"]
            for yv in y_cols:
                row.append(f"{yv[i]:.12g}" if i < len(yv) else "")
            w.writerow(row)

        w.writerow([])
        w.writerow(["END_VIEW", view])
        w.writerow([])

    views = sorted(set(list(history.keys()) + list(latest.keys()) + ["fft_bins"]))
    with open(fn, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["#RP2040_ANALYZER_EXPORT", "all_views_wide"])
        w.writerow(["#views"] + views)
        w.writerow([])
        for view in views:
            write_view_wide(w, view)
