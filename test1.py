import socket
import numpy as np
import scipy.signal as signal
import matplotlib.pyplot as plt
import time

# -------------------- Configuration --------------------
UDP_IP = "0.0.0.0"   # Listen on all network interfaces
UDP_PORT = 5005
FS = 500              # Sampling rate (must match ESP32)
BATCH_SIZE = 50       # Samples per UDP packet
BUFFER_LEN = 3000     # Number of samples to display

# -------------------- UDP Setup --------------------
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
print(f"Listening for binary UDP packets on port {UDP_PORT} ...")

# -------------------- Filter Design --------------------
def design_filters(fs):
    # 50 Hz notch
    notch_b, notch_a = signal.iirnotch(50, Q=30, fs=fs)
    # Band-pass 15–45 Hz for PCG
    bp_b, bp_a = signal.butter(4, [15, 45], btype='band', fs=fs)
    return notch_b, notch_a, bp_b, bp_a

notch_b, notch_a, bp_b, bp_a = design_filters(FS)

# -------------------- Plot Setup --------------------
plt.ion()
fig, axs = plt.subplots(3, 1, figsize=(10, 8))

# Raw and filtered plots
raw_line, = axs[0].plot([], [], lw=0.8)
axs[0].set_title("Microphone Voltage (Raw)")
axs[0].set_ylim(-0.5, 0.5)

filt_line, = axs[1].plot([], [], lw=0.8)
axs[1].set_title("Filtered PCG (15–45 Hz)")
axs[1].set_ylim(-0.2, 0.2)

env_line, = axs[2].plot([], [], lw=1.2, color='orange')
axs[2].set_title("Heart Sound Envelope + Detected Peaks")
axs[2].set_ylim(0, 0.2)

for ax in axs:
    ax.grid(True)

# -------------------- Heart Rate Parameters --------------------
REFRACTORY_SEC = 0.55  # seconds (prevents double-counting S1/S2)
last_peak_time = 0
peak_times = []
buffer = np.zeros(BUFFER_LEN)

# -------------------- Main Loop --------------------
while True:
    data, _ = sock.recvfrom(BATCH_SIZE * 4)  # 4 bytes per float32
    samples = np.frombuffer(data, dtype=np.float32)

    # Shift buffer
    buffer = np.roll(buffer, -len(samples))
    buffer[-len(samples):] = samples

    # Filter chain
    filtered = signal.filtfilt(notch_b, notch_a, buffer)
    filtered = signal.filtfilt(bp_b, bp_a, filtered)

    # Envelope (Hilbert)
    envelope = np.abs(signal.hilbert(filtered))

    # Peak detection
    peaks, _ = signal.find_peaks(envelope, height=np.mean(envelope) * 2,
                                 distance=int(REFRACTORY_SEC * FS))
    current_time = np.arange(len(buffer)) / FS
    peak_times = current_time[peaks]

    # Heart rate estimation
    bpm = 0
    if len(peak_times) >= 2:
        intervals = np.diff(peak_times)
        bpm = 60 / np.mean(intervals[-3:])  # rolling average of last 3 beats

    # -------------------- Update Plots --------------------
    raw_line.set_data(np.arange(len(buffer)), buffer)
    filt_line.set_data(np.arange(len(filtered)), filtered)
    env_line.set_data(np.arange(len(envelope)), envelope)
    axs[0].set_xlim(0, len(buffer))
    axs[1].set_xlim(0, len(buffer))
    axs[2].set_xlim(0, len(buffer))

    # Display BPM on the envelope plot
    axs[2].set_title(f"Heart Sound Envelope — BPM: {bpm:.1f}")

    plt.pause(0.05)
