# raw_analysis.py
from __future__ import annotations

import math
from typing import Dict, Tuple

import numpy as np

from constants import DBU_REF_VRMS, PC_RAW_DATASETS, PC_RAW_VIEWS
from parsing import Frame, _safe_float

def _dataset_name(fr: Frame) -> str:
    return (fr.dataset or fr.view or "").strip()

def _is_raw_frame(fr: Frame) -> bool:
    ds = _dataset_name(fr).lower()
    vw = (fr.view or "").lower()

    if vw in ("sweep", "thd_sweep", "xfer", "fft_bins", "wave"):
        return False
    if ds in ("sweep", "thd_sweep", "xfer", "fft_bins", "wave_screen"):
        return False

    if ds in PC_RAW_DATASETS or vw in PC_RAW_VIEWS:
        return True

    cols = [c.lower() for c in (fr.cols or [])]
    if (("sample" in cols) or ("q24" in cols) or ("s_q24" in cols)) and ("v" not in cols and "t_s" not in cols):
        return True

    return False

def _raw_frame_to_samples(fr: Frame) -> Tuple[np.ndarray, float]:
    fs = _safe_float(fr.cfg.get("fs_hz", ""), float("nan"))
    if not (fs == fs) or fs <= 0:
        fs = 48000.0

    cols = [c.strip() for c in (fr.cols or [])]
    ci = {c: i for i, c in enumerate(cols)}

    def get(row, name):
        i = ci.get(name, -1)
        if i < 0 or i >= len(row):
            return ""
        return row[i]

    if "v" in ci:
        vv = []
        for r in fr.rows:
            v = _safe_float(get(r, "v"))
            if v == v:
                vv.append(v)
        return np.asarray(vv, dtype=np.float64), fs

    cand_names = ["q24", "sample", "s", "x", "y"]
    col_name = None
    for nm in cand_names:
        if nm in ci:
            col_name = nm
            break

    vals = []
    if col_name is None:
        for r in fr.rows:
            if not r:
                continue
            try:
                vals.append(int(float(r[0])))
            except Exception:
                continue
    else:
        for r in fr.rows:
            try:
                vals.append(int(float(get(r, col_name))))
            except Exception:
                continue

    xi = np.asarray(vals, dtype=np.float64)
    if xi.size == 0:
        return xi, fs

    int_scale = _safe_float(fr.cfg.get("int_scale", ""), float("nan"))
    if int_scale == int_scale and int_scale > 0:
        x = xi * float(int_scale)
    else:
        if np.max(np.abs(xi)) > 2**20:
            x = xi / float(1 << 24)
        else:
            x = xi
    return x, fs

def _window_vec(name: str, n: int) -> np.ndarray:
    name = (name or "hann").lower()
    if n <= 0:
        return np.ones((0,), dtype=np.float64)
    if name == "rect":
        return np.ones((n,), dtype=np.float64)
    if name == "hann":
        return np.hanning(n).astype(np.float64)
    if name == "blackmanharris":
        a0, a1, a2, a3 = 0.35875, 0.48829, 0.14128, 0.01168
        k = np.arange(n, dtype=np.float64)
        return (a0
                - a1 * np.cos(2.0*np.pi*k/(n-1))
                + a2 * np.cos(4.0*np.pi*k/(n-1))
                - a3 * np.cos(6.0*np.pi*k/(n-1)))
    return np.hanning(n).astype(np.float64)

