from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel

from ui.theme import apply_card_shadow


class SummaryCard(QFrame):
    def __init__(self, title: str, highlight: bool = False):
        super().__init__()
        self.setObjectName("summaryCardHighlight" if highlight else "summaryCard")
        apply_card_shadow(self, strength=0.7)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        layout.addWidget(self.title_label)

        self.value_label = QLabel("-")
        self.value_label.setObjectName("cardValue")
        layout.addWidget(self.value_label)

        self.sub_label = QLabel("")
        self.sub_label.setObjectName("cardSub")
        layout.addWidget(self.sub_label)

    def set_value(self, value: str, sub: str = ""):
        self.value_label.setText(value)
        self.sub_label.setText(sub)
        self.sub_label.setVisible(bool(sub))