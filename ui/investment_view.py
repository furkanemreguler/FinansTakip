"""
Yatırım ekranı.

Bölümler (yukarıdan aşağı):
1. Başlık + araç filtresi + "Araçları yönet"
2. Her zaman görünen tek satırlık yeni işlem formu (Tarih, Araç, Alış/Satış,
   Miktar, Birim fiyat TL — Tutar anlık hesaplanıp gösterilir)
3. Beş özet kartı (Toplam alım, Toplam satım, Elde kalan maliyet,
   Gerçekleşen K/Z, İşlem sayısı)
4. Geçmiş işlemler tablosu (sayfalama, satır içi silme)

income_view'dan farklı olarak kur çekme yok — fiyat doğrudan TL olarak
girilir, ledger'dır (işlemler değişmez, sadece silinebilir).
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QDateEdit, QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QFrame,
    QHeaderView, QMessageBox, QAbstractItemView, QScrollArea, QSizePolicy
)
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor

import investment_repo
from formatting import fmt_try, fmt_qty, fmt_pct, parse_decimal
from ui.summary_card import SummaryCard
from ui.item_manager_dialog import ItemManagerDialog
from ui.segmented_control import SegmentedControl
from ui.theme import apply_card_shadow, LIGHT, DARK

PAGE_SIZE = 12
SIDE_LABELS = {"buy": "Alış", "sell": "Satış"}


class InvestmentView(QWidget):
    def __init__(self):
        super().__init__()
        self.filter_item_id: int | None = None  # None = Tüm araçlar
        self.current_page = 1
        self.entry_side = "buy"
        self._theme = DARK

        self._build_ui()
        self._reload_all()

    def apply_theme(self, mode: str):
        self._theme = DARK if mode == "dark" else LIGHT
        self._refresh_summary_and_table()

    # ---------- UI kurulum ----------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(16)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_entry_form())
        layout.addWidget(self._build_summary_section())
        layout.addWidget(self._build_history_table())

    def _build_header(self) -> QWidget:
        container = QWidget()
        top_row = QHBoxLayout(container)
        top_row.setContentsMargins(0, 0, 0, 0)

        title_col = QVBoxLayout()
        title = QLabel("Yatırım")
        title.setObjectName("screenTitle")
        title_col.addWidget(title)
        self.summary_hint = QLabel("")
        self.summary_hint.setObjectName("hintText")
        title_col.addWidget(self.summary_hint)
        top_row.addLayout(title_col)
        top_row.addStretch()

        top_row.addWidget(QLabel("Yatırım aracı"))
        self.filter_combo = QComboBox()
        self.filter_combo.currentIndexChanged.connect(self._on_filter_item_changed)
        top_row.addWidget(self.filter_combo)

        manage_button = QPushButton("Araçları yönet")
        manage_button.setProperty("variant", "secondary")
        manage_button.setCursor(Qt.PointingHandCursor)
        manage_button.clicked.connect(self._on_manage_items_clicked)
        top_row.addWidget(manage_button)

        return container

    def _build_entry_form(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        apply_card_shadow(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("Yeni işlem")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        form_row = QHBoxLayout()

        date_col = QVBoxLayout()
        date_col.addWidget(QLabel("Tarih"))
        self.entry_date = QDateEdit(QDate.currentDate())
        self.entry_date.setCalendarPopup(True)
        self.entry_date.setDisplayFormat("dd.MM.yyyy")
        date_col.addWidget(self.entry_date)
        form_row.addLayout(date_col)

        item_col = QVBoxLayout()
        item_col.addWidget(QLabel("Yatırım aracı"))
        self.entry_item_combo = QComboBox()
        item_col.addWidget(self.entry_item_combo)
        form_row.addLayout(item_col)

        side_col = QVBoxLayout()
        side_col.addWidget(QLabel("İşlem"))
        self.side_control = SegmentedControl(
            [("buy", "Alış"), ("sell", "Satış")], default="buy"
        )
        self.side_control.value_changed.connect(self._set_entry_side)
        side_col.addWidget(self.side_control)
        form_row.addLayout(side_col)

        qty_col = QVBoxLayout()
        qty_col.addWidget(QLabel("Miktar"))
        self.qty_input = QLineEdit()
        self.qty_input.setPlaceholderText("10")
        self.qty_input.textChanged.connect(self._update_total_preview)
        qty_col.addWidget(self.qty_input)
        form_row.addLayout(qty_col)

        price_col = QVBoxLayout()
        price_col.addWidget(QLabel("Birim fiyat (TL)"))
        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("245,50")
        self.price_input.textChanged.connect(self._update_total_preview)
        price_col.addWidget(self.price_input)
        form_row.addLayout(price_col)

        self.save_button = QPushButton("Kaydet")
        self.save_button.setMinimumWidth(110)
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.clicked.connect(self._on_save_clicked)
        form_row.addWidget(self.save_button, alignment=Qt.AlignBottom)

        layout.addLayout(form_row)

        self.total_preview = QLabel("Tutar: -")
        self.total_preview.setObjectName("hintText")
        layout.addWidget(self.total_preview)

        return frame

    def _build_summary_section(self) -> QWidget:
        widget = QWidget()
        grid = QGridLayout(widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        self.card_buy = SummaryCard("Toplam alım")
        self.card_sell = SummaryCard("Toplam satım")
        self.card_open = SummaryCard("Elde kalan maliyet")
        self.card_pnl = SummaryCard("Gerçekleşen K/Z", highlight=True)
        self.card_count = SummaryCard("İşlem sayısı")

        grid.addWidget(self.card_buy, 0, 0)
        grid.addWidget(self.card_sell, 0, 1)
        grid.addWidget(self.card_open, 0, 2)
        grid.addWidget(self.card_pnl, 0, 3)
        grid.addWidget(self.card_count, 0, 4)

        return widget

    def _build_history_table(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        apply_card_shadow(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)

        header_row = QHBoxLayout()
        title = QLabel("Geçmiş işlemler")
        title.setObjectName("sectionTitle")
        header_row.addWidget(title)
        header_row.addStretch()
        order_hint = QLabel("En yeni üstte")
        order_hint.setObjectName("hintText")
        header_row.addWidget(order_hint)
        layout.addLayout(header_row)

        # Kolonlar: Tarih, Araç, İşlem, Miktar, Birim fiyat, Tutar, Sil
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["TARİH", "ARAÇ", "İŞLEM", "MİKTAR", "BİRİM FİYAT", "TUTAR", ""]
        )
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(90)
        self.table.setColumnWidth(0, 120)  # Tarih
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Araç
        self.table.setColumnWidth(2, 90)   # İşlem
        self.table.setColumnWidth(3, 120)  # Miktar
        self.table.setColumnWidth(4, 130)  # Birim fiyat
        self.table.setColumnWidth(5, 140)  # Tutar
        self.table.setColumnWidth(6, 70)   # Sil

        LEFT_COLS = (0, 1, 2)
        RIGHT_COLS = (3, 4, 5)
        for col in LEFT_COLS:
            item = self.table.horizontalHeaderItem(col)
            if item is not None:
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for col in RIGHT_COLS:
            item = self.table.horizontalHeaderItem(col)
            if item is not None:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self.pagination_row = QHBoxLayout()
        layout.addLayout(self.pagination_row)

        return frame

    # ---------- Yardımcılar ----------

    def _refresh_item_combos(self):
        items = investment_repo.get_items()

        self.entry_item_combo.blockSignals(True)
        self.entry_item_combo.clear()
        for item in items:
            self.entry_item_combo.addItem(item["name"], item["id"])
        self.entry_item_combo.blockSignals(False)

        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem("Tüm araçlar", None)
        for item in items:
            self.filter_combo.addItem(item["name"], item["id"])
        self.filter_combo.blockSignals(False)

    def _set_entry_side(self, side: str):
        self.entry_side = side

    def _update_total_preview(self):
        try:
            qty = parse_decimal(self.qty_input.text()) if self.qty_input.text().strip() else 0
            price = parse_decimal(self.price_input.text()) if self.price_input.text().strip() else 0
            self.total_preview.setText(f"Tutar: {fmt_try(qty * price)}")
        except ValueError:
            self.total_preview.setText("Tutar: -")

    # ---------- Olaylar ----------

    def _on_manage_items_clicked(self):
        dialog = ItemManagerDialog(
            investment_repo, "Yatırım Araçları", "Yeni araç adı (örn. THYAO, BTC)", self
        )
        dialog.items_changed.connect(self._reload_all)
        dialog.exec()

    def _on_filter_item_changed(self):
        idx = self.filter_combo.currentIndex()
        self.filter_item_id = self.filter_combo.itemData(idx)
        self.current_page = 1
        self._refresh_summary_and_table()

    def _on_save_clicked(self):
        idx = self.entry_item_combo.currentIndex()
        if idx < 0:
            QMessageBox.warning(self, "Eksik bilgi", "Önce bir yatırım aracı ekle.")
            return
        item_id = self.entry_item_combo.itemData(idx)

        try:
            qty = parse_decimal(self.qty_input.text())
            if qty <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Geçersiz değer", "Miktar pozitif bir sayı olmalı.")
            return

        try:
            price = parse_decimal(self.price_input.text())
            if price <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Geçersiz değer", "Birim fiyat pozitif bir sayı olmalı.")
            return

        date_str = self.entry_date.date().toString("yyyy-MM-dd")
        investment_repo.add_transaction(date_str, item_id, self.entry_side, qty, price)

        self.qty_input.clear()
        self.price_input.clear()
        self._reload_all()

    def _on_delete_clicked(self, transaction_id: int):
        reply = QMessageBox.question(
            self, "İşlemi sil", "Bu yatırım işlemini silmek istediğine emin misin?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            investment_repo.delete_transaction(transaction_id)
            self._reload_all()

    def _on_page_changed(self, page: int):
        self.current_page = page
        self._refresh_table()

    # ---------- Yenileme ----------

    def _reload_all(self):
        self._refresh_item_combos()
        self.current_page = 1
        self._refresh_summary_and_table()

    def _refresh_summary_and_table(self):
        filter_name = self.filter_combo.currentText() if self.filter_combo.count() else "tüm araçlar"
        self.summary_hint.setText(filter_name.lower())

        summary = investment_repo.get_summary(self.filter_item_id)
        self.card_buy.set_value(fmt_try(summary["total_buy_try"]))
        self.card_sell.set_value(fmt_try(summary["total_sell_try"]))
        self.card_open.set_value(fmt_try(summary["open_cost_try"]))
        pnl = summary["realized_pnl_try"]
        sign = "+" if pnl > 0 else ""
        self.card_pnl.set_value(
            f"{sign}{fmt_try(pnl)}", f"{sign}{fmt_pct(summary['realized_pnl_pct'])}"
        )
        if pnl > 0:
            self.card_pnl.set_value_color(self._theme["success"])
        elif pnl < 0:
            self.card_pnl.set_value_color(self._theme["danger"])
        else:
            self.card_pnl.set_value_color(None)
        self.card_count.set_value(str(summary["count"]))

        self._refresh_table()

    def _refresh_table(self):
        all_txs = investment_repo.get_transactions(self.filter_item_id)

        total_pages = max(1, (len(all_txs) + PAGE_SIZE - 1) // PAGE_SIZE)
        self.current_page = min(self.current_page, total_pages)
        page_start = (self.current_page - 1) * PAGE_SIZE
        page_txs = all_txs[page_start: page_start + PAGE_SIZE]

        self.table.setRowCount(len(page_txs))
        for i, t in enumerate(page_txs):
            date_display = QDate.fromString(t["date"], "yyyy-MM-dd").toString("dd.MM.yyyy")

            date_item = QTableWidgetItem(date_display)
            date_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(i, 0, date_item)

            item_item = QTableWidgetItem(t["item_name"])
            item_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(i, 1, item_item)

            side_item = QTableWidgetItem(SIDE_LABELS.get(t["side"], t["side"]))
            side_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            if t["side"] == "sell":
                side_item.setForeground(QColor(self._theme["danger"]))
            self.table.setItem(i, 2, side_item)

            qty_item = QTableWidgetItem(fmt_qty(t["quantity"]))
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(i, 3, qty_item)

            price_item = QTableWidgetItem(fmt_try(t["price_try"]))
            price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(i, 4, price_item)

            total_item = QTableWidgetItem(fmt_try(t["total_try"]))
            total_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(i, 5, total_item)

            delete_button = QPushButton("Sil")
            delete_button.setProperty("variant", "destructive")
            delete_button.setCursor(Qt.PointingHandCursor)
            delete_button.setFixedHeight(28)
            delete_button.clicked.connect(
                lambda checked=False, tid=t["id"]: self._on_delete_clicked(tid)
            )
            delete_cell = QWidget()
            delete_cell_layout = QHBoxLayout(delete_cell)
            delete_cell_layout.setContentsMargins(0, 0, 0, 0)
            delete_cell_layout.setAlignment(Qt.AlignCenter)
            delete_cell_layout.addWidget(delete_button)
            self.table.setCellWidget(i, 6, delete_cell)

        self._resize_table_to_rows(len(page_txs))
        self._render_pagination(total_pages, len(all_txs))

    def _resize_table_to_rows(self, row_count: int):
        header_h = self.table.horizontalHeader().sizeHint().height()
        row_h = self.table.verticalHeader().defaultSectionSize()
        frame = self.table.frameWidth() * 2
        self.table.setFixedHeight(header_h + row_h * row_count + frame + 2)

    def _render_pagination(self, total_pages: int, total_records: int):
        while self.pagination_row.count():
            child = self.pagination_row.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        info_label = QLabel(f"{total_records} işlem")
        info_label.setObjectName("hintText")
        self.pagination_row.addWidget(info_label)
        self.pagination_row.addStretch()

        for page in range(1, total_pages + 1):
            btn = QPushButton(str(page))
            btn.setProperty("variant", "pageActive" if page == self.current_page else "page")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedSize(30, 30)
            btn.clicked.connect(lambda checked=False, p=page: self._on_page_changed(p))
            self.pagination_row.addWidget(btn)
