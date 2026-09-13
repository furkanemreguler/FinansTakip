"""
"Kalemleri yönet" modal'ı: mevcut kalemler (aktif+arşivli) listelenir,
her satırda Arşivle/Geri al butonu vardır. Altta yeni kalem ekleme alanı var.

Kapatıldığında items_changed sinyali yayılır, çağıran ekran dropdown'ları
ve tabloyu yenilemelidir.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QWidget, QFrame, QMessageBox
)
from PySide6.QtCore import Signal, Qt

import income_repo


class ItemManagerDialog(QDialog):
    items_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kalemleri Yönet")
        self.setMinimumWidth(420)
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Gelir Kalemleri")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        layout.addWidget(scroll)

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setSpacing(4)
        scroll.setWidget(self.list_container)

        add_row = QHBoxLayout()
        self.new_item_input = QLineEdit()
        self.new_item_input.setPlaceholderText("Yeni kalem adı (örn. İkramiye)")
        add_row.addWidget(self.new_item_input)

        add_button = QPushButton("Ekle")
        add_button.setCursor(Qt.PointingHandCursor)
        add_button.clicked.connect(self._on_add_clicked)
        add_row.addWidget(add_button)

        layout.addLayout(add_row)

        close_button = QPushButton("Kapat")
        close_button.setProperty("variant", "secondary")
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

    def _refresh_list(self):
        # Önceki satırları temizle
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        items = income_repo.get_items(include_archived=True)
        for item in items:
            row = QHBoxLayout()

            name_label = QLabel(item["name"])
            if not item["is_active"]:
                name_label.setObjectName("hintText")
            row.addWidget(name_label, stretch=1)

            if item["is_active"]:
                action_button = QPushButton("Arşivle")
                action_button.setProperty("variant", "secondary")
                action_button.clicked.connect(
                    lambda checked=False, iid=item["id"]: self._on_toggle(iid, False)
                )
            else:
                action_button = QPushButton("Geri al")
                action_button.setProperty("variant", "secondary")
                action_button.clicked.connect(
                    lambda checked=False, iid=item["id"]: self._on_toggle(iid, True)
                )
            action_button.setCursor(Qt.PointingHandCursor)
            row.addWidget(action_button)

            row_widget = QWidget()
            row_widget.setLayout(row)
            self.list_layout.addWidget(row_widget)

    def _on_toggle(self, item_id: int, make_active: bool):
        income_repo.set_item_active(item_id, make_active)
        self._refresh_list()
        self.items_changed.emit()

    def _on_add_clicked(self):
        name = self.new_item_input.text().strip()
        if not name:
            return
        try:
            income_repo.add_item(name)
        except Exception:
            QMessageBox.warning(self, "Kalem eklenemedi", "Bu isimde bir kalem zaten var.")
            return
        self.new_item_input.clear()
        self._refresh_list()
        self.items_changed.emit()