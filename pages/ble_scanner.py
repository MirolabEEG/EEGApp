# === ble_scanner.py ===
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from bleak import BleakScanner
import asyncio
import logging

logger = logging.getLogger(__name__)

class BLEScanner(QObject):
    devices_found = pyqtSignal(list)
    scan_failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.thread = QThread()
        self.moveToThread(self.thread)
        self.thread.started.connect(self.scan)

    def start(self):
        self.thread.start()

    def stop(self):
        self.thread.quit()
        self.thread.wait()

    def scan(self):
        try:
            asyncio.run(self.run_scan())
        except Exception as e:
            logger.exception("BLEScanner failed")
            self.scan_failed.emit(str(e))

    async def run_scan(self):
        try:
            devices = await BleakScanner.discover(timeout=5.0)
            device_list = [(d.name or "Unknown", d.address) for d in devices]
            logger.info(f"BLEScanner: {len(device_list)} device(s) found.")
            self.devices_found.emit(device_list)
        except Exception as e:
            logger.exception("BLEScanner async scan failed")
            self.scan_failed.emit(str(e))
