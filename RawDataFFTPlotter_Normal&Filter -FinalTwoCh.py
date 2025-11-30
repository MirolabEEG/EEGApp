import asyncio
import time
import logging
from collections import deque
import queue
import matplotlib.pyplot as plt
import numpy as np
from bleak import BleakClient
from scipy.signal import butter, filtfilt
import ctypes

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ensure the application is running in an MTA (Multi-Threaded Apartment)
def set_mta():
    try:
        ctypes.windll.ole32.CoInitializeEx(0, 0x0)
    except AttributeError:
        pass  # If on non-Windows platform, do nothing

class BLEDevice:
    def __init__(self, address, uuids, data_queues):
        self.address = address
        self.uuids = uuids
        self.packet_counts = {uuid: 0 for uuid in uuids.values()}
        self.poor_counts = {uuid: 0 for uuid in uuids.values()}
        self.start_times = {uuid: time.time() for uuid in uuids.values()}
        self.buffers = {uuid: bytearray() for uuid in uuids.values()}
        self.signal_quality_ints = {uuid: 0 for uuid in uuids.values()}
        self.data_queues = data_queues

    def process_packet(self, uuid, packet):
        hex_packet = ' '.join(f'{byte:02X}' for byte in packet)
        self.packet_counts[uuid] += 1
        signal_quality = hex_packet[15:17]
        self.signal_quality_ints[uuid] = int(signal_quality, 16)
        if self.signal_quality_ints[uuid] == 0:
            self.poor_counts[uuid] += 1
        high_byte = hex_packet[18:20]
        low_byte = hex_packet[21:23]
        high_byte_int = int(high_byte, 16)
        low_byte_int = int(low_byte, 16)
        raw_value = (high_byte_int << 8) | low_byte_int
        if raw_value >= 32768:
            raw_value -= 65536
        raw_value_microvolts = raw_value * (1.8 / 4096) / 2000 * 1000
        self.data_queues[uuid].put(raw_value_microvolts)

    def calculate_sampling_rate(self, uuid):
        current_time = time.time()
        elapsed_time = current_time - self.start_times[uuid]
        if elapsed_time >= 1.0:
            sampling_rate = self.packet_counts[uuid] / elapsed_time
            poor_rate = self.poor_counts[uuid] / elapsed_time
            quality_percent = (poor_rate / sampling_rate) * 100
            ear = [k for k, v in self.uuids.items() if v == uuid][0]
            logging.info(f"{ear} - Sampling Rate: {sampling_rate:.2f}")
            self.packet_counts[uuid] = 0
            self.poor_counts[uuid] = 0
            self.start_times[uuid] = current_time

    async def notification_handler(self, uuid, sender, data):
        self.buffers[uuid] += data
        while b'\xAA\xAA' in self.buffers[uuid]:
            start_index = self.buffers[uuid].find(b'\xAA\xAA')
            packet_size = 8
            if len(self.buffers[uuid]) >= start_index + packet_size:
                packet = self.buffers[uuid][start_index:start_index + packet_size]
                self.process_packet(uuid, packet)
                self.buffers[uuid] = self.buffers[uuid][start_index + packet_size:]
            else:
                break
        self.calculate_sampling_rate(uuid)

    async def read_data_from_device(self):
        retry_attempts = 5
        while retry_attempts > 0:
            try:
                async with BleakClient(self.address) as client:
                    if not client.is_connected:
                        await client.connect()
                        logging.info(f"Connected to {self.address}")

                    try:
                        for ear, uuid in self.uuids.items():
                            await client.start_notify(uuid, lambda sender, data, uuid=uuid: asyncio.create_task(self.notification_handler(uuid, sender, data)))
                            logging.info(f"Subscribed to notifications from {ear}")
                        while True:
                            await asyncio.sleep(1)
                    except Exception as e:
                        logging.error(f"Failed to subscribe to notifications: {e}")
                        retry_attempts -= 1
                        if retry_attempts == 0:
                            return
                        logging.info("Retrying...")
                        await asyncio.sleep(5)
                    finally:
                        if client.is_connected:
                            for uuid in self.uuids.values():
                                await client.stop_notify(uuid)
                            await client.disconnect()
                            logging.info(f"Disconnected from {self.address}")
            except Exception as e:
                logging.error(f"Could not connect to {self.address}: {e}")
                retry_attempts -= 1
                if retry_attempts == 0:
                    return
                logging.info("Retrying...")
                await asyncio.sleep(5)

