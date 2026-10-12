"""
"Kalemleri yönet" modal'ı: mevcut kalemler (aktif+arşivli) listelenir,
her satırda Arşivle/Geri al butonu vardır. Altta yeni kalem ekleme alanı var.

Gelir kalemleri ve yatırım araçları aynı CRUD şeklini (get_items/add_item/
set_item_active) paylaştığı için bu dialog ikisi arasında repo modülü
parametresiyle paylaşılır — income_view ve investment_view ikisi de kullanır.

Kapatıldığında items_changed sinyali yayılır, çağıran ekran dropdown'ları
ve tabloyu yenilemelidir.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QWidget, QFrame, QMessageBox
)
from PySide6.QtCore import Signal, Qt


class ItemManagerDialog(QDialog):
    items_changed = Signal()

    def __init__(self, repo, section_title: str, placeholder: str, parent=None):
        """repo: get_items(include_archived)/add_item(name)/set_item_active(id, bool)
        fonksiyonlarını sağlayan modül (income_repo veya investment_repo)."""
        super().__init__(parent)
        self.repo = repo
        self._placeholder = placeholder
        self.setWindowTitle("Kalemleri Yönet")
        self.setMinimumWidth(420)
        self._build_ui(section_title)
        self._refresh_list()

    def _build_ui(self, section_title: str):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel(section_title)
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
        self.new_item_input.setPlaceholderText(self._placeholder)
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

        items = self.repo.get_items(include_archived=True)
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
        self.repo.set_item_active(item_id, make_active)
        self._refresh_list()
        self.items_changed.emit()

    def _on_add_clicked(self):
        name = self.new_item_input.text().strip()
        if not name:
            return
        try:
            self.repo.add_item(name)
        except Exception:
            QMessageBox.warning(self, "Kalem eklenemedi", "Bu isimde bir kalem zaten var.")
            return
        self.new_item_input.clear()
        self._refresh_list()
        self.items_changed.emit()