import socket
import numpy as np
import scipy.signal as signal
import matplotlib.pyplot as plt

# -------------------- Configuration --------------------
UDP_IP = "0.0.0.0"
UDP_PORT = 5005
FS = 500                  # Sampling rate (Hz)
BATCH_SIZE = 50
BUFFER_LEN = 3000         # Samples shown in plots

# -------------------- UDP Setup --------------------
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
print(f"Listening for binary UDP packets on port {UDP_PORT} ...")

# -------------------- Filter Design --------------------
def design_filters(fs):
    notch_b, notch_a = signal.iirnotch(50, Q=30, fs=fs)
    bp_b, bp_a = signal.butter(4, [25, 35], btype='band', fs=fs)  # focused heart band
    return notch_b, notch_a, bp_b, bp_a

notch_b, notch_a, bp_b, bp_a = design_filters(FS)

# -------------------- Plot Setup --------------------
plt.ion()
fig, axs = plt.subplots(4, 1, figsize=(10, 9))

raw_line, = axs[0].plot([], [], lw=0.8)
filt_line, = axs[1].plot([], [], lw=0.8)
env_line, = axs[2].plot([], [], lw=1.2, color='orange')
quality_bar = axs[3].barh([0], [0], color='gray')

axs[0].set_title("Microphone Voltage (Raw)")
axs[1].set_title("Filtered PCG (25–35 Hz)")
axs[2].set_title("Heart Sound Envelope — BPM: 0.0")
axs[3].set_title("Signal Quality Indicator")
axs[3].set_xlim(0, 100)
axs[3].set_yticks([])

for ax in axs[:3]:
    ax.set_xlim(0, BUFFER_LEN)
    ax.grid(True)

axs[0].set_ylim(-0.5, 0.5)
axs[1].set_ylim(-0.2, 0.2)
axs[2].set_ylim(0, 0.2)

# -------------------- BPM and Quality Logic --------------------
REFRACTORY_SEC = 0.55
last_valid_bpm = 0
buffer = np.zeros(BUFFER_LEN)

def estimate_quality(envelope, filtered):
    """Compute signal quality based on SNR and consistency"""
    env_std = np.std(envelope)
    sig_std = np.std(filtered)
    if sig_std < 0.005:
        return 20, "Weak / Disconnected", 'gray'
    snr = (np.mean(envelope)**2) / (np.var(filtered) + 1e-6)
    if snr < 0.02:
        return 40, "Noisy", 'red'
    elif snr < 0.06:
        return 70, "Moderate", 'orange'
    else:
        return 100, "Clean", 'green'

# -------------------- Main Loop --------------------
while True:
    data, _ = sock.recvfrom(BATCH_SIZE * 4)
    samples = np.frombuffer(data, dtype=np.float32)

    buffer = np.roll(buffer, -len(samples))
    buffer[-len(samples):] = samples

    # --- Filtering ---
    filtered = signal.filtfilt(notch_b, notch_a, buffer)
    filtered = signal.filtfilt(bp_b, bp_a, filtered)

    # --- Envelope ---
    envelope = np.abs(signal.hilbert(filtered))

    # --- Adaptive Threshold ---
    window = int(0.8 * FS)
    moving_mean = np.convolve(envelope, np.ones(window)/window, mode='same')
    threshold = moving_mean * 1.5

    peaks, _ = signal.find_peaks(envelope, height=threshold,
                                 distance=int(REFRACTORY_SEC * FS))

    current_time = np.arange(len(buffer)) / FS
    peak_times = current_time[peaks]

    # --- BPM ---
    bpm = last_valid_bpm
    if len(peak_times) >= 2:
        intervals = np.diff(peak_times)
        valid_intervals = intervals[intervals > REFRACTORY_SEC]
        if len(valid_intervals) >= 2:
            bpm_instant = 60 / np.mean(valid_intervals[-3:])
            if 40 < bpm_instant < 180:
                bpm = 0.7 * last_valid_bpm + 0.3 * bpm_instant if last_valid_bpm > 0 else bpm_instant
                last_valid_bpm = bpm

    # --- Signal Quality ---
    quality_value, quality_label, quality_color = estimate_quality(envelope, filtered)

    # --- Update Plots ---
    raw_line.set_data(np.arange(len(buffer)), buffer)
    filt_line.set_data(np.arange(len(filtered)), filtered)
    env_line.set_data(np.arange(len(envelope)), envelope)
    axs[2].set_title(f"Heart Sound Envelope — BPM: {bpm:.1f}")
    quality_bar[0].set_width(quality_value)
    quality_bar[0].set_color(quality_color)
    axs[3].set_title(f"Signal Quality: {quality_label}")

    print(f"BPM: {bpm:.1f}, Quality: {quality_label} ({quality_value}%)")
    plt.pause(0.05)
