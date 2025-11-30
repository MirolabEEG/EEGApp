import time
import numpy as np
import csv
from collections import deque

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit,
    QHBoxLayout, QSizePolicy, QCheckBox, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from eeg_worker import EEGWorker
from pages.plot_page import butter_bandpass_filter, cheby_bandpass_filter, notch_filter, downsample, normalize


# 🔧 Constant strict thresholds used for everybody (no calibration)
STRICT_THRESHOLDS = {
    "D_A": 3.0,
    "T_A": 2.3,
    "T_B": 1.8,
    "A_B": 1.4,
}


class DrowsinessPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.worker = None
        self.buffer = deque(maxlen=512 * 120)
        self.signal_quality = {"Left": 255, "Right": 255}
        self.fs = 512
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_buffer)

        # 🔧 baseline now always present, from strict defaults
        self.baseline = {"thresholds": STRICT_THRESHOLDS.copy()}

        self.csv_file = None
        self.csv_writer = None

        self.selected_methods = {"D_A": True, "T_A": True, "T_B": True, "A_B": True}

        # warm-up counter to ignore first few windows
        self.process_counter = 0

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(12)

        self.title_label = QLabel("🧪 Drowsiness Monitor")
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.user_label = QLabel(f"👤 User: {self.main_window.config.get('username', 'N/A')}")
        self.user_label.setObjectName("UserLabel")
        self.user_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.user_label)

        self.sampling_label = QLabel("📊 Sampling Rate: N/A Hz")
        self.sampling_label.setObjectName("SamplingLabel")
        layout.addWidget(self.sampling_label)

        self.log_output = QTextEdit()
        self.log_output.setObjectName("LogOutput")
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        self.figure = Figure(facecolor="#ffffff")
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas)

        self.ax = self.figure.add_subplot(1, 1, 1)
        self.plot_data = {"D_A": [], "T_A": [], "T_B": [], "A_B": []}

        method_box = QGroupBox("Select Ratios to Plot")
        method_box.setObjectName("MethodBox")
        method_layout = QHBoxLayout()

        self.checkboxes = {}
        for method in self.selected_methods:
            cb = QCheckBox(method)
            cb.setObjectName(f"Check{method}")
            cb.setChecked(True)
            cb.stateChanged.connect(self.update_selected_methods)
            method_layout.addWidget(cb)
            self.checkboxes[method] = cb

        method_box.setLayout(method_layout)
        layout.addWidget(method_box)

        btn_row = QHBoxLayout()
        self.connect_btn = QPushButton("🔌 Connect")
        self.connect_btn.setObjectName("ConnectButton")
        self.disconnect_btn = QPushButton("❌ Disconnect")
        self.disconnect_btn.setObjectName("DisconnectButton")
        self.start_btn = QPushButton("▶ Start Monitoring")
        self.start_btn.setObjectName("StartButton")
        self.reset_btn = QPushButton("🔄 Reset Plot")
        self.reset_btn.setObjectName("ResetButton")
        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.setObjectName("SettingsButton")
        self.back_btn = QPushButton("⬅ Back")
        self.back_btn.setObjectName("BackButton")

        self.connect_btn.clicked.connect(self.connect_device)
        self.disconnect_btn.clicked.connect(self.disconnect_device)
        self.start_btn.clicked.connect(self.start_monitoring)
        self.reset_btn.clicked.connect(self.reset_plot)
        self.settings_btn.clicked.connect(self.open_settings)
        self.back_btn.clicked.connect(self.stop_monitoring)

        for btn in [
            self.connect_btn,
            self.disconnect_btn,
            self.start_btn,
            self.reset_btn,
            self.settings_btn,
            self.back_btn,
        ]:
            btn_row.addWidget(btn)

        layout.addLayout(btn_row)
        self.setLayout(layout)

    def log(self, msg, alert=False):
        ts = time.strftime("%H:%M:%S")
        if alert:
            self.log_output.append(f"<span style='color:red;'>[{ts}] {msg}</span>")
        else:
            self.log_output.append(f"[{ts}] {msg}")

    def log_drowsiness_alert(self, is_drowsy):
        if is_drowsy:
            self.title_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: red;")
            self.title_label.setText("🛑 Drowsiness Detected!")
        else:
            self.title_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: #009688;")
            self.title_label.setText("🧪 Drowsiness Monitor")

    def update_selected_methods(self):
        for method in self.selected_methods:
            self.selected_methods[method] = self.checkboxes[method].isChecked()

    def connect_device(self):
        if self.worker and self.worker.thread and self.worker.thread.isRunning():
            self.log("⚠ Already connected.")
            return

        address = self.main_window.config.get("device_address")
        if not address:
            self.log("❌ No device address configured.")
            return

        uuids = {
            "Left Ear": "6e400003-b5b0-f393-e0a9-e50e24dcca9f",
            "Right Ear": "6e400003-b5b1-f393-e0a9-e50e24dcca9f",
        }
        self.worker = EEGWorker(address, uuids)
        self.worker.update_log.connect(self.log_output.append)
        self.worker.update_signal.connect(self.update_signal_quality)
        self.worker.update_raw.connect(self.update_raw_data)
        self.worker.connection_failed.connect(self.handle_connection_failed)
        self.worker.start()
        self.log("🔌 Device connection started.")

    def disconnect_device(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
            self.log("❌ Disconnected from device.")
            self.timer.stop()

    def reset_plot(self):
        for key in self.plot_data:
            self.plot_data[key] = []
        self.ax.clear()
        self.canvas.draw()
        self.log("🔄 Plot has been reset.")

    def open_settings(self):
        from PyQt5.QtWidgets import QMessageBox

        QMessageBox.information(
            self,
            "Settings",
            "Please use MenuBar → Settings → Plot Settings to configure display.",
        )

    def handle_connection_failed(self, msg):
        self.log(msg)
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.log("❌ Connection failed. You can try to connect again.")

    def update_signal_quality(self, left_q, right_q):
        self.signal_quality["Left"] = left_q
        self.signal_quality["Right"] = right_q
        self.sampling_label.setText(f"📊 Sampling Rate: {self.fs} Hz")  # Assume fs is stable

    def update_raw_data(self, left, right):
        if left is not None and right is not None:
            self.buffer.append((left, right))

    def start_monitoring(self):
        user = self.main_window.config.get("username", "unknown")

        # 🚫 No calibration file needed anymore, using STRICT_THRESHOLDS
        self.log(
            f"ℹ Using strict built-in drowsiness thresholds (no calibration) for user '{user}'."
        )

        self.csv_file = open(f"{user}_drowsiness.csv", "w", newline="")
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(["Timestamp", "D/A", "T/A", "T/B", "A/B", "State"])

        self.process_counter = 0  # reset warm-up
        self.timer.start(3000)
        self.log("🚀 Real-time monitoring started.")

    def process_buffer(self):
        print("[DEBUG] process_buffer called")

        target_fs = self.main_window.config["signal"].get("target_rate", 128)
        min_samples_needed = target_fs * 6

        if len(self.buffer) < min_samples_needed:
            self.log(
                f"⚠ Not enough data to process. Current buffer: {len(self.buffer)} samples, need: {min_samples_needed}"
            )
            return

        # Ignore first few windows to avoid startup spikes
        self.process_counter += 1
        if self.process_counter <= 3:
            self.log("⏳ Warming up... collecting stable data.")
            return

        data = np.array(self.buffer)[-min_samples_needed:]
        settings = self.main_window.config["signal"]

        results = []
        thresholds = self.baseline["thresholds"]
        MIN_POWER = 1e-3  # floor for very small band powers
        MAX_RATIO = 20.0  # clamp unrealistic spikes

        for ch in range(2):
            raw = data[:, ch]
            raw = self.apply_processing(raw, settings)

            delta = self.segmented_band_power(raw, target_fs, 0.5, 4)
            theta = self.segmented_band_power(raw, target_fs, 4, 8)
            alpha = self.segmented_band_power(raw, target_fs, 8, 13)
            beta = self.segmented_band_power(raw, target_fs, 13, 30)

            # Safe floors
            delta_safe = max(delta, MIN_POWER)
            theta_safe = max(theta, MIN_POWER)
            alpha_safe = max(alpha, MIN_POWER)
            beta_safe = max(beta, MIN_POWER)

            ratios = {}
            ratios["D_A"] = delta_safe / alpha_safe
            ratios["T_A"] = theta_safe / alpha_safe
            ratios["T_B"] = theta_safe / beta_safe
            ratios["A_B"] = alpha_safe / beta_safe

            # Clamp extreme values
            for key in ratios:
                if ratios[key] > MAX_RATIO:
                    ratios[key] = MAX_RATIO

            print(f"[DEBUG] Channel {ch+1} Ratios: {ratios}")

            # Strict rule: both D_A AND T_A must exceed thresholds
            drowsy = (
                ratios["D_A"] >= thresholds["D_A"]
                and ratios["T_A"] >= thresholds["T_A"]
            )
            state = "Drowsy" if drowsy else "Wakeful"

            self.log_drowsiness_alert(state == "Drowsy")
            self.log(
                f"Channel {ch+1} - D/A: {ratios['D_A']:.2f}, T/A: {ratios['T_A']:.2f} => STATE: {state}"
            )
            results.append(ratios)

            for key in ratios:
                self.plot_data[key].append(ratios[key])
                max_len = self.main_window.config["plot"].get(
                    "drowsiness_max_points", 200
                )
                if len(self.plot_data[key]) > max_len:
                    self.plot_data[key] = self.plot_data[key][-max_len:]

        timestamp = time.strftime("%H:%M:%S")
        self.csv_writer.writerow(
            [timestamp] + [results[0][key] for key in ["D_A", "T_A", "T_B", "A_B"]] + [state]
        )
        self.csv_file.flush()

        self.update_plot()

    def apply_processing(self, raw, settings):
        original_rate = settings.get("original_rate", 512)
        target_rate = settings.get("target_rate", 128)
        filter_order = settings.get("filter_order", 4)
        filter_type = settings.get("filter_type", "butter")
        notch_q = settings.get("notch_q", 30)

        if settings.get("downsample", True):
            raw = downsample(raw, original_rate, target_rate)

        if settings.get("bandpass", True):
            if filter_type == "butter":
                raw = butter_bandpass_filter(
                    raw, settings["bandpass_low"], settings["bandpass_high"], target_rate, filter_order
                )
            elif filter_type == "cheby":
                raw = cheby_bandpass_filter(
                    raw, settings["bandpass_low"], settings["bandpass_high"], target_rate, filter_order
                )

        if settings.get("notch", True):
            raw = notch_filter(raw, settings["notch_freq"], target_rate, notch_q)

        if settings.get("normalize", True):
            raw = normalize(raw)

        return raw

    def segmented_band_power(self, signal, fs, lowcut, highcut, segment_duration=1):
        segment_len = int(fs * segment_duration)
        powers = []
        for i in range(0, len(signal) - segment_len + 1, segment_len):
            seg = signal[i: i + segment_len]
            power = self.calculate_band_power(seg, fs, lowcut, highcut)
            powers.append(power)
        return np.mean(powers) if powers else 0.0

    def calculate_band_power(self, signal, fs, lowcut, highcut):
        from scipy.signal import welch

        f, Pxx = welch(signal, fs=fs, nperseg=len(signal), noverlap=len(signal) // 2)
        mask = (f >= lowcut) & (f <= highcut)
        return np.trapz(Pxx[mask], f[mask])

    def update_plot(self):
        self.ax.clear()

        colors = {
            "D_A": "blue",
            "T_A": "green",
            "T_B": "orange",
            "A_B": "purple",
        }

        thresholds = self.baseline["thresholds"]

        for key in self.selected_methods:
            if self.selected_methods[key] and len(self.plot_data[key]) > 0:
                x_values = list(range(len(self.plot_data[key])))

                self.ax.plot(x_values, self.plot_data[key], label=key, color=colors[key])

                threshold = thresholds[key]
                self.ax.axhline(
                    threshold,
                    color=colors[key],
                    linestyle="--",
                    label=f"{key} Threshold",
                )

        self.ax.legend()
        self.ax.set_title("Drowsiness Ratios Over Time")
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

    def stop_monitoring(self):
        self.timer.stop()
        if self.csv_file:
            self.csv_file.close()
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.main_window.navigate_to(2)
        self.log("⬅ Back to feature page.")
