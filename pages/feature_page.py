from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QButtonGroup, QSizePolicy
)
from PyQt5.QtCore import Qt
import logging

logger = logging.getLogger(__name__)

class FeaturePage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)

        # === TITLE ===
        title = QLabel("🧠 Select Feature to Visualize")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # === USER LABEL ===
        self.user_label = QLabel(f"👤 User: {self.main_window.config.get('username', 'N/A')}")
        self.user_label.setObjectName("UserLabel")
        self.user_label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.user_label)

        # === FEATURE BUTTONS ===
        self.feature_buttons = {}
        self.feature_group = QButtonGroup(self)
        self.feature_group.setExclusive(True)

        self.add_feature_button("🧠 Raw EEG + FFT", "raw_fft", layout)
        self.add_feature_button("🧘 Meditation", "meditation", layout)
        self.add_feature_button("🎯 Attention", "attention", layout)
        self.add_feature_button("🧪 Drowsiness Monitor", "drowsiness", layout)
        self.add_feature_button("🧐 Launch Recorder", "recorder", layout)

        layout.addSpacing(10)


        # === ACTION BUTTONS (Back / Continue) ===
        self.back_button = QPushButton("⬅ Back")
        self.back_button.setObjectName("BackButton")
        self.back_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.back_button.clicked.connect(self.go_back)

        self.continue_button = QPushButton("Continue ➔")
        self.continue_button.setObjectName("ContinueButton")
        self.continue_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.continue_button.clicked.connect(self.proceed)

        nav_layout = QHBoxLayout()
        nav_layout.addWidget(self.back_button)
        nav_layout.addWidget(self.continue_button)
        layout.addLayout(nav_layout)

        self.setLayout(layout)

    def add_feature_button(self, label, key, parent_layout):
        button = QPushButton(label)
        button.setCheckable(True)
        button.setObjectName(f"Feature_{key}")
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        button.setMinimumHeight(40)
        self.feature_group.addButton(button)
        self.feature_buttons[key] = button
        parent_layout.addWidget(button)

    def update_username_label(self):
        username = self.main_window.config.get("username", "N/A")
        self.user_label.setText(f"👤 User: {username}")

    def go_back(self):
        logger.info("User navigated back to Discovery Page.")
        self.main_window.navigate_to(0)

    def proceed(self):
        selected_button = self.feature_group.checkedButton()
        if not selected_button:
            logger.warning("No feature selected.")
            return

        key = [k for k, btn in self.feature_buttons.items() if btn == selected_button][0]
        logger.info(f"Selected feature: {key}")

        if key == "raw_fft":
            self.main_window.config["features"] = {"raw": True, "fft": True}
            self.main_window.navigate_to(3)
        elif key == "meditation":
            self.main_window.config["features"] = {"med": True}
            self.main_window.navigate_to(3)
        elif key == "attention":
            self.main_window.config["features"] = {"att": True}
            self.main_window.navigate_to(3)
        elif key == "drowsiness":
            self.main_window.navigate_to(5)
        elif key == "recorder":
            self.main_window.navigate_to(4)


    def launch_drowsiness_monitor(self):
        logger.info("User launched the Drowsiness Monitor.")
        self.main_window.navigate_to(5)

    def launch_recorder(self):
        logger.info("User launched the EEG recorder.")
        self.main_window.navigate_to(4)
