# serial_io.py
from __future__ import annotations

import queue
import threading
import time
from typing import Optional

import serial
import serial.tools.list_ports

from parsing import Frame, FrameParser

def _find_port_by_match_key(match_key: dict) -> Optional[str]:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return None

    vid = match_key.get("vid")
    pid = match_key.get("pid")
    sn = match_key.get("serial_number")
    loc = match_key.get("location")
    hwid = match_key.get("hwid")

    candidates = []
    for p in ports:
        p_vid = getattr(p, "vid", None)
        p_pid = getattr(p, "pid", None)
        p_sn = getattr(p, "serial_number", None)
        p_loc = getattr(p, "location", None)
        p_hwid = getattr(p, "hwid", None)

        score = 0
        if vid is not None and pid is not None and p_vid == vid and p_pid == pid:
            score += 5
        if sn and p_sn and p_sn == sn:
            score += 5
        if loc and p_loc and p_loc == loc:
            score += 3
        if hwid and p_hwid and hwid == p_hwid:
            score += 2

        if score > 0:
            candidates.append((score, p.device))

    if not candidates:
        return None

    candidates.sort(reverse=True, key=lambda t: t[0])
    return candidates[0][1]

def _open_serial_with_retry(
    port: str,
    match_key: dict,
    baud: int,
    stop_evt: threading.Event,
    base_sleep: float = 0.10,
    max_sleep: float = 1.0,
) -> Optional[serial.Serial]:
    sleep_s = base_sleep
    cur_port = port

    while not stop_evt.is_set():
        try:
            ser = serial.Serial(
                cur_port,
                baudrate=baud,
                timeout=0.05,
                write_timeout=0.05,
            )
            try:
                ser.reset_input_buffer()
            except Exception:
                pass
            return ser
        except Exception:
            new_port = _find_port_by_match_key(match_key) if match_key else None
            if new_port:
                cur_port = new_port
            t0 = time.time()
            while (time.time() - t0) < sleep_s and not stop_evt.is_set():
                time.sleep(0.02)
            sleep_s = min(max_sleep, sleep_s * 1.4)

    return None

def serial_reader(
    port: str,
    match_key: dict,
    baud: int,
    out_q: "queue.Queue[Frame]",
    stop_evt: threading.Event,
) -> None:
    parser = FrameParser()
    buf = b""

    while not stop_evt.is_set():
        ser = _open_serial_with_retry(port, match_key, baud, stop_evt)
        if ser is None:
            break

        try:
            buf = b""
            while not stop_evt.is_set():
                try:
                    chunk = ser.read(4096)
                    if stop_evt.is_set():
                        break
                    if not chunk:
                        time.sleep(0.01)
                        continue

                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        try:
                            s = line.decode("utf-8", errors="replace").rstrip("\r")
                        except Exception:
                            continue

                        frame = parser.feed_line(s)
                        if frame is not None:
                            try:
                                out_q.put_nowait(frame)
                            except queue.Full:
                                try:
                                    _ = out_q.get_nowait()
                                except queue.Empty:
                                    pass
                                try:
                                    out_q.put_nowait(frame)
                                except Exception:
                                    pass

                except (serial.SerialException, OSError):
                    break
                except Exception:
                    continue
        finally:
            try:
                ser.close()
            except Exception:
                pass

        time.sleep(0.2)
