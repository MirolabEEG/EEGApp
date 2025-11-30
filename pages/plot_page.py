from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QGroupBox, QSizePolicy
from PyQt5.QtCore import Qt, QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from eeg_worker import EEGWorker

import numpy as np
import logging
from scipy.signal import butter, cheby1, filtfilt, iirnotch, decimate

logger = logging.getLogger(__name__)

def normalize(data):
    mean = np.mean(data)
    std = np.std(data)
    return (data - mean) / std if std > 0 else data

def butter_bandpass_filter(data, lowcut, highcut, fs, order):
    if fs <= 0 or highcut >= fs / 2 or lowcut <= 0 or lowcut >= highcut:
        logger.warning(f"[butter] Invalid bandpass params: fs={fs}, low={lowcut}, high={highcut}")
        return data
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    if not (0 < low < high < 1):
        logger.warning(f"[butter] Skipping filter: normalized low={low:.3f}, high={high:.3f}")
        return data
    b, a = butter(order, [low, high], btype='band')
    padlen = 3 * max(len(a), len(b))
    if len(data) <= padlen:
        return data
    return filtfilt(b, a, data)


def cheby_bandpass_filter(data, lowcut, highcut, fs, order, ripple=0.5):
    if fs <= 0 or highcut >= fs / 2 or lowcut <= 0 or lowcut >= highcut:
        logger.warning(f"[cheby] Invalid bandpass params: fs={fs}, low={lowcut}, high={highcut}")
        return data
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    if not (0 < low < high < 1):
        logger.warning(f"[cheby] Skipping filter: normalized low={low:.3f}, high={high:.3f}")
        return data
    b, a = cheby1(order, ripple, [low, high], btype='band')
    padlen = 3 * max(len(a), len(b))
    if len(data) <= padlen:
        return data
    return filtfilt(b, a, data)

def notch_filter(data, freq, fs, q):
    b, a = iirnotch(freq / (fs / 2), q)
    padlen = 3 * max(len(a), len(b))
    if len(data) <= padlen:
        return data
    return filtfilt(b, a, data)

def downsample(data, original_rate, target_rate):
    if target_rate >= original_rate or original_rate % target_rate != 0:
        return data
    decimation_factor = original_rate // target_rate
    return decimate(data, decimation_factor, ftype='fir', zero_phase=True)

class PlotPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.worker = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_plot)

        self.left_data = []
        self.right_data = []
        self.med_left = []
        self.med_right = []
        self.att_left = []
        self.att_right = []
        self.fs_left = 512
        self.fs_right = 512

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(12)

        # === TITLE ROW ===
        title_row = QHBoxLayout()
        title = QLabel("🧠 EEG Live Visualization")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignLeft)

        self.user_label = QLabel(f"👤 User: {self.main_window.config.get('username', 'N/A')}")
        self.user_label.setObjectName("UserLabel")
        self.user_label.setAlignment(Qt.AlignRight)

        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.user_label)
        layout.addLayout(title_row)

        # === PLOT CANVAS ===
        self.figure = Figure(facecolor="#ffffff")
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas)

        # === INFO GROUP ===
        info_group = QGroupBox()
        info_layout = QVBoxLayout()

        rate_row = QHBoxLayout()
        self.rate_label_left = QLabel("Left Rate: -- Hz")
        self.rate_label_left.setObjectName("RateLabelLeft")
        self.rate_label_right = QLabel("Right Rate: -- Hz")
        self.rate_label_right.setObjectName("RateLabelRight")
        rate_row.addWidget(self.rate_label_left)
        rate_row.addStretch()
        rate_row.addWidget(self.rate_label_right)
        info_layout.addLayout(rate_row)

        sig_row = QHBoxLayout()
        self.signal_label_left = QLabel("Left Signal: N/A")
        self.signal_label_left.setObjectName("SignalLabelLeft")
        self.signal_label_right = QLabel("Right Signal: N/A")
        self.signal_label_right.setObjectName("SignalLabelRight")
        sig_row.addWidget(self.signal_label_left)
        sig_row.addStretch()
        sig_row.addWidget(self.signal_label_right)
        info_layout.addLayout(sig_row)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # === LOG OUTPUT ===
        self.log_output = QTextEdit()
        self.log_output.setObjectName("LogOutput")
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(100)
        layout.addWidget(self.log_output)

        # === BUTTONS ===
        btn_row = QHBoxLayout()

        self.reconnect_button = QPushButton("🔄 Reconnect")
        self.reconnect_button.setObjectName("ReconnectButton")
        self.reconnect_button.setEnabled(False)
        self.reconnect_button.clicked.connect(self.reconnect_device)
        btn_row.addWidget(self.reconnect_button)

        self.back_button = QPushButton("⬅ Back")
        self.back_button.setObjectName("BackButton")
        self.back_button.clicked.connect(self.go_back)
        btn_row.addStretch()
        btn_row.addWidget(self.back_button)

        layout.addLayout(btn_row)

        self.disconnect_button = QPushButton("🔌 Disconnect")
        self.disconnect_button.setObjectName("DisconnectButton")
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.clicked.connect(self.disconnect_device)
        layout.addWidget(self.disconnect_button)

        self.setLayout(layout)



    def set_sampling_rate(self, side, rate):
        if side == "Left":
            self.fs_left = rate
            self.rate_label_left.setText(f"Left Rate: {rate:.1f} Hz")
        elif side == "Right":
            self.fs_right = rate
            self.rate_label_right.setText(f"Right Rate: {rate:.1f} Hz")


    def reconnect_device(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.log_output.append("\ud83d\udd04 Attempting reconnection...")
        self.start_visualization()

    def handle_connection_failure(self, msg):
        self.log_output.append(f"\u274c Connection Failed: {msg}")
        self.reconnect_button.setEnabled(True)

    def disconnect_device(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
            self.log_output.append("🔌 Disconnected from device.")
            self.disconnect_button.setEnabled(False)
            self.reconnect_button.setEnabled(True)
            self.timer.stop()

    def start_visualization(self):
        self.left_data.clear()
        self.right_data.clear()
        self.med_left.clear()
        self.med_right.clear()
        self.att_left.clear()
        self.att_right.clear()

        self.figure.clear()
        self.reconnect_button.setEnabled(False)
        self.disconnect_button.setEnabled(True)
        features = self.main_window.config["features"]

        logger.info(f"Visualization config: {features}")

        if features.get("raw") and features.get("fft"):
            self.ax_raw_left = self.figure.add_subplot(2, 2, 1)
            self.ax_raw_right = self.figure.add_subplot(2, 2, 2)
            self.ax_fft_left = self.figure.add_subplot(2, 2, 3)
            self.ax_fft_right = self.figure.add_subplot(2, 2, 4)

        elif features.get("med"):
            self.ax_med = self.figure.add_subplot(1, 1, 1)

        elif features.get("att"):
            self.ax_att = self.figure.add_subplot(1, 1, 1)

        self.canvas.draw()

        uuids = {
            "Left Ear": "6e400003-b5b0-f393-e0a9-e50e24dcca9f",
            "Right Ear": "6e400003-b5b1-f393-e0a9-e50e24dcca9f"
        }
        address = self.main_window.config["device_address"]

        self.worker = EEGWorker(address, uuids)
        self.worker.update_log.connect(self.log_output.append)
        self.worker.update_signal.connect(self.update_signal_quality)
        self.worker.update_raw.connect(self.main_window.handle_raw_data)
        self.worker.update_med_att.connect(self.update_med_att_plot)
        self.worker.connection_failed.connect(self.handle_connection_failure)
        self.worker.update_sampling_rate.connect(self.set_sampling_rate)
        self.worker.start()

        self.timer.start(200)

    def refresh_plot(self):
        features = self.main_window.config["features"]
        settings = self.main_window.config["signal"]
        plot_cfg = self.main_window.config["plot"] 

        def process(raw, fs):
            original_rate = int(fs)
            target_rate = settings.get("target_rate", 128)
            filter_order = settings.get("filter_order", 4)
            filter_type = settings.get("filter_type", "butter")
            notch_q = settings.get("notch_q", 30)

            if fs <= 1 or fs is None:
                logger.warning(f"[process] Skipping processing due to invalid fs={fs}")
                return None, None

            if len(raw) >= original_rate:
                plot_cfg = self.main_window.config["plot"]
                segment = np.array(raw[-plot_cfg["window_size"]:])

                # 🛡️ Minimum length check for filtering
                if len(segment) < 30:
                    return None, None

                # 🧠 DEBUG LOGGING
                logger.debug(f"[refresh_plot] Segment length: {len(segment)}")
                logger.debug(f"[filter] Using fs={original_rate}, bandpass=({settings['bandpass_low']}, {settings['bandpass_high']})")

                if settings.get("downsample", True):
                    segment = downsample(segment, original_rate, target_rate)
                    fs = target_rate

                if settings.get("bandpass", True):
                    if filter_type == "butter":
                        segment = butter_bandpass_filter(segment, settings["bandpass_low"], settings["bandpass_high"], fs, filter_order)
                    elif filter_type == "cheby":
                        segment = cheby_bandpass_filter(segment, settings["bandpass_low"], settings["bandpass_high"], fs, filter_order)

                if settings.get("notch", True):
                    segment = notch_filter(segment, settings["notch_freq"], fs, notch_q)

                if settings.get("normalize", True):
                    segment = normalize(segment)

                return segment, fs
            return None, None



        if features.get("raw") and features.get("fft"):
            self.ax_raw_left.clear()
            self.ax_raw_right.clear()
            self.ax_fft_left.clear()
            self.ax_fft_right.clear()

            left_processed, fs_left = process(self.left_data, self.fs_left)
            right_processed, fs_right = process(self.right_data, self.fs_right)

            if left_processed is not None:
                self.ax_raw_left.plot(left_processed, label="Left (filtered)")
                freqs, power = self.compute_fft(left_processed, fs_left)
                power = np.maximum(power, 1)
                self.ax_fft_left.plot(freqs, power)
                self.ax_fft_left.set_xlim(0, plot_cfg["fft_max_hz"])
                if plot_cfg["log_scale"]:
                    self.ax_fft_left.set_yscale("log")
                self.ax_fft_left.set_ylim(1, 10000)

            if right_processed is not None:
                self.ax_raw_right.plot(right_processed, label="Right (filtered)")
                freqs, power = self.compute_fft(right_processed, fs_right)
                power = np.maximum(power, 1)
                self.ax_fft_right.plot(freqs, power)
                self.ax_fft_right.set_xlim(0, plot_cfg["fft_max_hz"])
                if plot_cfg["log_scale"]:
                    self.ax_fft_right.set_yscale("log")
                self.ax_fft_right.set_ylim(1, 10000)

        elif features.get("med"):
            self.ax_med.clear()
            if self.med_left:
                self.ax_med.plot(self.med_left[-50:], label="Med Left", color="blue")
            if self.med_right:
                self.ax_med.plot(self.med_right[-50:], label="Med Right", color="cyan")
            self.ax_med.set_ylim(0, 100)
            self.ax_med.legend()

        elif features.get("att"):
            self.ax_att.clear()
            if self.att_left:
                self.ax_att.plot(self.att_left[-50:], label="Att Left", color="red")
            if self.att_right:
                self.ax_att.plot(self.att_right[-50:], label="Att Right", color="orange")
            self.ax_att.set_ylim(0, 100)
            self.ax_att.legend()

        self.canvas.draw()

    def update_raw_plot(self, left, right):
        if left:
            self.left_data.append(left)
        if right:
            self.right_data.append(right)

    def compute_fft(self, data, sample_rate):
        data = np.array(data)
        data = data - np.mean(data)
        fft_vals = np.abs(np.fft.fft(data))
        freqs = np.fft.fftfreq(len(data), d=1/sample_rate)
        return freqs[:len(freqs)//2], fft_vals[:len(fft_vals)//2]

    def update_signal_quality(self, left_q, right_q):
        def style(label, q):
            if q == 0:
                label.setText(f"Signal: Good (0)")
                label.setStyleSheet("color: green;")
            elif 1 <= q <= 50:
                label.setText(f"Signal: Poor ({q})")
                label.setStyleSheet("color: orange;")
            else:
                label.setText(f"Signal: Very Poor ({q})")
                label.setStyleSheet("color: red;")
        style(self.signal_label_left, left_q)
        style(self.signal_label_right, right_q)

    def update_med_att_plot(self, source, med, att):
        if source == "Left":
            self.med_left.append(med)
            self.att_left.append(att)
        elif source == "Right":
            self.med_right.append(med)
            self.att_right.append(att)
        self.log_output.append(f"[{source}] Med: {med}, Att: {att}")

    def update_username_label(self):
        username = self.main_window.config.get("username", "N/A")
        self.user_label.setText(f"👤 User: {username}")


    def go_back(self):
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.timer.stop()
        self.main_window.navigate_to(2)
