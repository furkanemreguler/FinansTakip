"""
Uygulama kabuğu: üstte başlık + tema anahtarı, altında sekme çubuğu
(Gelir / Harcama / Yatırım / Varlık ve Borç), en altta seçili ekranın içeriği.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
    QFrame
)
from PySide6.QtCore import Signal, Qt

from ui.income_view import IncomeView
from ui.placeholder_view import PlaceholderView
from ui.segmented_control import SegmentedControl
from db import DB_PATH


class AppShell(QWidget):
    theme_changed = Signal(str)  # "light" | "dark"

    def __init__(self):
        super().__init__()
        self.tab_buttons: list[QPushButton] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_top_bar())
        layout.addWidget(self._build_tab_bar())

        self.stack = QStackedWidget()
        self.screens = [
            ("Gelir", IncomeView()),
            ("Harcama", PlaceholderView("Harcama")),
            ("Yatırım", PlaceholderView("Yatırım")),
            ("Varlık ve Borç", PlaceholderView("Varlık ve Borç")),
        ]
        for _, widget in self.screens:
            self.stack.addWidget(widget)
        layout.addWidget(self.stack, stretch=1)

        income_view = self.screens[0][1]
        self.theme_changed.connect(income_view.apply_theme)

        self._select_tab(0)

    def _build_top_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("topBar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 10, 16, 10)

        title = QLabel("Finans Takip")
        title.setStyleSheet("font-weight: 600; font-size: 14px;")
        layout.addWidget(title)
        layout.addStretch()

        db_label = QLabel(DB_PATH.name)
        db_label.setObjectName("hintText")
        layout.addWidget(db_label)
        layout.addSpacing(12)

        self.theme_toggle = SegmentedControl(
            [("light", "Açık"), ("dark", "Koyu")], default="light"
        )
        self.theme_toggle.value_changed.connect(self.theme_changed.emit)
        layout.addWidget(self.theme_toggle)

        return frame

    def _build_tab_bar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("tabBar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(4)

        names = ["Gelir", "Harcama", "Yatırım", "Varlık ve Borç"]
        for i, name in enumerate(names):
            btn = QPushButton(name)
            btn.setProperty("variant", "tab")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, idx=i: self._select_tab(idx))
            layout.addWidget(btn)
            self.tab_buttons.append(btn)

        layout.addStretch()
        return frame

    def _select_tab(self, index: int):
        for i, btn in enumerate(self.tab_buttons):
            btn.setChecked(i == index)
        self.stack.setCurrentIndex(index)