def butter_bandpass(lowcut, highcut, fs, order=2):
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    b, a = butter(order, [low, high], btype='band')
    return b, a

def butter_bandpass_filter(data, lowcut, highcut, fs, order=2):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = filtfilt(b, a, data)
    return y

def normalize(data):
    mean = np.mean(data)
    std = np.std(data)
    return (data - mean) / std

def compute_fft(data, sample_rate):
    n = len(data)
    freq = np.fft.fftfreq(n, d=1/sample_rate)
    fft_values = np.fft.fft(data)
    return freq[:n // 2], np.abs(fft_values)[:n // 2]

async def plot_data(data_queues, sample_rate=512, yscale='log'):
    plt.ion()
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2)
    lines = [ax.plot([], [], lw=2)[0] for ax in (ax1, ax2, ax3, ax4)]

    # Update labels for raw data
    ax1.set_ylim(-10, 10)
    ax1.set_xlim(0, 3000)
    ax1.set_xlabel("Sample")
    ax1.set_ylabel("Microvolts")
    ax1.set_title("Left Ear")

    ax2.set_ylim(-10, 10)
    ax2.set_xlim(0, 3000)
    ax2.set_xlabel("Sample")
    ax2.set_ylabel("Microvolts")
    ax2.set_title("Right Ear")

    # Update labels for FFT
    ax3.set_yscale(yscale)
    ax3.set_xlim(0, 60)
    ax3.set_ylim(1, 1000)  # Fixed y-axis scale
    ax3.set_xlabel("Frequency (Hz)")
    ax3.set_ylabel("Amplitude")
    ax3.set_title("FFT Left Ear")

    ax4.set_yscale(yscale)
    ax4.set_xlim(0, 60)
    ax4.set_ylim(1, 1000)  # Fixed y-axis scale
    ax4.set_xlabel("Frequency (Hz)")
    ax4.set_ylabel("Amplitude")
    ax4.set_title("FFT Right Ear")

    raw_values_microvolts = {uuid: deque(maxlen=3000) for uuid in data_queues}

    while True:
        for i, (uuid, queue) in enumerate(data_queues.items()):
            while not queue.empty():
                raw_values_microvolts[uuid].append(queue.get())

            ydata = list(raw_values_microvolts[uuid])
            if len(ydata) >= 33:
                ydata = normalize(ydata)
                ydata = butter_bandpass_filter(ydata, 0.5, 50, sample_rate)
                xdata = list(range(len(ydata)))
                lines[i].set_data(xdata, ydata)
                lines[i].axes.set_xlim(0, len(ydata))

                # Compute FFT and update plot
                freq, fft_values = compute_fft(ydata, sample_rate)
                lines[i + 2].set_data(freq, fft_values)
                lines[i + 2].axes.set_xlim(0, 100)
                lines[i + 2].axes.set_ylim(1, 3000)  # Ensure y-axis is fixed at 1000

        fig.canvas.draw()
        fig.canvas.flush_events()
        await asyncio.sleep(0.01)

async def main():
    #device_address = "E0:82:BB:70:3A:58"
    #device_address = "C2:90:85:D8:3B:F5"
    #device_address = "F3:82:BF:68:57:ED"
    #device_address = "C5:DC:44:A7:B6:68"
    #device_address = "D2:1A:13:C2:8D:67"
    device_address = "D4:F5:33:9A:E0:F6"



    uuids = {
        "Left Ear": "6e400003-b5b0-f393-e0a9-e50e24dcca9f",
        "Right Ear": "6e400003-b5b1-f393-e0a9-e50e24dcca9f"
    }
    data_queues = {uuid: queue.Queue() for uuid in uuids.values()}

    ble_device = BLEDevice(device_address, uuids, data_queues)
    await asyncio.gather(
        ble_device.read_data_from_device(),
        plot_data(data_queues, yscale='log')  # Change 'log' to 'linear' for linear scale
    )

if __name__ == "__main__":
    set_mta()
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
