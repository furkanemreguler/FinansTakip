"""
Gelir ekranı.

Bölümler (yukarıdan aşağı):
1. Başlık + seçili aralık özeti, sağda tarih filtreleri + kalem filtresi + "Kalemleri yönet"
2. Her zaman görünen tek satırlık yeni kayıt formu (Brüt TL sadece "Maaş" kaleminde görünür)
3. Dört özet kartı
4. Aylık bar grafiği (Toplam gelir / Sadece [kalem] × USD / TL anahtarları)
5. Geçmiş kayıtlar tablosu (sayfalama, satır içi kur düzenleme, koşullu kolonlar)
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QDateEdit, QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QFrame,
    QHeaderView, QMessageBox, QAbstractItemView, QScrollArea, QSizePolicy
)
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtCharts import (
    QChart, QChartView, QAbstractBarSeries, QBarSeries, QBarSet,
    QBarCategoryAxis, QValueAxis,
)

import income_repo
from rates import RateFetchWorker
from formatting import fmt_try, fmt_usd, fmt_pct, fmt_rate
from ui.summary_card import SummaryCard
from ui.item_manager_dialog import ItemManagerDialog
from ui.segmented_control import SegmentedControl
from ui.theme import apply_card_shadow, LIGHT, DARK

PAGE_SIZE = 12
MONTHLY_CHART_MONTHS = 12
AY_KISALTMA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def month_label(yyyy_mm: str) -> str:
    year, month = yyyy_mm.split("-")
    return f"{AY_KISALTMA[int(month) - 1]} {year[2:]}"


class IncomeView(QWidget):
    def __init__(self):
        super().__init__()
        income_repo  # tablo zaten main.py'de init edildi

        self.filter_item_id: int | None = None      # None = Tüm kalemler
        self.chart_mode = "total"                     # "total" | "item"
        self.chart_currency = "try"                    # "try" | "usd"
        self.current_page = 1
        self._pending_record: dict | None = None       # kur beklenirken tutulan form verisi
        self._rate_worker: RateFetchWorker | None = None
        self._theme = DARK

        self._build_ui()
        self._reload_all()

    def apply_theme(self, mode: str):
        self._theme = DARK if mode == "dark" else LIGHT
        self._refresh_chart()

    # ---------- UI kurulum ----------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        # Kaydırma çubuğu görünmesin; fare tekerleği/trackpad ile kaydırma
        # yine çalışır (ScrollBarAlwaysOff sadece görünürlüğü kapatır).
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
        layout.addWidget(self._build_chart_section())
        layout.addWidget(self._build_history_table())

    def _build_header(self) -> QWidget:
        wrapper = QVBoxLayout()
        container = QWidget()
        container.setLayout(wrapper)

        top_row = QHBoxLayout()

        title_col = QVBoxLayout()
        title = QLabel("Gelir")
        title.setObjectName("screenTitle")
        title_col.addWidget(title)

        self.range_summary_label = QLabel("")
        self.range_summary_label.setObjectName("hintText")
        title_col.addWidget(self.range_summary_label)

        top_row.addLayout(title_col)
        top_row.addStretch()

        top_row.addWidget(QLabel("Başlangıç"))
        self.start_date = QDateEdit(QDate(2025, 1, 1))
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd.MM.yyyy")
        self.start_date.dateChanged.connect(self._on_filters_changed)
        top_row.addWidget(self.start_date)

        top_row.addWidget(QLabel("Bitiş"))
        self.end_date = QDateEdit(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("dd.MM.yyyy")
        self.end_date.dateChanged.connect(self._on_filters_changed)
        top_row.addWidget(self.end_date)

        top_row.addWidget(QLabel("Gelir kalemi"))
        self.filter_combo = QComboBox()
        self.filter_combo.currentIndexChanged.connect(self._on_filter_item_changed)
        top_row.addWidget(self.filter_combo)

        manage_button = QPushButton("Kalemleri yönet")
        manage_button.setProperty("variant", "secondary")
        manage_button.setCursor(Qt.PointingHandCursor)
        manage_button.clicked.connect(self._on_manage_items_clicked)
        top_row.addWidget(manage_button)

        wrapper.addLayout(top_row)
        return container

    def _build_entry_form(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        apply_card_shadow(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("Yeni gelir kaydı")
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
        item_col.addWidget(QLabel("Gelir kalemi"))
        self.entry_item_combo = QComboBox()
        self.entry_item_combo.currentTextChanged.connect(self._update_gross_field_visibility)
        item_col.addWidget(self.entry_item_combo)
        form_row.addLayout(item_col)

        # Düz QWidget yerine QFrame: aksi halde global "QWidget" QSS kuralından
        # sayfa zemin rengini (kartın beyaz/surface tonundan farklı) miras alıp
        # Brüt TL kutusunun köşelerinden/etrafından sızdırıyor, Net TL'den
        # farklı görünmesine yol açıyordu.
        self.gross_col_widget = QFrame()
        gross_col = QVBoxLayout(self.gross_col_widget)
        gross_col.setContentsMargins(0, 0, 0, 0)
        gross_col.addWidget(QLabel("Brüt TL"))
        self.gross_input = QLineEdit()
        self.gross_input.setPlaceholderText("120.000")
        gross_col.addWidget(self.gross_input)
        form_row.addWidget(self.gross_col_widget)

        net_col = QVBoxLayout()
        net_col.addWidget(QLabel("Net TL"))
        self.net_input = QLineEdit()
        self.net_input.setPlaceholderText("94.800")
        net_col.addWidget(self.net_input)
        form_row.addLayout(net_col)

        self.save_button = QPushButton("Kaydet")
        self.save_button.setMinimumWidth(110)
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.clicked.connect(self._on_save_clicked)
        form_row.addWidget(self.save_button, alignment=Qt.AlignBottom)

        layout.addLayout(form_row)

        hint = QLabel(
            "Kur, kayıt tarihine göre otomatik çekilir. Brüt/Net USD ve oranlar hesaplanır."
        )
        hint.setObjectName("hintText")
        layout.addWidget(hint)

        # Kur alınamazsa gösterilecek uyarı paneli (varsayılan gizli)
        self.warning_panel = QFrame()
        self.warning_panel.setObjectName("warningPanel")
        self.warning_panel.setVisible(False)
        warn_layout = QHBoxLayout(self.warning_panel)
        warn_layout.setContentsMargins(12, 10, 12, 10)

        self.warning_label = QLabel("")
        self.warning_label.setObjectName("warningText")
        self.warning_label.setWordWrap(True)
        warn_layout.addWidget(self.warning_label, stretch=1)

        self.manual_rate_input = QLineEdit()
        self.manual_rate_input.setPlaceholderText("Kur (örn. 37,05)")
        self.manual_rate_input.setFixedWidth(140)
        warn_layout.addWidget(self.manual_rate_input)

        save_rate_button = QPushButton("Kuru kaydet")
        save_rate_button.setCursor(Qt.PointingHandCursor)
        save_rate_button.clicked.connect(self._on_manual_rate_confirmed)
        warn_layout.addWidget(save_rate_button)

        cancel_button = QPushButton("Vazgeç")
        cancel_button.setProperty("variant", "secondary")
        cancel_button.setCursor(Qt.PointingHandCursor)
        cancel_button.clicked.connect(self._on_manual_rate_cancelled)
        warn_layout.addWidget(cancel_button)

        layout.addWidget(self.warning_panel)

        return frame

    def _build_summary_section(self) -> QWidget:
        widget = QWidget()
        grid = QGridLayout(widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        self.card_gross = SummaryCard("Toplam brüt")
        self.card_net = SummaryCard("Toplam net", highlight=True)
        self.card_ratio = SummaryCard("Ortalama net/brüt")
        self.card_count = SummaryCard("Kayıt sayısı")

        grid.addWidget(self.card_gross, 0, 0)
        grid.addWidget(self.card_net, 0, 1)
        grid.addWidget(self.card_ratio, 0, 2)
        grid.addWidget(self.card_count, 0, 3)

        return widget

    def _build_chart_section(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        apply_card_shadow(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)

        header_row = QHBoxLayout()

        title_col = QVBoxLayout()
        title = QLabel("Aylık seyir")
        title.setObjectName("sectionTitle")
        title_col.addWidget(title)
        self.chart_subtitle = QLabel("")
        self.chart_subtitle.setObjectName("hintText")
        title_col.addWidget(self.chart_subtitle)
        header_row.addLayout(title_col)
        header_row.addStretch()

        self.chart_mode_control = SegmentedControl(
            [("total", "Toplam gelir"), ("item", "Sadece kalem")], default="total"
        )
        self.chart_mode_control.set_enabled_option("item", False)
        self.chart_mode_control.value_changed.connect(self._set_chart_mode)
        header_row.addWidget(self.chart_mode_control)

        self.currency_control = SegmentedControl(
            [("try", "TL"), ("usd", "USD")], default="try"
        )
        self.currency_control.value_changed.connect(self._set_chart_currency)
        header_row.addWidget(self.currency_control)

        layout.addLayout(header_row)

        self.chart = QChart()
        self.chart.legend().setVisible(False)
        self.chart.setBackgroundVisible(False)
        chart_view = QChartView(self.chart)
        chart_view.setMinimumHeight(240)
        layout.addWidget(chart_view)

        return frame

    def _build_history_table(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        apply_card_shadow(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 16, 18, 16)

        header_row = QHBoxLayout()
        title = QLabel("Geçmiş kayıtlar")
        title.setObjectName("sectionTitle")
        header_row.addWidget(title)
        header_row.addStretch()
        order_hint = QLabel("En yeni üstte")
        order_hint.setObjectName("hintText")
        header_row.addWidget(order_hint)
        layout.addLayout(header_row)

        # Kolonlar: Tarih, Kalem, Brüt TL, Net TL, Net/Brüt, Kur, Net USD, Sil
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["TARİH", "KALEM", "BRÜT TL", "NET TL", "NET/BRÜT", "KUR", "NET USD", ""]
        )

        # Tablo, içinde bulunduğu kartın tam genişliğini kaplasın. Dikeyde Fixed:
        # yükseklik _refresh_table içinde gösterilen satır sayısına göre elle
        # hesaplanır, böylece tablonun kendi iç kaydırma çubuğu hiç devreye
        # girmez — taşma olursa sayfayı saran QScrollArea kaydırır.
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(90)
        # Hiçbir kolon içeriğe göre otomatik daraltılmasın (bkz. _refresh_table:
        # eskiden çağrılan resizeColumnsToContents kolonları içeriğe kilitleyip
        # başlıkları/kırpıyordu). Kalem kolonu kalan boşluğu Stretch ile alır,
        # diğerleri sabit-ama-yeterli genişlikte kalır.
        self.table.setColumnWidth(0, 120)   # Tarih
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Kalem
        self.table.setColumnWidth(2, 140)   # Brüt TL
        self.table.setColumnWidth(3, 140)   # Net TL
        self.table.setColumnWidth(4, 130)   # Net/Brüt
        self.table.setColumnWidth(5, 120)   # Kur
        self.table.setColumnWidth(6, 130)   # Net USD
        self.table.setColumnWidth(7, 70)    # Sil

        LEFT_COLS = (0, 1)
        RIGHT_COLS = (2, 3, 4, 5, 6)
        for col in LEFT_COLS:
            item = self.table.horizontalHeaderItem(col)
            if item is not None:
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for col in RIGHT_COLS:
            item = self.table.horizontalHeaderItem(col)
            if item is not None:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.table.verticalHeader().setVisible(False)
        # Sil butonu satır içine sığacak kadar yer olsun diye satır yüksekliği
        # sabitlendi; aksi halde buton içeriği hücreden taşıp "Sil" yazısı kırpılıyordu.
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setAlternatingRowColors(True)
        self.table.itemChanged.connect(self._on_table_item_changed)
        self._suppress_item_changed = False
        layout.addWidget(self.table)

        self.pagination_row = QHBoxLayout()
        layout.addLayout(self.pagination_row)

        return frame

    # ---------- Yardımcılar ----------

    def _selected_entry_item(self) -> tuple[int, str] | None:
        idx = self.entry_item_combo.currentIndex()
        if idx < 0:
            return None
        return self.entry_item_combo.itemData(idx), self.entry_item_combo.currentText()

    def _update_gross_field_visibility(self):
        is_maas = self.entry_item_combo.currentText() == income_repo.MAAS_KALEM_ADI
        self.gross_col_widget.setVisible(is_maas)

    def _refresh_item_combos(self):
        items = income_repo.get_items()

        self.entry_item_combo.blockSignals(True)
        self.entry_item_combo.clear()
        for item in items:
            self.entry_item_combo.addItem(item["name"], item["id"])
        self.entry_item_combo.blockSignals(False)
        self._update_gross_field_visibility()

        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItem("Tüm kalemler", None)
        for item in items:
            self.filter_combo.addItem(item["name"], item["id"])
        self.filter_combo.blockSignals(False)

    def _current_date_range(self) -> tuple[str, str]:
        return (
            self.start_date.date().toString("yyyy-MM-dd"),
            self.end_date.date().toString("yyyy-MM-dd"),
        )

    # ---------- Olaylar ----------

    def _on_manage_items_clicked(self):
        dialog = ItemManagerDialog(self)
        dialog.items_changed.connect(self._reload_all)
        dialog.exec()

    def _on_filters_changed(self):
        self.current_page = 1
        self._refresh_summary_and_table()
        self._refresh_chart()

    def _on_filter_item_changed(self):
        idx = self.filter_combo.currentIndex()
        self.filter_item_id = self.filter_combo.itemData(idx)
        self.current_page = 1
        self._apply_filter_item_state()
        self._refresh_summary_and_table()
        self._refresh_chart()

    def _apply_filter_item_state(self):
        """Kalem filtresi durumuna göre grafik modu butonunu senkronize eder.
        Hem kullanıcı filtreyi değiştirdiğinde hem de ekran ilk yüklendiğinde çağrılır.
        'Tüm kalemler' seçiliyken buton varsayılan olarak Maaş'ı hedefler."""
        if self.filter_item_id is None:
            self.chart_mode_control.set_label("item", f"Sadece {income_repo.MAAS_KALEM_ADI}")
        else:
            self.chart_mode_control.set_label("item", f"Sadece {self.filter_combo.currentText()}")
        self.chart_mode_control.set_enabled_option("item", True)

    def _maas_item_id(self) -> int | None:
        for item in income_repo.get_items():
            if item["name"] == income_repo.MAAS_KALEM_ADI:
                return item["id"]
        return None

    def _set_chart_mode(self, mode: str):
        self.chart_mode = mode
        self._refresh_chart()

    def _set_chart_currency(self, currency: str):
        self.chart_currency = currency
        self._refresh_chart()

    def _on_save_clicked(self):
        selected = self._selected_entry_item()
        if selected is None:
            QMessageBox.warning(self, "Eksik bilgi", "Önce bir gelir kalemi ekle.")
            return
        item_id, item_name = selected

        net_text = self.net_input.text().strip().replace(".", "").replace(",", ".")
        if not net_text:
            QMessageBox.warning(self, "Eksik bilgi", "Net TL girmelisin.")
            return
        try:
            net_try = float(net_text)
        except ValueError:
            QMessageBox.warning(self, "Geçersiz değer", "Net TL sayısal olmalı.")
            return

        if item_name == income_repo.MAAS_KALEM_ADI:
            gross_text = self.gross_input.text().strip().replace(".", "").replace(",", ".")
            if not gross_text:
                QMessageBox.warning(self, "Eksik bilgi", "Maaş kalemi için Brüt TL girmelisin.")
                return
            try:
                gross_try = float(gross_text)
            except ValueError:
                QMessageBox.warning(self, "Geçersiz değer", "Brüt TL sayısal olmalı.")
                return
        else:
            gross_try = net_try  # Maaş dışındaki kalemlerde brüt = net kabul edilir

        date_str = self.entry_date.date().toString("yyyy-MM-dd")

        self._pending_record = {
            "date": date_str, "item_id": item_id,
            "gross_try": gross_try, "net_try": net_try,
        }

        self.save_button.setEnabled(False)
        self.save_button.setText("Kur çekiliyor...")
        self.warning_panel.setVisible(False)

        self._rate_worker = RateFetchWorker(date_str)
        self._rate_worker.succeeded.connect(self._on_rate_fetched)
        self._rate_worker.failed.connect(self._on_rate_fetch_failed)
        self._rate_worker.start()

    def _on_rate_fetched(self, rate: float):
        self._finish_saving_record(rate)

    def _on_rate_fetch_failed(self, error_message: str):
        self.save_button.setEnabled(True)
        self.save_button.setText("Kaydet")
        self.warning_label.setText(
            f"{error_message}\nBu tarih için kuru elle girip devam edebilirsin."
        )
        self.warning_panel.setVisible(True)

    def _on_manual_rate_confirmed(self):
        rate_text = self.manual_rate_input.text().strip().replace(",", ".")
        try:
            rate = float(rate_text)
        except ValueError:
            QMessageBox.warning(self, "Geçersiz kur", "Kuru sayısal olarak gir.")
            return
        self.warning_panel.setVisible(False)
        self.manual_rate_input.clear()
        self._finish_saving_record(rate)

    def _on_manual_rate_cancelled(self):
        self.warning_panel.setVisible(False)
        self.manual_rate_input.clear()
        self._pending_record = None
        self.save_button.setEnabled(True)
        self.save_button.setText("Kaydet")

    def _finish_saving_record(self, rate: float):
        if not self._pending_record:
            return
        r = self._pending_record
        income_repo.add_record(r["date"], r["item_id"], r["gross_try"], r["net_try"], rate)
        self._pending_record = None

        self.gross_input.clear()
        self.net_input.clear()
        self.save_button.setEnabled(True)
        self.save_button.setText("Kaydet")

        self._reload_all()

    def _on_table_item_changed(self, table_item: QTableWidgetItem):
        if self._suppress_item_changed:
            return
        if table_item.column() != 5:  # sadece Kur kolonu düzenlenebilir
            return

        record_id = table_item.data(Qt.UserRole)
        new_text = table_item.text().strip().replace(",", ".")
        try:
            new_rate = float(new_text)
            if new_rate <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Geçersiz kur", "Kur pozitif bir sayı olmalı.")
            self._refresh_table()  # eski değere döndür
            return

        income_repo.update_record_rate(record_id, new_rate)
        self._refresh_summary_and_table()
        self._refresh_chart()

    def _on_delete_clicked(self, record_id: int):
        reply = QMessageBox.question(
            self, "Kaydı sil", "Bu gelir kaydını silmek istediğine emin misin?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            income_repo.delete_record(record_id)
            self._reload_all()

    def _on_page_changed(self, page: int):
        self.current_page = page
        self._refresh_table()

    # ---------- Yenileme ----------

    def _reload_all(self):
        self._refresh_item_combos()
        self._apply_filter_item_state()

        self.current_page = 1
        self._refresh_summary_and_table()
        self._refresh_chart()

    def _refresh_summary_and_table(self):
        start, end = self._current_date_range()
        filter_name = self.filter_combo.currentText() if self.filter_combo.count() else "tüm kalemler"
        self.range_summary_label.setText(
            f"{self.start_date.date().toString('dd.MM.yyyy')} – "
            f"{self.end_date.date().toString('dd.MM.yyyy')} · {filter_name.lower()}"
        )

        summary = income_repo.get_summary(start, end, self.filter_item_id)
        self.card_gross.set_value(
            fmt_try(summary["total_gross_try"]), fmt_usd(summary["total_gross_usd"])
        )
        self.card_net.set_value(
            fmt_try(summary["total_net_try"]), fmt_usd(summary["total_net_usd"])
        )
        self.card_ratio.set_value(
            fmt_pct(summary["avg_net_gross_pct"]), f"Cutoff {fmt_pct(summary['avg_cutoff_pct'])}"
        )
        self.card_count.set_value(str(summary["count"]))

        self._refresh_table()

    def _refresh_table(self):
        start, end = self._current_date_range()
        all_records = income_repo.get_records(start, end, self.filter_item_id)

        # Sayfalama
        total_pages = max(1, (len(all_records) + PAGE_SIZE - 1) // PAGE_SIZE)
        self.current_page = min(self.current_page, total_pages)
        page_start = (self.current_page - 1) * PAGE_SIZE
        page_records = all_records[page_start: page_start + PAGE_SIZE]

        show_gross_columns = self.filter_item_id is not None
        self.table.setColumnHidden(2, not show_gross_columns)  # Brüt TL
        self.table.setColumnHidden(4, not show_gross_columns)  # Net/Brüt

        self._suppress_item_changed = True
        self.table.setRowCount(len(page_records))
        for i, r in enumerate(page_records):
            date_display = QDate.fromString(r["date"], "yyyy-MM-dd").toString("dd.MM.yyyy")

            date_item = QTableWidgetItem(date_display)
            date_item.setFlags(date_item.flags() & ~Qt.ItemIsEditable)
            date_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(i, 0, date_item)

            item_item = QTableWidgetItem(r["item_name"])
            item_item.setFlags(item_item.flags() & ~Qt.ItemIsEditable)
            item_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(i, 1, item_item)

            gross_item = QTableWidgetItem(fmt_try(r["gross_try"]))
            gross_item.setFlags(gross_item.flags() & ~Qt.ItemIsEditable)
            gross_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(i, 2, gross_item)

            net_item = QTableWidgetItem(fmt_try(r["net_try"]))
            net_item.setFlags(net_item.flags() & ~Qt.ItemIsEditable)
            net_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(i, 3, net_item)

            pct_item = QTableWidgetItem(fmt_pct(r["net_gross_pct"]))
            pct_item.setFlags(pct_item.flags() & ~Qt.ItemIsEditable)
            pct_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(i, 4, pct_item)

            rate_item = QTableWidgetItem(fmt_rate(r["rate"]))
            rate_item.setData(Qt.UserRole, r["id"])
            rate_item.setFlags(rate_item.flags() | Qt.ItemIsEditable)
            rate_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(i, 5, rate_item)

            usd_item = QTableWidgetItem(fmt_usd(r["net_usd"]))
            usd_item.setFlags(usd_item.flags() & ~Qt.ItemIsEditable)
            usd_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(i, 6, usd_item)

            delete_button = QPushButton("Sil")
            delete_button.setProperty("variant", "destructive")
            delete_button.setCursor(Qt.PointingHandCursor)
            delete_button.setFixedHeight(28)
            delete_button.clicked.connect(
                lambda checked=False, rid=r["id"]: self._on_delete_clicked(rid)
            )
            # Buton doğrudan hücreye konursa hücreyi tümüyle kaplayıp
            # satırlar arasında kaymış görünüyordu; sarmalayıcı widget
            # üzerinden ortalayarak her satırda aynı hizada tutuyoruz.
            delete_cell = QWidget()
            delete_cell_layout = QHBoxLayout(delete_cell)
            delete_cell_layout.setContentsMargins(0, 0, 0, 0)
            delete_cell_layout.setAlignment(Qt.AlignCenter)
            delete_cell_layout.addWidget(delete_button)
            self.table.setCellWidget(i, 7, delete_cell)

        self._suppress_item_changed = False

        self._resize_table_to_rows(len(page_records))
        self._render_pagination(total_pages, len(all_records))

    def _resize_table_to_rows(self, row_count: int):
        """Tabloyu gösterilen satır sayısına göre boyutlandırır ki iç kaydırma
        çubuğu hiç gerekmesin; taşma varsa sayfayı saran QScrollArea kaydırır."""
        header_h = self.table.horizontalHeader().sizeHint().height()
        row_h = self.table.verticalHeader().defaultSectionSize()
        frame = self.table.frameWidth() * 2
        self.table.setFixedHeight(header_h + row_h * row_count + frame + 2)

    def _render_pagination(self, total_pages: int, total_records: int):
        while self.pagination_row.count():
            child = self.pagination_row.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        info_label = QLabel(f"{total_records} kayıt")
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

    def _refresh_chart(self):
        if self.chart_mode == "item":
            item_id_for_chart = (
                self.filter_item_id if self.filter_item_id is not None else self._maas_item_id()
            )
        else:
            item_id_for_chart = None
        series_data = income_repo.get_monthly_series(item_id_for_chart)[-MONTHLY_CHART_MONTHS:]

        if self.chart_mode == "total":
            mode_label = "toplam"
        elif self.filter_item_id is not None:
            mode_label = self.filter_combo.currentText().lower()
        else:
            mode_label = income_repo.MAAS_KALEM_ADI.lower()
        currency_label = "USD" if self.chart_currency == "usd" else "net TL"
        self.chart_subtitle.setText(f"{mode_label} · aylık {currency_label}")

        self.chart.removeAllSeries()
        for axis in self.chart.axes():
            self.chart.removeAxis(axis)

        if not series_data:
            return

        is_usd = self.chart_currency == "usd"

        bar_set = QBarSet("Gelir")
        categories = []
        for point in series_data:
            raw_value = point["net_usd"] if is_usd else point["net_try"]
            chart_value = raw_value if is_usd else raw_value / 1000
            bar_set.append(round(chart_value))
            categories.append(month_label(point["month"]))

        bar_set.setColor(QColor(self._theme["accent"]))
        bar_set.setLabelColor(QColor(self._theme["text_secondary"]))

        series = QBarSeries()
        series.append(bar_set)
        series.setLabelsVisible(True)
        series.setLabelsFormat("$@value" if is_usd else "@valueB ₺")
        series.setLabelsPosition(QAbstractBarSeries.LabelsPosition.LabelsOutsideEnd)
        self.chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsColor(QColor(self._theme["text_secondary"]))
        self.chart.addAxis(axis_x, Qt.AlignBottom)
        series.attachAxis(axis_x)

        max_value = max((bar_set.at(i) for i in range(bar_set.count())), default=0)
        axis_y = QValueAxis()
        axis_y.setRange(0, max_value * 1.25 if max_value else 1)
        axis_y.setVisible(False)
        self.chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_y)