def _analyze_raw_pc(
    x_in: np.ndarray,
    fs: float,
    fft_n: int,
    window: str,
    harmonics: int,
    fullscale_vrms: float,
    band_lo_hz: float = 20.0,
    band_hi_hz: float = 20000.0,
) -> Dict[str, object]:
    x = np.asarray(x_in, dtype=np.float64)
    n0 = int(x.size)
    if n0 < 32 or not (fs > 0):
        return {"f_hz": np.array([]), "dbu": np.array([]), "metrics": {}}

    n = int(fft_n)
    if n < 256:
        n = 256
    if n & (n - 1) != 0:
        n = 1 << int(math.floor(math.log2(n)))
    n = int(min(n, n0))
    x = x[-n:]
    x = x - np.mean(x)

    w = _window_vec(window, n)
    xw = x * w
    cg = float(np.sum(w) / n) if n > 0 else 1.0
    if cg <= 0:
        cg = 1.0

    X = np.fft.rfft(xw)
    mag = np.abs(X)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)

    vpk = (2.0 * mag) / (n * cg)
    vrms = vpk / math.sqrt(2.0)

    volts_rms = vrms * float(fullscale_vrms)
    dbu = 20.0 * np.log10(np.maximum(volts_rms, 1e-20) / DBU_REF_VRMS)

    fmin = max(0.0, float(band_lo_hz))
    fmax = min(float(band_hi_hz), 0.5 * float(fs))
    band = (freqs >= fmin) & (freqs <= fmax)
    if band.size > 0:
        band[0] = False

    idxs = np.where(band)[0]
    if idxs.size == 0:
        return {"f_hz": freqs, "dbu": dbu, "metrics": {}}

    k0 = int(idxs[np.argmax(vrms[idxs])])
    if k0 <= 1 or k0 >= len(freqs) - 2:
        f0 = float(freqs[k0])
    else:
        y0 = float(vrms[k0 - 1] ** 2)
        y1 = float(vrms[k0] ** 2)
        y2 = float(vrms[k0 + 1] ** 2)
        denom = (y0 - 2.0 * y1 + y2)
        delta = 0.0
        if abs(denom) > 1e-30:
            delta = 0.5 * (y0 - y2) / denom
            delta = max(-0.5, min(0.5, delta))
        f0 = float((k0 + delta) * fs / n)

    def bin_power(k: int, half: int = 1) -> float:
        k = int(k)
        a = max(1, k - half)
        b = min(len(vrms) - 1, k + half)
        return float(np.sum((vrms[a:b + 1] ** 2)))

    kf = int(round(f0 * n / fs))
    kf = max(1, min(kf, len(freqs) - 2))

    fund_p = bin_power(kf, half=1)
    fund_rms = math.sqrt(max(fund_p, 0.0))

    K = max(1, min(int(harmonics), 20))
    harm_p = 0.0
    used_bins = set()

    def mark_bins(k: int, half: int = 1):
        for kk in range(max(1, k - half), min(len(freqs) - 1, k + half) + 1):
            used_bins.add(int(kk))

    mark_bins(kf, 1)

    for h in range(2, K + 1):
        fh = f0 * h
        if fh > fmax:
            break
        kh = int(round(fh * n / fs))
        kh = max(1, min(kh, len(freqs) - 2))
        harm_p += bin_power(kh, half=1)
        mark_bins(kh, 1)

    harm_rms = math.sqrt(max(harm_p, 0.0))
    thd = harm_rms / max(fund_rms, 1e-20)

    noise_bins = band.copy()
    for kk in used_bins:
        if 0 <= kk < noise_bins.size:
            noise_bins[kk] = False
    noise_p = float(np.sum((vrms[noise_bins] ** 2)))
    noise_rms = math.sqrt(max(noise_p, 0.0))

    resid_rms = math.sqrt(harm_rms * harm_rms + noise_rms * noise_rms)

    fund_v = fund_rms * fullscale_vrms
    noise_v = noise_rms * fullscale_vrms

    def dbu_from_v(vr: float) -> float:
        vr = max(vr, 1e-20)
        return 20.0 * math.log10(vr / DBU_REF_VRMS)

    thd_db = 20.0 * math.log10(max(thd, 1e-20))
    thdn = resid_rms / max(fund_rms, 1e-20)
    thdn_db = 20.0 * math.log10(max(thdn, 1e-20))

    snr_db = 20.0 * math.log10(max(fund_rms, 1e-20) / max(noise_rms, 1e-20))
    sinad_db = 20.0 * math.log10(max(fund_rms, 1e-20) / max(resid_rms, 1e-20))

    metrics = {
        "f0_hz": f"{f0:.6f}",
        "meas_dbu": f"{dbu_from_v(fund_v):.6f}",
        "thd_db": f"{thd_db:.6f}",
        "thd_pct": f"{(100.0 * thd):.6f}",
        "thdn_db": f"{thdn_db:.6f}",
        "thdn_pct": f"{(100.0 * thdn):.6f}",
        "noise_dbu": f"{dbu_from_v(noise_v):.6f}",
        "snr_db": f"{snr_db:.6f}",
        "sinad_db": f"{sinad_db:.6f}",
        "pc_fft_n": str(n),
        "pc_window": window,
        "pc_harm": str(K),
    }

    return {"f_hz": freqs, "dbu": dbu, "metrics": metrics}
