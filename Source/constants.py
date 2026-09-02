# constants.py

BAUD = 115200

DBU_REF_VRMS = 0.775
DB_FLOOR = -130.0

HIST_VIEWS = ("sweep", "thd_sweep", "xfer", "fft_bins", "wave")

VIEW_TITLES = {
    "sweep": "Sweep",
    "thd_sweep": "THD Sweep",
    "xfer": "Transfer",
    "fft_bins": "FFT Spectrum",
    "wave": "Waveform",
    "raw": "Raw",
}

HIST_ALPHA = 0.65
HIST_LW = 1.2
HIST_CMAP_NAME = "tab10"

MAX_LABEL_BOXES = 8

WINDOWS = ("rect", "hann", "blackmanharris")
DEFAULT_FFT_N = 4096
DEFAULT_WINDOW = "hann"
DEFAULT_HARMONICS = 6

PC_RAW_VIEWS = ("raw", "raw_analyze", "samples", "capture")
PC_RAW_DATASETS = ("raw", "raw_analyze", "raw_samples", "analyze_raw", "wave_raw", "samples_raw")
PC_ANALYSIS_STALE_S = 1.5
