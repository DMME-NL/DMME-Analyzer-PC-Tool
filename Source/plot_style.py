# plot_style.py
from __future__ import annotations

from matplotlib.ticker import LogLocator, NullFormatter, ScalarFormatter

def _apply_plot_style(ax) -> None:
    ax.grid(True, which="major")
    ax.grid(True, which="minor", alpha=0.35)
    ax.set_facecolor("white")
    for spine in ax.spines.values():
        spine.set_linewidth(1)

def style_axes(ax, plot_kind: str) -> None:
    if plot_kind in ("freq_db", "fft_db"):
        ax.set_xscale("log")
        ax.xaxis.set_major_locator(LogLocator(base=10.0, numticks=12))
        ax.xaxis.set_minor_locator(LogLocator(base=10.0, subs=(2,3,4,5,6,7,8,9), numticks=100))
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.get_xaxis().set_major_formatter(ScalarFormatter())
        ax.ticklabel_format(axis="x", style="plain")
        ax.margins(x=0.02, y=0.06)
    else:
        ax.set_xscale("linear")
        ax.margins(x=0.02, y=0.06)

    ax.set_yscale("linear")
    _apply_plot_style(ax)
