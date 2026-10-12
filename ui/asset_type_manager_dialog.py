"""
"Segmentleri yönet" modal'ı: mevcut varlık VE borç segmentleri (aktif+arşivli)
iki ayrı grup halinde listelenir, her satırda Arşivle/Geri al butonu vardır.
Altta yeni segment ekleme alanı var (ad + tür: Varlık/Borç + birim: TL / USD /
EUR / Gram altın).

Kapatıldığında types_changed sinyali yayılır, çağıran ekran listeyi yenilemelidir.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QScrollArea, QWidget, QFrame, QMessageBox
)
from PySide6.QtCore import Signal, Qt

import asset_repo
from formatting import UNIT_LABELS

UNIT_OPTIONS = [("try", "TL"), ("usd", "USD"), ("eur", "EUR"), ("gram_altin", "Gram altın")]
KIND_OPTIONS = [("asset", "Varlık"), ("debt", "Borç")]


class AssetTypeManagerDialog(QDialog):
    types_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Segmentleri Yönet")
        self.setMinimumWidth(460)
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Varlık ve Borç Segmentleri")
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
        self.new_item_input.setPlaceholderText("Yeni segment adı (örn. Kripto)")
        add_row.addWidget(self.new_item_input, stretch=1)

        self.new_item_kind = QComboBox()
        for value, label in KIND_OPTIONS:
            self.new_item_kind.addItem(label, value)
        add_row.addWidget(self.new_item_kind)

        self.new_item_unit = QComboBox()
        for value, label in UNIT_OPTIONS:
            self.new_item_unit.addItem(label, value)
        add_row.addWidget(self.new_item_unit)

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

    def _add_group_header(self, text: str):
        label = QLabel(text)
        label.setObjectName("hintText")
        self.list_layout.addWidget(label)

    def _add_type_row(self, t: dict):
        row = QHBoxLayout()

        name_label = QLabel(f"{t['name']} · {UNIT_LABELS.get(t['unit'], t['unit'])}")
        if not t["is_active"]:
            name_label.setObjectName("hintText")
        row.addWidget(name_label, stretch=1)

        if t["is_active"]:
            action_button = QPushButton("Arşivle")
            action_button.setProperty("variant", "secondary")
            action_button.clicked.connect(
                lambda checked=False, tid=t["id"]: self._on_toggle(tid, False)
            )
        else:
            action_button = QPushButton("Geri al")
            action_button.setProperty("variant", "secondary")
            action_button.clicked.connect(
                lambda checked=False, tid=t["id"]: self._on_toggle(tid, True)
            )
        action_button.setCursor(Qt.PointingHandCursor)
        row.addWidget(action_button)

        row_widget = QWidget()
        row_widget.setLayout(row)
        self.list_layout.addWidget(row_widget)

    def _refresh_list(self):
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        types = asset_repo.get_asset_types(include_archived=True)
        assets = [t for t in types if t["kind"] == "asset"]
        debts = [t for t in types if t["kind"] == "debt"]

        self._add_group_header("VARLIK SEGMENTLERİ")
        for t in assets:
            self._add_type_row(t)

        self._add_group_header("BORÇ SEGMENTLERİ")
        for t in debts:
            self._add_type_row(t)

    def _on_toggle(self, asset_type_id: int, make_active: bool):
        asset_repo.set_asset_type_active(asset_type_id, make_active)
        self._refresh_list()
        self.types_changed.emit()

    def _on_add_clicked(self):
        name = self.new_item_input.text().strip()
        if not name:
            return
        kind = self.new_item_kind.currentData()
        unit = self.new_item_unit.currentData()
        try:
            asset_repo.add_asset_type(name, unit, kind)
        except Exception:
            QMessageBox.warning(self, "Segment eklenemedi", "Bu isimde bir segment zaten var.")
            return
        self.new_item_input.clear()
        self._refresh_list()
        self.types_changed.emit()
