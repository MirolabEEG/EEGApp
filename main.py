from PyQt5.QtWidgets import QApplication
from main_window import MainWindow
import sys
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("eeg_app.log", mode="w")
    ]
)

def load_stylesheet():
    style_path = os.path.join(os.path.dirname(__file__), "style.qss")
    if os.path.exists(style_path):
        with open(style_path, "r") as f:
            return f.read()
    else:
        logging.warning("⚠️ style.qss not found. Using default style.")
        return ""

if __name__ == "__main__":
    logging.info("Starting EEG App...")
    app = QApplication(sys.argv)
    app.setApplicationName("EEG Desktop App")

    # Apply Fluent-style theme
    app.setStyleSheet(load_stylesheet())

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
