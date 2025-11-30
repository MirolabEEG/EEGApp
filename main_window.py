from PyQt5.QtWidgets import (
    QMainWindow, QStackedWidget, QMenuBar, QAction, QMessageBox, QDialog
)
from pages.user_page import UserPage
from pages.discovery_page import DiscoveryPage
from pages.feature_page import FeaturePage
from pages.plot_page import PlotPage
from pages.recording_page import RecordingPage
from pages.drowsiness_page import DrowsinessPage
from pages.settings_dialog import SettingsDialog
from PyQt5.QtWidgets import QDialog
import logging
import sys
import copy

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EEG Desktop App")
        self.resize(1000, 700)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # === Default Configs ===
        self.default_config = {
            "signal": {
                "downsample": True,
                "original_rate": 512,
                "target_rate": 128,
                "bandpass": True,
                "bandpass_low": 0.5,
                "bandpass_high": 50.0,
                "filter_type": "butter",
                "filter_order": 4,
                "notch": True,
                "notch_freq": 50,
                "notch_q": 30,
                "normalize": True
            },
            "plot": {
                "window_size": 1024,
                "fft_max_hz": 100,
                "log_scale": True,
                "drowsiness_max_points": 200
            }
        }

        # === Runtime Session Config ===
        self.config = {
            "username": None,
            "device_address": None,
            "features": {},
            "signal": copy.deepcopy(self.default_config["signal"]),
            "plot": copy.deepcopy(self.default_config["plot"])
        }

        self.init_menu()

        # Page setup
        self.discovery_page = DiscoveryPage(self)   # index 0
        self.user_page = UserPage(self)             # index 1
        self.feature_page = FeaturePage(self)       # index 2
        self.plot_page = PlotPage(self)             # index 3
        self.recording_page = RecordingPage(self)   # index 4
        self.drowsiness_page = DrowsinessPage(self) # index 5

        self.stack.addWidget(self.discovery_page)
        self.stack.addWidget(self.user_page)
        self.stack.addWidget(self.feature_page)
        self.stack.addWidget(self.plot_page)
        self.stack.addWidget(self.recording_page)
        self.stack.addWidget(self.drowsiness_page)

        self.stack.setCurrentIndex(1)
        logger.info("Initialized MainWindow and loaded Discovery Page")

    def init_menu(self):
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        # File Menu
        file_menu = menu_bar.addMenu("File")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Settings Menu
        settings_menu = menu_bar.addMenu("Settings")
        plot_settings_action = QAction("Plot Settings", self)
        plot_settings_action.triggered.connect(self.open_plot_settings)
        settings_menu.addAction(plot_settings_action)
        signal_settings_action = QAction("Signal Settings", self)
        signal_settings_action.triggered.connect(self.open_signal_settings)
        settings_menu.addAction(signal_settings_action)

        # Help Menu
        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)



    def open_signal_settings(self):
        dlg = SettingsDialog(self.config["signal"], self)
        if dlg.exec_() == QDialog.Accepted:
            dlg.update_config()
            QMessageBox.information(self, "✅ Signal Settings", "Settings have been updated.")

    def open_plot_settings(self):
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QSpinBox, QCheckBox, QPushButton

        class PlotSettingsDialog(QDialog):
            def __init__(self, plot_config, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Plot Settings")
                self.config = plot_config

                layout = QVBoxLayout()

                layout.addWidget(QLabel("Window size (samples to display):"))
                self.window_spin = QSpinBox()
                self.window_spin.setRange(100, 10000)
                self.window_spin.setValue(self.config.get("window_size", 512))
                layout.addWidget(self.window_spin)

                layout.addWidget(QLabel("Max FFT frequency (Hz):"))
                self.fft_spin = QSpinBox()
                self.fft_spin.setRange(10, 500)
                self.fft_spin.setValue(self.config.get("fft_max_hz", 100))
                layout.addWidget(self.fft_spin)

                self.log_check = QCheckBox("Use log scale for FFT")
                self.log_check.setChecked(self.config.get("log_scale", True))
                layout.addWidget(self.log_check)

                layout.addWidget(QLabel("Max drowsiness points to plot:"))
                self.drowsiness_spin = QSpinBox()
                self.drowsiness_spin.setRange(50, 1000)
                self.drowsiness_spin.setValue(self.config.get("drowsiness_max_points", 200))
                layout.addWidget(self.drowsiness_spin)

                save_btn = QPushButton("Save")
                save_btn.clicked.connect(self.accept)
                layout.addWidget(save_btn)

                self.setLayout(layout)

            def apply(self):
                self.config["window_size"] = self.window_spin.value()
                self.config["fft_max_hz"] = self.fft_spin.value()
                self.config["log_scale"] = self.log_check.isChecked()
                self.config["drowsiness_max_points"] = self.drowsiness_spin.value()

        dialog = PlotSettingsDialog(self.config["plot"], self)
        if dialog.exec_() == QDialog.Accepted:
            dialog.apply()
            QMessageBox.information(self, "✅ Settings Saved", "Plot settings have been updated.")

    def show_about_dialog(self):
        QMessageBox.information(
            self,
            "About EEG App",
            "EEG Desktop App\nVersion 1.0\nDeveloped with ❤️ using PyQt5"
        )

    def handle_raw_data(self, left, right):
        if hasattr(self.plot_page, "update_raw_plot"):
            self.plot_page.update_raw_plot(left, right)

        if self.recording_page.recorder.recording:
            self.recording_page.recorder.add_sample(left, right)

    def reset_settings(self):
        self.config["signal"] = copy.deepcopy(self.default_config["signal"])
        self.config["plot"] = copy.deepcopy(self.default_config["plot"])
        logger.info("Reset signal and plot settings to default.")

    def navigate_to(self, index):

        if index == 5:
            logger.info("Navigating to Drowsiness Monitor Page")
            self.reset_settings()
        elif index == 4:
            logger.info("Navigating to Recording Page")
            self.recording_page.user_label.setText(f"👤 User: {self.config.get('username', 'N/A')}")
        elif index == 3:
            logger.info("Navigating to PlotPage, starting visualization...")
            self.reset_settings()
            self.plot_page.update_username_label()
            self.plot_page.start_visualization()
        elif index == 2:
            logger.info("Navigating to Feature Selection Page")
            self.feature_page.update_username_label()
        elif index == 1:
            logger.info("Navigating to User Page")
        elif index == 0:
            logger.info("Navigating to Discovery Page")
            self.discovery_page.update_username_label()

        self.stack.setCurrentIndex(index)
