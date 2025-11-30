import asyncio
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from bleak import BleakClient, BleakScanner
import logging
import time

logger = logging.getLogger(__name__)

class EEGWorker(QObject):
    update_log = pyqtSignal(str)
    update_signal = pyqtSignal(int, int)
    update_raw = pyqtSignal(float, float)
    update_med_att = pyqtSignal(str, int, int)
    connection_failed = pyqtSignal(str)
    update_sampling_rate = pyqtSignal(str, float)

    def __init__(self, device_address, uuids):
        super().__init__()
        self.device_address = device_address
        self.uuids = uuids
        self.buffers = {uuid: bytearray() for uuid in uuids.values()}
        self.signal_quality_long = {uuid: 0 for uuid in uuids.values()}
        self.packet_counts = {uuid: 0 for uuid in uuids.values()}
        self.poor_counts = {uuid: 0 for uuid in uuids.values()}
        self.start_times = {uuid: time.time() for uuid in uuids.values()}
        self.running = False
        self.thread = None

    def start(self):
        logger.info(f"Starting EEGWorker thread for {self.device_address}")
        self.running = True
        self.thread = QThread()
        self.moveToThread(self.thread)
        self.thread.started.connect(self.run)
        self.thread.start()

    def stop(self):
        logger.info("Stopping EEGWorker thread...")
        self.running = False
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()
            logger.info("EEGWorker thread stopped.")

    async def connect_and_listen(self):
        try:
            logger.info(f"Connecting to {self.device_address}...")
            device = await BleakScanner.find_device_by_address(self.device_address, timeout=10.0)
            if not device:
                raise Exception(f"Device with address {self.device_address} was not found.")

            async with BleakClient(device) as client:
                self.update_log.emit(f"Connected to {self.device_address}")

                for uuid in self.uuids.values():
                    await client.start_notify(
                        uuid,
                        lambda sender, data, uuid=uuid: asyncio.create_task(
                            self.notification_handler(uuid, sender, data)
                        )
                    )
                    logger.info(f"Started notify on {uuid}")

                while self.running:
                    await asyncio.sleep(0.1)

                for uuid in self.uuids.values():
                    await client.stop_notify(uuid)

                await client.disconnect()
                self.update_log.emit("Disconnected.")
                logger.info("Disconnected from device.")

        except asyncio.TimeoutError:
            msg = f"BLE connection error: Timeout while connecting to {self.device_address}"
            logger.error(msg)
            self.update_log.emit(msg)
            self.connection_failed.emit(msg)

        except Exception as e:
            msg = f"BLE connection error: {e}"
            logger.exception(msg)
            self.update_log.emit(msg)
            self.connection_failed.emit(msg)

        finally:
            self.stop()

    def run(self):
        logger.info("EEGWorker event loop starting...")
        asyncio.run(self.connect_and_listen())

    async def notification_handler(self, uuid, sender, data):
        self.buffers[uuid] += data
        while b'\xAA\xAA' in self.buffers[uuid]:
            start_index = self.buffers[uuid].find(b'\xAA\xAA')
            if len(self.buffers[uuid]) > start_index + 2:
                packet_type = self.buffers[uuid][start_index + 2]
                if packet_type == 0x04 and len(self.buffers[uuid]) >= start_index + 8:
                    packet = self.buffers[uuid][start_index:start_index + 8]
                    self.process_short_packet(uuid, packet)
                    self.buffers[uuid] = self.buffers[uuid][start_index + 8:]
                elif packet_type == 0x20 and len(self.buffers[uuid]) >= start_index + 36:
                    packet = self.buffers[uuid][start_index:start_index + 36]
                    self.process_long_packet(uuid, packet)
                    self.buffers[uuid] = self.buffers[uuid][start_index + 36:]
                else:
                    self.buffers[uuid] = self.buffers[uuid][start_index + 1:]
            else:
                break

    def process_short_packet(self, uuid, packet):
        try:
            hex_packet = ' '.join(f'{byte:02X}' for byte in packet)
            high_byte = int(hex_packet[18:20], 16)
            low_byte = int(hex_packet[21:23], 16)
            raw_value = (high_byte << 8) | low_byte
            if raw_value >= 32768:
                raw_value -= 65536
            microvolts = raw_value * (1.8 / 4096) / 2000 * 1000

            if "b0" in uuid:
                self.update_raw.emit(microvolts, 0.0)
            elif "b1" in uuid:
                self.update_raw.emit(0.0, microvolts)

            self.packet_counts[uuid] += 1
            if "00" not in hex_packet[15:17]:
                self.poor_counts[uuid] += 1
            self.calculate_sampling_rate(uuid)

        except Exception as e:
            msg = f"Short packet error: {e}"
            logger.exception(msg)
            self.update_log.emit(msg)

    def process_long_packet(self, uuid, packet):
        try:
            hex_packet = ' '.join(f'{byte:02X}' for byte in packet)
            meditation = int(hex_packet[96:98], 16)
            attention = int(hex_packet[-5:-3], 16)
            long_signal_quality = int(hex_packet[12:14], 16)

            self.signal_quality_long[uuid] = long_signal_quality

            source = "Left" if "b0" in uuid else "Right"
            self.update_med_att.emit(source, meditation, attention)

            left_q = self.signal_quality_long.get(self.uuids.get("Left Ear"), 0)
            right_q = self.signal_quality_long.get(self.uuids.get("Right Ear"), 0)
            self.update_signal.emit(left_q, right_q)

            msg = f"[{uuid[-4:]}] Med: {meditation}, Att: {attention}, SQ: {long_signal_quality}"
            logger.info(msg)
            self.update_log.emit(msg)

        except Exception as e:
            msg = f"Long packet error: {e}"
            logger.exception(msg)
            self.update_log.emit(msg)

    def calculate_sampling_rate(self, uuid):
        current_time = time.time()
        elapsed_time = current_time - self.start_times[uuid]
        if elapsed_time >= 1.0:
            count = self.packet_counts[uuid]
            sampling_rate = count / elapsed_time
            poor_rate = self.poor_counts[uuid] / elapsed_time if elapsed_time > 0 else 0
            quality_percent = (poor_rate / sampling_rate) * 100 if sampling_rate > 0 else 0
            ear = [k for k, v in self.uuids.items() if v == uuid][0]

            logger.info(f"{ear} - Sampling Rate: {sampling_rate:.2f} Hz | Poor Signal: {quality_percent:.1f}%")
            self.update_log.emit(f"{ear} - Sampling Rate: {sampling_rate:.2f} Hz | Poor Signal: {quality_percent:.1f}%")

            if "b0" in uuid:
                self.update_sampling_rate.emit("Left", sampling_rate)
            elif "b1" in uuid:
                self.update_sampling_rate.emit("Right", sampling_rate)

            self.packet_counts[uuid] = 0
            self.poor_counts[uuid] = 0
            self.start_times[uuid] = current_time
