#!/usr/bin/env python3

# Build script for Windows (run from cmd.exe):
# Path\RP2040-Analyzer\Code\.venv\Scripts\python.exe -m pip install pyinstaller
# Path\RP2040-Analyzer\Code\.venv\Scripts\python.exe -m PyInstaller ^
#   --onefile ^
#   --noconsole ^
#   --name DMME_Analyzer ^
#   --icon "Icons\app_icon.ico" ^
#   main.py

# main.py
from __future__ import annotations

import atexit
import os
import argparse
import queue
import threading
import time
from typing import Dict, List, Optional

# ---- backend must be set before importing pyplot ----
import matplotlib
matplotlib.use("TkAgg")

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.widgets import Button, TextBox, CheckButtons

from constants import (
    BAUD, DB_FLOOR,
    HIST_VIEWS, VIEW_TITLES, HIST_ALPHA, HIST_LW, HIST_CMAP_NAME,
    MAX_LABEL_BOXES,
    DEFAULT_FFT_N, DEFAULT_WINDOW, DEFAULT_HARMONICS,
    PC_ANALYSIS_STALE_S,
)
from parsing import Frame, _safe_float
from serial_io import serial_reader
from dialogs import select_serial_port, pc_options_dialog
from data_convert import frame_to_xy
from fft_avg import FFTAverager
from raw_analysis import _is_raw_frame, _raw_frame_to_samples, _analyze_raw_pc
from info_panel import _render_info_panel
from plot_style import style_axes
from export_csv import Trace, make_trace_from_frame, export_all_csv
from tk_helpers import tk_destroy_root

def width_ratios_for_table_cap(fig_w_in: float, table_cap_in: float):
    left_in = min(table_cap_in, 0.45 * fig_w_in)
    right_in = max(1.0, fig_w_in - left_in)
    return left_in, right_in

