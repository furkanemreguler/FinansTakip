"""
Yan yana, tek bir grup gibi görünen pil butonlar (segmented control).
Tema anahtarı (Açık/Koyu), grafik modu (Toplam/Sadece kalem) ve
para birimi (TL/USD) anahtarlarının hepsi bu bileşeni kullanır —
böylece "buton duruşu" uygulama genelinde tutarlı kalır.
"""
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QButtonGroup
from PySide6.QtCore import Signal, Qt


class SegmentedControl(QFrame):
    value_changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], default: str | None = None):
        """options: [(value, label), ...]"""
        super().__init__()
        self.setObjectName("segmentedControl")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}

        for value, label in options:
            btn = QPushButton(label)
            btn.setProperty("variant", "segment")
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, v=value: self.value_changed.emit(v))
            layout.addWidget(btn)
            self.group.addButton(btn)
            self.buttons[value] = btn

        if default and default in self.buttons:
            self.buttons[default].setChecked(True)

    def set_value(self, value: str):
        if value in self.buttons:
            self.buttons[value].setChecked(True)

    def set_label(self, value: str, label: str):
        if value in self.buttons:
            self.buttons[value].setText(label)

    def set_enabled_option(self, value: str, enabled: bool):
        if value in self.buttons:
            self.buttons[value].setEnabled(enabled)