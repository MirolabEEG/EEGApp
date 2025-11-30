from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QListWidget, QMessageBox, QHBoxLayout
from PyQt5.QtCore import Qt
from pages.ble_scanner import BLEScanner
import logging
import os

logger = logging.getLogger(__name__)

KNOWN_DEVICES_FILE = "known_devices.txt"
DEFAULT_KNOWN_DEVICES = [
    "F3:82:BF:68:57:ED",
    "C2:90:85:D8:3B:F5",
    "D4:F5:33:9A:E0:F6",
    "E0:82:BB:70:3A:58",
    "C5:DC:44:A7:B6:68",
    "D2:1A:13:C2:8D:67"
]

class DiscoveryPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.device_list = []
        self.selected_address = None
        self.ble_scanner = None
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                color: #333333;
                font-family: 'Segoe UI';
                font-size: 10pt;
            }
            QLabel#UserLabel {
                font-size: 10pt;
                color: #666666;
                padding: 2px;
            }
            QLabel#Title {
                font-size: 18px;
                font-weight: bold;
                color: #009688;
            }
            QPushButton {
                background-color: #009688;
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #00796b;
            }
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
            }
        """)
        self.init_ui()
        self.load_known_devices()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("🔍 Bluetooth Device Discovery")
        title.setObjectName("TitleLabel")

        self.user_label = QLabel(f"👤 User: {self.main_window.config.get('username', 'N/A')}")
        self.user_label.setObjectName("UserLabel")
        self.user_label.setAlignment(Qt.AlignRight)

        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.user_label)
        layout.addLayout(title_row)

        # Known Devices Section
        known_label = QLabel("📘 Known Devices")
        known_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(known_label)

        self.known_list_widget = QListWidget()
        self.known_list_widget.setObjectName("KnownList")
        layout.addWidget(self.known_list_widget)

        self.use_known_button = QPushButton("Use Selected Known Device")
        self.use_known_button.setObjectName("UseKnownButton")
        self.use_known_button.clicked.connect(self.use_known_device)
        layout.addWidget(self.use_known_button)

        # Scan Controls
        self.scan_button = QPushButton("🔄 Start Scan")
        self.scan_button.setObjectName("ScanButton")
        self.scan_button.clicked.connect(self.start_scan)
        layout.addWidget(self.scan_button)

        self.device_list_widget = QListWidget()
        self.device_list_widget.setObjectName("ScanList")
        self.device_list_widget.itemClicked.connect(self.device_selected)
        layout.addWidget(self.device_list_widget)

        self.connect_button = QPushButton("✅ Connect to Selected Device")
        self.connect_button.setObjectName("ConnectButton")
        self.connect_button.setEnabled(False)
        self.connect_button.clicked.connect(self.connect_device)
        layout.addWidget(self.connect_button)

        self.setLayout(layout)

    def load_known_devices(self):
        if not os.path.exists(KNOWN_DEVICES_FILE):
            with open(KNOWN_DEVICES_FILE, "w") as f:
                for addr in DEFAULT_KNOWN_DEVICES:
                    f.write(addr + "\n")

        self.known_list_widget.clear()
        with open(KNOWN_DEVICES_FILE, "r") as f:
            for line in f:
                address = line.strip()
                if address:
                    self.known_list_widget.addItem(address)

    def update_username_label(self):
        username = self.main_window.config.get("username", "N/A")
        self.user_label.setText(f"👤 User: {username}")

    def save_new_device(self, address):
        with open(KNOWN_DEVICES_FILE, "r") as f:
            known = {line.strip() for line in f}
        if address not in known:
            with open(KNOWN_DEVICES_FILE, "a") as f:
                f.write(address + "\n")
            logger.info(f"New device address saved to known list: {address}")
            self.load_known_devices()

    def start_scan(self):
        self.scan_button.setEnabled(False)
        self.device_list_widget.clear()
        self.device_list = []
        logger.info("Starting BLE scan via BLEScanner...")

        self.ble_scanner = BLEScanner()
        self.ble_scanner.devices_found.connect(self.on_devices_found)
        self.ble_scanner.scan_failed.connect(self.on_scan_failed)
        self.ble_scanner.start()

    def on_devices_found(self, devices):
        logger.info(f"BLEScanner found {len(devices)} devices.")
        self.device_list = devices
        self.device_list_widget.clear()

        for name, address in self.device_list:
            label = f"{name or 'Unnamed'} ({address})"
            self.device_list_widget.addItem(label)

        if not devices:
            QMessageBox.information(self, "No Devices", "No BLE devices found.")
            logger.warning("No BLE devices found.")

        self.scan_button.setEnabled(True)
        self.ble_scanner.stop()

    def on_scan_failed(self, error):
        logger.error(f"Scan failed: {error}")
        QMessageBox.critical(self, "Scan Error", error)
        self.scan_button.setEnabled(True)
        self.ble_scanner.stop()

    def device_selected(self, item):
        index = self.device_list_widget.row(item)
        self.selected_address = self.device_list[index][1]
        self.connect_button.setEnabled(True)
        logger.info(f"Selected device: {self.device_list[index]}")

    def connect_device(self):
        if self.selected_address:
            self.save_new_device(self.selected_address)
            self.main_window.config["device_address"] = self.selected_address
            logger.info(f"Connecting to selected device: {self.selected_address}")
            self.proceed_after_device_selection()

            
    def use_known_device(self):
        selected_item = self.known_list_widget.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "No Selection", "Please select a known device.")
            return
        address = selected_item.text()
        self.main_window.config["device_address"] = address
        logger.info(f"Using known device: {address}")
        self.proceed_after_device_selection()

    def proceed_after_device_selection(self):
        logger.info("Proceeding to Feature Page (calibration disabled).")
        self.main_window.navigate_to(2)  # Feature Page