def main() -> None:
    try:
        port, match_key = select_serial_port()
    except Exception as e:
        print(f"Port selection failed: {e}")
        return

    ap = argparse.ArgumentParser()
    ap.add_argument("--fps", type=float, default=60.0, help="Max UI loop rate (draws only when dirty)")
    ap.add_argument("--table_cap_in", type=float, default=3.2, help="Max left panel width (inches)")
    ap.add_argument("--queue_max", type=int, default=500, help="Serial frame queue max depth (drop-oldest)")
    ap.add_argument("--max_drain", type=int, default=200, help="Max frames drained per UI tick")
    args = ap.parse_args()

    q_frames: "queue.Queue[Frame]" = queue.Queue(maxsize=max(50, args.queue_max))
    stop_evt = threading.Event()
    t = threading.Thread(
        target=serial_reader,
        args=(port, match_key, BAUD, q_frames, stop_evt),
        daemon=True,
    )
    t.start()

    latest: Dict[str, Frame] = {}
    selected_view = "sweep"
    auto_follow = True
    autoscale = True
    freeze_ylim = False
    show_history = True

    fft_avg = FFTAverager(n=1)
    history: Dict[str, List[Trace]] = {v: [] for v in HIST_VIEWS}

    pc_fft_n = DEFAULT_FFT_N
    pc_window = DEFAULT_WINDOW
    pc_harmonics = DEFAULT_HARMONICS
    pc_enable = False
    pc_fft_frame: Optional[Frame] = None
    pc_last_raw_t = 0.0

    fig_w, fig_h = 14.0, 7.6
    fig = plt.figure(figsize=(fig_w, fig_h))

    closing = False
    def shutdown():
        nonlocal closing
        if closing:
            return
        closing = True
        stop_evt.set()
        try:
            plt.close("all")
        except Exception:
            pass
        tk_destroy_root()

    fig.canvas.mpl_connect("close_event", lambda _evt: shutdown())
    atexit.register(shutdown)

    left_in, right_in = width_ratios_for_table_cap(fig_w, args.table_cap_in)
    outer = GridSpec(1, 2, width_ratios=[left_in, right_in], wspace=0.20, figure=fig)

    left = outer[0, 0].subgridspec(2, 1, height_ratios=[0.20, 0.80], hspace=0.03)
    ax_ctrl = fig.add_subplot(left[0, 0])
    ax_info = fig.add_subplot(left[1, 0])
    ax_ctrl.set_axis_off()
    ax_info.set_axis_off()

    right = outer[0, 1].subgridspec(2, 1, height_ratios=[0.82, 0.18], hspace=0.10)
    ax_plot = fig.add_subplot(right[0, 0])
    ax_lbl = fig.add_subplot(right[1, 0])
    ax_lbl.set_axis_off()

    fig.subplots_adjust(left=0.01, right=0.995, bottom=0.05, top=0.96)

    (line,) = ax_plot.plot([], [], linestyle="-", linewidth=1.7)
    style_axes(ax_plot, "freq_db")

    hist_lines: List = []
    history_dirty = True
    labels_dirty = True
    last_plot_kind: Optional[str] = None

    label_boxes: List[TextBox] = []
    label_box_axes: List = []
    cmap = plt.get_cmap(HIST_CMAP_NAME)

    plt.ion()
    plt.show(block=False)
    fig.canvas.draw_idle()
    plt.pause(0.05)

    ax_ctrl.text(0.02, 0.92, "Controls", fontsize=10, weight="bold", transform=ax_ctrl.transAxes)

    def add_box_in(ax_panel, relx, rely, relw, relh):
        pos = ax_panel.get_position()
        x0 = pos.x0 + relx * pos.width
        y0 = pos.y0 + rely * pos.height
        w = relw * pos.width
        h = relh * pos.height
        return fig.add_axes([x0, y0, w, h])

    ax_ctrl.text(0.02, 0.62, "FFT Avg (N):", fontsize=9, transform=ax_ctrl.transAxes)
    ax_avg = add_box_in(ax_ctrl, 0.32, 0.54, 0.16, 0.30)
    tb_avg = TextBox(ax_avg, "", initial=str(fft_avg.n))
    tb_avg.label.set_visible(False)

    ax_chk = add_box_in(ax_ctrl, 0.52, 0.52, 0.45, 0.34)
    chk = CheckButtons(ax_chk, ["Show history"], [show_history])

    ax_btn_keep = add_box_in(ax_ctrl, 0.02, 0.10, 0.18, 0.35)
    ax_btn_clear = add_box_in(ax_ctrl, 0.22, 0.10, 0.18, 0.35)
    ax_btn_export = add_box_in(ax_ctrl, 0.42, 0.10, 0.18, 0.35)
    ax_btn_pcopts = add_box_in(ax_ctrl, 0.66, 0.10, 0.30, 0.35)

    btn_keep = Button(ax_btn_keep, "Keep")
    btn_clear = Button(ax_btn_clear, "Clear")
    btn_export = Button(ax_btn_export, "Export")
    btn_pcopts = Button(ax_btn_pcopts, "PC opts")

    avg_updating = False
    last_info_t = 0.0

    def compute_ylim(yvals, pad_frac=0.08, floor=None):
        y0 = min(yvals)
        y1 = max(yvals)
        if y0 == y1:
            y0 -= 1.0
            y1 += 1.0
        span = y1 - y0
        pad = span * pad_frac
        y0 -= pad
        y1 += pad
        if floor is not None:
            y0 = max(y0, floor)
        return y0, y1

    def merged_y_for_autoscale(cur_y, plot_kind):
        yy = list(cur_y)
        if show_history and selected_view in history:
            for tr in history[selected_view]:
                if tr.plot_kind == plot_kind:
                    yy.extend(tr.y)
        return yy

    def rebuild_label_boxes():
        nonlocal label_boxes, label_box_axes, labels_dirty
        for a in label_box_axes:
            try:
                a.remove()
            except Exception:
                pass
        label_boxes = []
        label_box_axes = []

        ax_lbl.clear()
        ax_lbl.set_axis_off()

        traces = history.get(selected_view, [])
        n = min(len(traces), MAX_LABEL_BOXES)

        title = f"History labels ({VIEW_TITLES.get(selected_view, selected_view)})"
        ax_lbl.text(0.01, 0.90, title, fontsize=9, weight="bold", transform=ax_lbl.transAxes)

        if n == 0:
            ax_lbl.text(0.01, 0.55, "No history traces. Click Keep to add.", fontsize=9, transform=ax_lbl.transAxes)
            labels_dirty = False
            return

        top_y = 0.72
        row_h = 0.22
        if n > 4:
            row_h = 0.70 / max(1, n)

        for i in range(n):
            y = top_y - i * row_h
            color = cmap(i % cmap.N)
            ax_lbl.plot([0.01, 0.03], [y, y], transform=ax_lbl.transAxes, linewidth=4,
                        color=color, solid_capstyle="round")
            ax_lbl.text(0.035, y, f"H{i+1}:", fontsize=9, va="center", transform=ax_lbl.transAxes)

            ax_tb = add_box_in(ax_lbl, 0.11, y - 0.08, 0.40, 0.16)
            tb = TextBox(ax_tb, "", initial=(traces[i].label or f"{selected_view}_{i+1}"))
            tb.label.set_visible(False)

            def _make_submit(idx):
                def _on_submit(text):
                    tlist = history.get(selected_view, [])
                    if 0 <= idx < len(tlist):
                        tlist[idx].label = (text or "").strip()
                return _on_submit

            tb.on_submit(_make_submit(i))

            label_boxes.append(tb)
            label_box_axes.append(ax_tb)

        labels_dirty = False

    def on_avg_submit(text):
        nonlocal avg_updating
        if avg_updating:
            return
        try:
            n = int(text.strip())
        except Exception:
            n = 1
        n = max(1, min(n, 128))
        fft_avg.set_n(n)
        if text.strip() != str(n):
            avg_updating = True
            try:
                tb_avg.set_val(str(n))
            finally:
                avg_updating = False

    def on_chk(_label):
        nonlocal show_history, history_dirty
        show_history = chk.get_status()[0]
        history_dirty = True

    def on_pc_opts(_evt):
        nonlocal pc_fft_n, pc_window, pc_harmonics, history_dirty, labels_dirty
        pc_fft_n, pc_window, pc_harmonics = pc_options_dialog(pc_fft_n, pc_window, pc_harmonics)
        history_dirty = True
        labels_dirty = True

    tb_avg.on_submit(on_avg_submit)
    chk.on_clicked(on_chk)
    btn_pcopts.on_clicked(on_pc_opts)

    def on_keep(_evt):
        nonlocal history_dirty, labels_dirty

        fr = pc_fft_frame if (selected_view == "fft_bins" and pc_enable and pc_fft_frame is not None) else latest.get(selected_view)
        if fr is None or fr.view not in HIST_VIEWS:
            return

        tr = make_trace_from_frame(fr)
        if tr is None:
            return

        # If we're in FFT view and averaging is enabled, keep the *displayed* (already averaged) data
        if tr.view == "fft_bins" and fft_avg.n > 1:
            xd = list(line.get_xdata())
            yd = list(line.get_ydata())
            if xd and yd and len(xd) == len(yd):
                tr.x = xd
                tr.y = yd

        tr.label = f"{selected_view}_{len(history[selected_view]) + 1}"
        history[selected_view].append(tr)
        history_dirty = True
        labels_dirty = True


    def on_clear(_evt):
        nonlocal history_dirty, labels_dirty
        if selected_view in history:
            history[selected_view].clear()
            history_dirty = True
            labels_dirty = True

    def on_export(_evt):
        export_all_csv(latest, history, fft_avg, pc_fft_frame, pc_enable)

    btn_keep.on_clicked(on_keep)
    btn_clear.on_clicked(on_clear)
    btn_export.on_clicked(on_export)

    dirty = True
    last_tick = time.time()
    printed_no_data = False

    while plt.fignum_exists(fig.number) and not stop_evt.is_set():
        got_new = False

        for _ in range(max(1, args.max_drain)):
            try:
                fr = q_frames.get_nowait()
            except queue.Empty:
                break

            if fr.view:
                latest[fr.view] = fr
            if fr.dataset:
                latest[fr.dataset] = fr
            if not fr.view and not fr.dataset:
                latest["unknown"] = fr

            got_new = True

            if selected_view not in latest:
                if "sweep" in latest:
                    selected_view = "sweep"
                elif "fft_bins" in latest:
                    selected_view = "fft_bins"
                elif "raw" in latest:
                    selected_view = "raw"
                else:
                    selected_view = next(iter(latest.keys()))
                history_dirty = True
                labels_dirty = True

            if _is_raw_frame(fr):
                pc_last_raw_t = time.time()
                pc_enable = True

                try:
                    x_samp, fs_hz = _raw_frame_to_samples(fr)
                    if x_samp is None or x_samp.size == 0:
                        raise RuntimeError("empty raw frame")

                    fullscale_vrms = _safe_float(fr.cfg.get("fullscale_vrms", ""), float("nan"))
                    if not (fullscale_vrms == fullscale_vrms) or fullscale_vrms <= 0:
                        fullscale_vrms = 1.0

                    band_lo = _safe_float(fr.cfg.get("min_hz", ""), 20.0)
                    band_hi = _safe_float(fr.cfg.get("max_hz", ""), 20000.0)

                    res = _analyze_raw_pc(
                        np.asarray(x_samp, dtype=np.float64),
                        fs_hz,
                        pc_fft_n,
                        pc_window,
                        pc_harmonics,
                        fullscale_vrms,
                        band_lo_hz=band_lo,
                        band_hi_hz=band_hi,
                    )

                    freqs = res["f_hz"]
                    dbu = res["dbu"]
                    metrics = res["metrics"]

                    pc_fft_frame = Frame(view="fft_bins", frame_id=fr.frame_id, t_us=fr.t_us)
                    pc_fft_frame.dataset = "fft_bins"
                    pc_fft_frame.meta = dict(fr.meta)
                    pc_fft_frame.cfg = dict(fr.cfg)

                    pc_fft_frame.cfg["pc_src"] = "raw_single"
                    if isinstance(metrics, dict):
                        pc_fft_frame.cfg.update({str(k): str(v) for k, v in metrics.items()})

                    pc_fft_frame.cols = ["bin", "f_hz", "dbu"]
                    pc_fft_frame.rows = [
                        [str(k), f"{float(freqs[k]):.6f}", f"{float(dbu[k]):.9f}"]
                        for k in range(1, len(freqs))
                    ]

                    selected_view = "fft_bins"
                    history_dirty = True
                    labels_dirty = True

                except Exception as e:
                    print("PC analysis error:", e)
                    pc_fft_frame = None

            if auto_follow and not (pc_enable and selected_view == "fft_bins" and pc_fft_frame is not None):
                new_view = fr.view or fr.dataset or selected_view
                if new_view != selected_view and new_view in latest:
                    selected_view = new_view
                    history_dirty = True
                    labels_dirty = True

        if got_new:
            dirty = True
            printed_no_data = False

        now = time.time()

        if pc_enable and (now - pc_last_raw_t) > PC_ANALYSIS_STALE_S:
            pc_enable = False
            pc_fft_frame = None
            history_dirty = True
            labels_dirty = True

        min_dt = 1.0 / max(args.fps, 1e-3)
        if (now - last_tick) < min_dt and not dirty and not history_dirty and not labels_dirty:
            plt.pause(0.01)
            continue
        last_tick = now

        if history_dirty or labels_dirty:
            dirty = True

        if not dirty:
            plt.pause(0.01)
            continue
        dirty = False

        pc_active_here = False
        if selected_view == "fft_bins" and pc_enable and pc_fft_frame is not None:
            fr_to_plot = pc_fft_frame
            pc_active_here = True
        else:
            fr_to_plot = latest.get(selected_view)

        if fr_to_plot is None:
            if not printed_no_data:
                print("No frames for selected_view =", selected_view, "available keys =", sorted(latest.keys())[:20])
                printed_no_data = True
            ax_plot.set_title(f"{VIEW_TITLES.get(selected_view, selected_view)} (waiting...)")
            if labels_dirty:
                rebuild_label_boxes()
            fig.canvas.draw_idle()
            plt.pause(0.01)
            continue

        x, y, xlabel, ylabel, plot_kind = frame_to_xy(fr_to_plot)
        if not x or not y:
            plt.pause(0.01)
            continue

        if plot_kind == "fft_db":
            x, y = fft_avg.push(x, y)

        if plot_kind != last_plot_kind:
            style_axes(ax_plot, plot_kind)
            last_plot_kind = plot_kind
            history_dirty = True

        line.set_data(x, y)
        ax_plot.set_xlabel(xlabel)
        ax_plot.set_ylabel(ylabel)

        try:
            if plot_kind in ("freq_db", "fft_db"):
                xmin = max(min(x), 1e-6)
                xmax = max(x)
                if xmin < xmax:
                    ax_plot.set_xlim(xmin, xmax)
            else:
                ax_plot.set_xlim(min(x), max(x))
        except Exception:
            pass

        if autoscale and not freeze_ylim:
            floor = DB_FLOOR if plot_kind in ("freq_db", "fft_db") else None
            pad = 0.10 if plot_kind in ("freq_db", "fft_db") else 0.08
            y_all = merged_y_for_autoscale(y, plot_kind)
            if y_all:
                y0, y1 = compute_ylim(y_all, pad_frac=pad, floor=floor)
                ax_plot.set_ylim(y0, y1)

        tag_pc = " [PC]" if pc_active_here else ""
        ax_plot.set_title(
            f"{VIEW_TITLES.get(selected_view, selected_view)}{tag_pc}"
            f"   {'[freezeY]' if freeze_ylim else ''}"
            f"   {'[FFTavg=%d]' % fft_avg.n if plot_kind == 'fft_db' and fft_avg.n > 1 else ''}"
        )

        if now - last_info_t > 0.10:
            _render_info_panel(ax_info, fr_to_plot)
            last_info_t = now

        if history_dirty:
            for hl in hist_lines:
                try:
                    hl.remove()
                except Exception:
                    pass
            hist_lines = []

            if show_history and selected_view in history:
                for i, tr in enumerate(history[selected_view]):
                    if tr.plot_kind != plot_kind:
                        continue
                    color = cmap(i % cmap.N)
                    (hl,) = ax_plot.plot(
                        tr.x, tr.y,
                        linestyle="-",
                        linewidth=HIST_LW,
                        alpha=HIST_ALPHA,
                        color=color,
                    )
                    hist_lines.append(hl)

            history_dirty = False

        if labels_dirty:
            rebuild_label_boxes()

        fig.canvas.draw_idle()
        plt.pause(0.001)

    shutdown()
    t.join(timeout=2.0)
    if t.is_alive():
        os._exit(0)

if __name__ == "__main__":
    main()
