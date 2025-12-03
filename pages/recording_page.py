import time
import csv
#import pyedflib
import numpy as np
import queue
import threading
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QComboBox, QLineEdit, QFileDialog
)
from PyQt5.QtCore import Qt, QTimer
from eeg_worker import EEGWorker

class EEGRecorder:
    def __init__(self):
        self.recording = False
        self.start_time = None
        self.paused_time = 0
        self.pause_start = None
        self.left_queue = queue.Queue()
        self.right_queue = queue.Queue()
        self.file_handle = None
        self.write_thread = None
        self.stop_thread = False
        self.total_lines = 0
        self.filename = None

    def start(self, path):
        self.filename = path
        self.file_handle = open(path, "w", newline='')
        self.file_handle.write("Real Time (HH:MM:SS.ss),Timestamp (ms),Left Ear,Right Ear,Marker\n")
        self.recording = True
        self.stop_thread = False
        self.start_time = time.time()
        self.paused_time = 0
        self.write_thread = threading.Thread(target=self.save_data_to_file)
        self.write_thread.start()

    def pause(self):
        self.recording = False
        self.pause_start = time.time()

    def resume(self):
        self.recording = True
        self.paused_time += time.time() - self.pause_start
        self.pause_start = None

    def stop(self):
        self.recording = False
        self.stop_thread = True
        if self.write_thread:
            self.write_thread.join()
        if self.file_handle:
            self.file_handle.close()

    def add_sample(self, left, right):
        if not self.recording: return
        timestamp = time.time() - self.start_time - self.paused_time
        if left:
            self.left_queue.put((timestamp, left))
        if right:
            self.right_queue.put((timestamp, right))

    def add_marker(self, marker):
        timestamp_ms = int((time.time() - self.start_time - self.paused_time) * 1000)
        safe_marker = marker.encode("ascii", "ignore").decode("ascii")
        if self.file_handle:
            absolute_time = self.start_time + (timestamp_ms / 1000) + self.paused_time
            time_str = time.strftime("%H:%M:%S", time.localtime(absolute_time)) + f".{int((absolute_time % 1) * 100):02}"
            self.file_handle.write(f"{time_str},{timestamp_ms},,,{safe_marker}\n")
            self.file_handle.flush()


    def add_unlabeled_marker(self):
        self.add_marker("Unlabeled")

    def save_data_to_file(self):
        buffer = []
        left_buf = []
        right_buf = []
        while not self.stop_thread:
            while not self.left_queue.empty():
                left_buf.append(self.left_queue.get())
            while not self.right_queue.empty():
                right_buf.append(self.right_queue.get())

            while left_buf and right_buf:
                l = left_buf.pop(0)
                r = right_buf.pop(0)
                timestamp_ms = int(l[0] * 1000)  # from left sample
                absolute_time = self.start_time + l[0] + self.paused_time
                time_str = time.strftime("%H:%M:%S", time.localtime(absolute_time)) + f".{int((absolute_time % 1) * 100):02}"
                buffer.append(f"{time_str},{timestamp_ms},{l[1]:.6f},{r[1]:.6f},\n")
                self.total_lines += 1

            if len(buffer) >= 100:
                self.file_handle.writelines(buffer)
                buffer.clear()
                self.file_handle.flush()

            time.sleep(0.01)

        for l in left_buf:
            absolute_time = self.start_time + l[0] + self.paused_time
            time_str = time.strftime("%H:%M:%S", time.localtime(absolute_time)) + f".{int((absolute_time % 1) * 100):02}"
            timestamp_ms = int(l[0] * 1000)
            self.file_handle.write(f"{time_str},{timestamp_ms},{l[1]:.6f},,\n")
        for r in right_buf:
            absolute_time = self.start_time + r[0] + self.paused_time
            time_str = time.strftime("%H:%M:%S", time.localtime(absolute_time)) + f".{int((absolute_time % 1) * 100):02}"
            timestamp_ms = int(r[0] * 1000)
            self.file_handle.write(f"{time_str},{timestamp_ms},,{r[1]:.6f},\n")


        self.file_handle.flush()

class RecordingPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.recorder = EEGRecorder()
        self.worker = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)
        self.elapsed_seconds = 0

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(12)

        # Title
        title = QLabel("🧠 EEG Data Recorder")
        title.setObjectName("TitleLabel")
        layout.addWidget(title, alignment=Qt.AlignCenter)

        self.user_label = QLabel(f"👤 User: {self.main_window.config.get('username', 'N/A')}")
        self.user_label.setObjectName("UserLabel")
        self.user_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.user_label)

        # Connect / Disconnect
        device_btn_row = QHBoxLayout()
        self.connect_btn = QPushButton("🔌 Connect")
        self.connect_btn.setObjectName("ConnectButton")
        self.disconnect_btn = QPushButton("❌ Disconnect")
        self.disconnect_btn.setObjectName("DisconnectButton")
        self.connect_btn.clicked.connect(self.connect_device)
        self.disconnect_btn.clicked.connect(self.disconnect_device)
        device_btn_row.addWidget(self.connect_btn)
        device_btn_row.addWidget(self.disconnect_btn)
        layout.addLayout(device_btn_row)

        # Timer
        self.timer_label = QLabel("⏱ Elapsed Time: 00:00:00")
        self.timer_label.setObjectName("TimerLabel")
        layout.addWidget(self.timer_label, alignment=Qt.AlignCenter)

        # Format selection
        format_row = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.setObjectName("FormatCombo")
        self.format_combo.addItems(["CSV", "EDF"])
        format_row.addWidget(QLabel("Save Format:"))
        format_row.addWidget(self.format_combo)
        layout.addLayout(format_row)

        # Start/Pause/Resume/Stop
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("▶ Start")
        self.start_btn.setObjectName("StartButton")
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.setObjectName("PauseButton")
        self.resume_btn = QPushButton("⏯ Resume")
        self.resume_btn.setObjectName("ResumeButton")
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setObjectName("StopButton")

        self.start_btn.clicked.connect(self.start_recording)
        self.pause_btn.clicked.connect(self.pause_recording)
        self.resume_btn.clicked.connect(self.resume_recording)
        self.stop_btn.clicked.connect(self.stop_recording)

        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)

        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.pause_btn)
        btn_row.addWidget(self.resume_btn)
        btn_row.addWidget(self.stop_btn)
        layout.addLayout(btn_row)

        # Marker Row
        marker_row = QHBoxLayout()
        self.marker_combo = QComboBox()
        self.marker_combo.setObjectName("MarkerCombo")
        self.marker_combo.addItems(["Stimulus", "Blink", "Left Tap", "Right Tap", "Rest"])
        self.insert_marker_btn = QPushButton("📍 Insert Marker")
        self.insert_marker_btn.setObjectName("InsertMarkerButton")
        self.insert_marker_btn.clicked.connect(self.insert_marker)
        self.unlabeled_marker_btn = QPushButton("⚡ Insert Unlabeled Marker")
        self.unlabeled_marker_btn.setObjectName("InsertUnlabeledButton")
        self.unlabeled_marker_btn.clicked.connect(self.insert_unlabeled_marker)
        marker_row.addWidget(self.marker_combo)
        marker_row.addWidget(self.insert_marker_btn)
        marker_row.addWidget(self.unlabeled_marker_btn)
        layout.addLayout(marker_row)

        # Annotation
        annotation_row = QHBoxLayout()
        self.annotation_input = QLineEdit()
        self.annotation_input.setObjectName("AnnotationInput")
        self.annotation_input.setPlaceholderText("Type annotation and press Enter")
        self.annotation_input.returnPressed.connect(self.insert_annotation)
        annotation_row.addWidget(self.annotation_input)
        layout.addLayout(annotation_row)

        # Log output
        self.log_output = QTextEdit()
        self.log_output.setObjectName("LogOutput")
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)

        # Back button
        self.back_btn = QPushButton("⬅ Back")
        self.back_btn.setObjectName("BackButton")
        self.back_btn.clicked.connect(lambda: self.main_window.navigate_to(2))
        layout.addWidget(self.back_btn, alignment=Qt.AlignRight)

        self.setLayout(layout)


    def handle_log_message(self, msg):
        if msg.startswith("["):
            return  # Ignore med/att logs
        self.log_output.append(msg)

    def handle_connection_failure(self, msg):
        self.log_error(f"❌ BLE Connection Failed: {msg}")
        self.disconnect_device()

    def log_info(self, text):
        self.log_output.append(f'<span style="color:#2e7d32;font-size:10pt;">{text}</span>')

    def log_error(self, text):
        self.log_output.append(f'<span style="color:#c62828;font-size:10pt;"><b>{text}</b></span>')


    def connect_device(self):
        address = self.main_window.config.get("device_address")
        if not address:
            self.log_error("⚠ No device selected.")
            return
        uuids = {
            "Left Ear": "6e400003-b5b0-f393-e0a9-e50e24dcca9f",
            "Right Ear": "6e400003-b5b1-f393-e0a9-e50e24dcca9f"
        }
        self.worker = EEGWorker(address, uuids)
        self.worker.update_raw.connect(self.main_window.handle_raw_data)
        self.worker.connection_failed.connect(self.handle_connection_failure)
        self.worker.start()
        self.worker.update_log.connect(self.handle_log_message)


    def disconnect_device(self):
        if self.worker:
            self.worker.stop()
            self.worker.thread.quit()
            self.worker.thread.wait()
            self.worker = None
            self.log_info("❌ Disconnected from device.")

    def update_timer(self):
        self.elapsed_seconds += 1
        hrs, rem = divmod(self.elapsed_seconds, 3600)
        mins, secs = divmod(rem, 60)
        self.timer_label.setText(f"⏱ Elapsed Time: {hrs:02}:{mins:02}:{secs:02}")

    def start_recording(self):
        username = self.main_window.config.get("username", "user")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        file_format = self.format_combo.currentText()
        ext = ".csv" if file_format == "CSV" else ".edf"
        default_name = f"{username}_{timestamp}{ext}"
        
        if ext == ".edf":
            self.log_error("⚠ EDF export is not implemented yet.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save EEG Recording", default_name, f"{file_format} Files (*{ext})")
        if not path:
            self.log_error("❌ Save location not selected.")
            return

        self.recorder.start(path)
        self.elapsed_seconds = 0
        self.timer.start(1000)
        self.log_info("▶ Recording started.")
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)


    def pause_recording(self):
        self.recorder.pause()
        self.timer.stop()
        ts = int(time.time() * 1000)
        self.recorder.add_marker(f"⏸ Paused at {ts} ms")
        self.log_info(f"🛑 Paused at {ts} ms")
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(True)


    def resume_recording(self):
        self.recorder.resume()
        self.timer.start(1000)
        ts = int(time.time() * 1000)
        self.recorder.add_marker(f"▶ Resumed at {ts} ms")
        self.log_info(f"▶ Resumed at {ts} ms")
        self.pause_btn.setEnabled(True)
        self.resume_btn.setEnabled(False)


    def stop_recording(self):
        self.recorder.stop()
        self.timer.stop()
        self.log_info("⏹ Recording stopped.")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.resume_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.log_info(f"💾 Recording saved to {self.recorder.filename}")

    def insert_marker(self):
        marker = self.marker_combo.currentText()
        self.recorder.add_marker(marker)
        self.log_info(f"📍 Marker inserted: {marker}")

    def insert_unlabeled_marker(self):
        self.recorder.add_unlabeled_marker()
        self.log_info("📍 Unlabeled marker inserted.")

    def insert_annotation(self):
        annotation = self.annotation_input.text().strip()
        if annotation:
            self.recorder.add_marker(annotation)
            self.annotation_input.clear()
            self.log_info(f"📝 Annotation added: {annotation}")


