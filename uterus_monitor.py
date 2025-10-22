import socket
import numpy as np
import scipy.signal as signal
import matplotlib.pyplot as plt
from collections import deque
from time import time

# ---------------- SETTINGS ----------------
UDP_IP = "0.0.0.0"
UDP_PORT = 5005
FS = 500                      # must match ESP32
WINDOW_SEC = 12               # plotting window
ENVELOPE_SMOOTH_SEC = 0.10    # smooth envelope ~100 ms
REFRACTORY_SEC = 0.55         # min time between beats (avoid double count)
MAD_K = 2.5                   # threshold sensitivity (try 2.0–3.5)
MIN_BPM, MAX_BPM = 35, 220    # sanity limits
# ------------------------------------------

# -------------- FILTERS -------------------
def design_filters(fs):
    notch_b, notch_a = signal.iirnotch(50, Q=30, fs=fs)
    # PCG band for S1/S2: 20–50 Hz (works well with your mic + 500 Hz FS)
    bp_b, bp_a = signal.butter(4, [20, 50], btype='band', fs=fs)
    return notch_b, notch_a, bp_b, bp_a

notch_b, notch_a, bp_b, bp_a = design_filters(FS)

def hilbert_envelope(x, fs, smooth_sec=0.10):
    # analytic signal -> abs -> lowpass (moving avg) to smooth
    analytic = signal.hilbert(x)
    env = np.abs(analytic)
    win = max(1, int(smooth_sec * fs))
    # causal moving average (simple and fast)
    kernel = np.ones(win, dtype=float) / win
    env_sm = np.convolve(env, kernel, mode='same')
    return env_sm

def adaptive_threshold(x, k=2.5):
    med = np.median(x)
    mad = np.median(np.abs(x - med)) + 1e-9
    return med + k * mad

# -------------- UDP & BUFFERS -------------
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
print(f"Listening on UDP {UDP_PORT} ...")

buf_len = FS * WINDOW_SEC
raw_buf = deque(maxlen=buf_len)

# -------------- PLOTTING -------------------
plt.ion()
fig = plt.figure(figsize=(11,7))
ax_sig = plt.subplot(3,1,1)
ax_env = plt.subplot(3,1,2)
ax_hr  = plt.subplot(3,1,3)
ax_sig.set_title("Filtered PCG (20–50 Hz)"); ax_sig.set_ylim([-0.5, 0.5])
ax_env.set_title("Hilbert Envelope + Threshold")
ax_hr.set_title("Heart Rate (BPM)")

# -------------- HR STATE -------------------
last_peak_t = -1e9
peak_times = deque(maxlen=20)  # store last ~20 peak timestamps (seconds)
bpm_series_t = deque(maxlen=600)
bpm_series_v = deque(maxlen=600)

def update_hr(peakt):
    peak_times.append(peakt)
    # need at least 2 peaks for interval, better with a small window
    if len(peak_times) >= 2:
        # use median of last N inter-beat intervals for robustness
        ibis = np.diff(np.array(peak_times))
        ibi = np.median(ibis) if len(ibis) else np.nan
        if ibi > 0:
            bpm = 60.0 / ibi
            # sanity check
            if MIN_BPM <= bpm <= MAX_BPM:
                bpm_series_t.append(peakt)
                bpm_series_v.append(bpm)

while True:
    data, _ = sock.recvfrom(4096)  # batch CSV: "v1,v2,...,"
    try:
        samples = [float(x) for x in data.decode().split(',') if x.strip() != ""]
    except:
        continue

    for s in samples:
        raw_buf.append(s)

    if len(raw_buf) < FS:  # wait until we have at least 1 sec
        continue

    # numpy arrays for DSP
    raw = np.array(raw_buf)

    # notch + bandpass
    x1 = signal.filtfilt(notch_b, notch_a, raw)
    pcg = signal.filtfilt(bp_b, bp_a, x1)

    # envelope
    env = hilbert_envelope(pcg, FS, ENVELOPE_SMOOTH_SEC)

    # dynamic threshold and peak picking
    thr = adaptive_threshold(env, MAD_K)
    above = env > thr

    # find rising-edge peaks with refractory
    # simple approach: local maxima in 'env' where 'above' is True
    # use a small neighborhood to avoid noisy double peaks
    # pick candidate indices
    candidates, _ = signal.find_peaks(env, height=thr, distance=int(REFRACTORY_SEC*FS))

    # convert last new candidates to times and update HR
    # only consider candidates that occurred since last loop draw
    now_t = time()
    # approximate sample-to-time mapping using now_t minus buffer duration
    start_t = now_t - (len(env)/FS)
    for idx in candidates[-10:]:  # recent ones
        cand_t = start_t + idx/FS
        # enforce strict refractory by wall-clock too (extra safety)
        if cand_t - last_peak_t >= REFRACTORY_SEC:
            last_peak_t = cand_t
            update_hr(cand_t)

    # ----------- plot ------------
    t = np.arange(len(pcg))/FS

    ax_sig.cla(); ax_env.cla(); ax_hr.cla()
    ax_sig.plot(t, pcg)
    ax_sig.set_title("Filtered PCG (20–50 Hz)"); ax_sig.set_ylim([-0.5, 0.5])

    ax_env.plot(t, env, label="Envelope")
    ax_env.plot(t, np.full_like(t, thr), '--', label="Threshold")
    # mark peaks in current window
    ax_env.plot(candidates/FS, env[candidates], 'o', label="Peaks")
    ax_env.set_title("Hilbert Envelope + Adaptive Threshold")
    ax_env.legend(loc="upper right")

    if bpm_series_t:
        # align HR times to a relative axis
        t0 = bpm_series_t[0]
        hr_t = np.array(bpm_series_t) - t0
        ax_hr.plot(hr_t, bpm_series_v, '-o')
        ax_hr.set_xlim([max(0, hr_t[-1]-60), hr_t[-1]+1])  # last ~60 s
    ax_hr.set_ylim([MIN_BPM, MAX_BPM])
    ax_hr.set_ylabel("BPM")

    plt.pause(0.01)
