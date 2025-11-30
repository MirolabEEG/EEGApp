from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox
from PyQt5.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("EEG Signal Processing Settings")
        self.setMinimumWidth(400)

        self.config = config

        layout = QVBoxLayout()

        self.downsample_cb = QCheckBox("Enable Downsampling")
        self.downsample_cb.setChecked(self.config.get("downsample", True))
        layout.addWidget(self.downsample_cb)

        rate_layout = QHBoxLayout()
        rate_layout.addWidget(QLabel("Original Rate (Hz):"))
        self.original_rate_spin = QSpinBox()
        self.original_rate_spin.setRange(128, 2048)
        self.original_rate_spin.setValue(self.config.get("original_rate", 512))
        rate_layout.addWidget(self.original_rate_spin)

        rate_layout.addWidget(QLabel("Target Rate (Hz):"))
        self.target_rate_spin = QSpinBox()
        self.target_rate_spin.setRange(64, 1024)
        self.target_rate_spin.setValue(self.config.get("target_rate", 128))
        rate_layout.addWidget(self.target_rate_spin)
        layout.addLayout(rate_layout)

        self.bandpass_cb = QCheckBox("Enable Bandpass Filter")
        self.bandpass_cb.setChecked(self.config.get("bandpass", True))
        layout.addWidget(self.bandpass_cb)

        band_layout = QHBoxLayout()
        band_layout.addWidget(QLabel("Low Cutoff (Hz):"))
        self.low_spin = QDoubleSpinBox()
        self.low_spin.setRange(0.1, 100.0)
        self.low_spin.setValue(self.config.get("bandpass_low", 0.5))
        band_layout.addWidget(self.low_spin)

        band_layout.addWidget(QLabel("High Cutoff (Hz):"))
        self.high_spin = QDoubleSpinBox()
        self.high_spin.setRange(0.1, 100.0)
        self.high_spin.setValue(self.config.get("bandpass_high", 50.0))
        band_layout.addWidget(self.high_spin)
        layout.addLayout(band_layout)

        filter_type_layout = QHBoxLayout()
        filter_type_layout.addWidget(QLabel("Filter Type:"))
        self.filter_type_combo = QComboBox()
        self.filter_type_combo.addItems(["butter", "cheby"])
        self.filter_type_combo.setCurrentText(self.config.get("filter_type", "butter"))
        filter_type_layout.addWidget(self.filter_type_combo)

        filter_type_layout.addWidget(QLabel("Order:"))
        self.filter_order_spin = QSpinBox()
        self.filter_order_spin.setRange(1, 10)
        self.filter_order_spin.setValue(self.config.get("filter_order", 4))
        filter_type_layout.addWidget(self.filter_order_spin)
        layout.addLayout(filter_type_layout)

        self.notch_cb = QCheckBox("Enable Notch Filter")
        self.notch_cb.setChecked(self.config.get("notch", True))
        layout.addWidget(self.notch_cb)

        notch_layout = QHBoxLayout()
        notch_layout.addWidget(QLabel("Notch Frequency (Hz):"))
        self.notch_spin = QSpinBox()
        self.notch_spin.setRange(10, 100)
        self.notch_spin.setValue(self.config.get("notch_freq", 50))
        notch_layout.addWidget(self.notch_spin)

        notch_layout.addWidget(QLabel("Q Factor:"))
        self.q_spin = QDoubleSpinBox()
        self.q_spin.setRange(1, 100)
        self.q_spin.setValue(self.config.get("notch_q", 30))
        notch_layout.addWidget(self.q_spin)
        layout.addLayout(notch_layout)

        self.normalize_cb = QCheckBox("Enable Normalization")
        self.normalize_cb.setChecked(self.config.get("normalize", True))
        layout.addWidget(self.normalize_cb)

        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def update_config(self):
        self.config["downsample"] = self.downsample_cb.isChecked()
        self.config["original_rate"] = self.original_rate_spin.value()
        self.config["target_rate"] = self.target_rate_spin.value()
        self.config["bandpass"] = self.bandpass_cb.isChecked()
        self.config["bandpass_low"] = self.low_spin.value()
        self.config["bandpass_high"] = self.high_spin.value()
        self.config["filter_type"] = self.filter_type_combo.currentText()
        self.config["filter_order"] = self.filter_order_spin.value()
        self.config["notch"] = self.notch_cb.isChecked()
        self.config["notch_freq"] = self.notch_spin.value()
        self.config["notch_q"] = self.q_spin.value()
        self.config["normalize"] = self.normalize_cb.isChecked()
