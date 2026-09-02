# fft_avg.py
from __future__ import annotations

import math
from collections import deque
from typing import List, Optional, Tuple

from constants import DBU_REF_VRMS

def dbu_to_vrms(dbu: float) -> float:
    return DBU_REF_VRMS * (10.0 ** (dbu / 20.0))

def vrms_to_dbu(vrms: float) -> float:
    vrms = max(vrms, 1e-30)
    return 20.0 * math.log10(vrms / DBU_REF_VRMS)

class FFTAverager:
    def __init__(self, n: int = 1) -> None:
        self.freq_ref: Optional[List[float]] = None
        self.buf: deque = deque()
        self.n = 1
        self.set_n(n)

    def set_n(self, n: int) -> None:
        try:
            n = int(n)
        except Exception:
            n = 1
        n = max(1, min(n, 128))
        self.n = n
        self.buf = deque(maxlen=self.n)
        self.freq_ref = None

    def push(self, f_hz: List[float], dbu: List[float]) -> Tuple[List[float], List[float]]:
        if self.n <= 1:
            return f_hz, dbu

        if self.freq_ref is None:
            self.freq_ref = list(f_hz)
            self.buf.clear()

        if len(f_hz) != len(self.freq_ref):
            self.freq_ref = list(f_hz)
            self.buf.clear()
        else:
            for idx in (0, len(f_hz) // 2, len(f_hz) - 1):
                if abs(f_hz[idx] - self.freq_ref[idx]) > 1e-6 * max(1.0, self.freq_ref[idx]):
                    self.freq_ref = list(f_hz)
                    self.buf.clear()
                    break

        p = [(dbu_to_vrms(y) ** 2) for y in dbu]
        self.buf.append(p)

        m = len(self.buf)
        if m == 0:
            return f_hz, dbu

        p_avg = [0.0] * len(self.freq_ref)
        for row in self.buf:
            for i, v in enumerate(row):
                p_avg[i] += v
        inv = 1.0 / m
        for i in range(len(p_avg)):
            p_avg[i] *= inv

        y_avg = [vrms_to_dbu(math.sqrt(max(v, 0.0))) for v in p_avg]
        return list(self.freq_ref), y_avg
