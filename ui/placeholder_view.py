from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class PlaceholderView(QWidget):
    def __init__(self, title: str):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel(f"{title}\n\nBu ekran henüz hazır değil.")
        label.setAlignment(Qt.AlignCenter)
        label.setObjectName("placeholderText")
        layout.addWidget(label)