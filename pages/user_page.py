import os
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QMessageBox, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt

logger = logging.getLogger(__name__)

USER_FILE = "users.txt"
CALIBRATION_DIR = "calibrations"

class UserPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(30, 20, 30, 20)

        # User label (top right)
        self.user_label = QLabel(f"👤 User: {self.main_window.config.get('username', 'N/A')}")
        self.user_label.setAlignment(Qt.AlignRight)
        self.user_label.setObjectName("UserLabel")
        layout.addWidget(self.user_label)

        # Title
        title = QLabel("👤 Welcome to EEG App")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        # Name input
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter your name")
        self.name_input.setObjectName("NameInput")
        layout.addWidget(self.name_input)

        # Add user button
        self.add_button = QPushButton("➕ Add User")
        self.add_button.setObjectName("AddUserButton")
        self.add_button.clicked.connect(self.add_user)
        layout.addWidget(self.add_button)

        layout.addSpacing(10)

        # User list
        self.user_list = QListWidget()
        self.user_list.setObjectName("UserList")
        self.load_users()
        layout.addWidget(self.user_list)

        # Select user button
        self.select_button = QPushButton("➡ Continue as Selected User")
        self.select_button.setObjectName("SelectUserButton")
        self.select_button.clicked.connect(self.select_user)
        layout.addWidget(self.select_button)

        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.setLayout(layout)

    def load_users(self):
        self.user_list.clear()
        if not os.path.exists(USER_FILE):
            return
        with open(USER_FILE, "r") as f:
            for line in f:
                name = line.strip()
                if name:
                    self.user_list.addItem(name)

    def add_user(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Input Error", "Name cannot be empty.")
            return

        existing = [self.user_list.item(i).text() for i in range(self.user_list.count())]
        if name in existing:
            QMessageBox.warning(self, "Duplicate", "This user already exists.")
            return

        with open(USER_FILE, "a") as f:
            f.write(name + "\n")
        self.load_users()
        self.name_input.clear()
        QMessageBox.information(self, "User Added", f"User '{name}' added successfully.")
        logger.info(f"New user added: {name}")

    def select_user(self):
        selected_item = self.user_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "No Selection", "Please select a user.")
            return

        username = selected_item.text()
        self.main_window.config["username"] = username
        logger.info(f"User selected: {username}")

        # No calibration required anymore
        self.main_window.pending_calibration = False


        self.main_window.navigate_to(0)  # → Go to Discovery Page
