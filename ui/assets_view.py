"""
Varlık ve Borç ekranı.

Bölümler (yukarıdan aşağı):
1. Başlık + "son güncelleme" bilgisi, sağda "Kurları yenile" + "Segmentleri yönet"
2. Dört özet kartı: Toplam varlık, Toplam borç, Net varlık (vurgulu) — her biri
   TL ana değer + USD karşılığı alt satırda — ve Tasarruf oranı (net varlığın
   şimdiye kadarki toplam net USD gelire oranı, income_repo'dan)
3. "Varlıklarım" (solda) ve "Borçlarım" (sağda, şimdilik sadece Kredi kartı)
   kartları yan yana, her biri sayfa genişliğinin yarısıyla sınırlı

Her segment için TEK güncel bakiye tutulur (asset_repo.set_balance upsert
yapar), ledger yok. TL dışındaki birimlerin TL karşılığı, MarketRatesWorker
ile arka planda çekilen güncel kurlarla anlık hesaplanır, DB'ye yazılmaz.
Net varlık = toplam varlık karşılığı - toplam borç karşılığı.
"""
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QMessageBox, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt

import asset_repo
import income_repo
from rates import MarketRatesWorker
from formatting import fmt_try, fmt_usd, fmt_pct, fmt_amount, fmt_rate, parse_decimal, UNIT_LABELS
from ui.summary_card import SummaryCard
from ui.theme import apply_card_shadow
from ui.asset_type_manager_dialog import AssetTypeManagerDialog

RATE_KEY_BY_UNIT = {"usd": "usd_try", "eur": "eur_try", "gram_altin": "gram_altin_try"}


class AssetRow(QFrame):
    """Tek bir segment satırı: ad/birim, miktar girişi, TL karşılığı."""

    def __init__(self, asset_type: dict, on_amount_committed):
        super().__init__()
        self.asset_type_id = asset_type["id"]
        self.unit = asset_type["unit"]
        self._on_amount_committed = on_amount_committed
        self._amount = asset_type["amount"]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)

        name_col = QVBoxLayout()
        name_label = QLabel(asset_type["name"])
        name_label.setStyleSheet("font-weight: 600;")
        name_col.addWidget(name_label)
        unit_label = QLabel(UNIT_LABELS.get(self.unit, self.unit))
        unit_label.setObjectName("hintText")
        name_col.addWidget(unit_label)
        name_col_widget = QWidget()
        name_col_widget.setLayout(name_col)
        name_col_widget.setMinimumWidth(130)
        layout.addWidget(name_col_widget)

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("0")
        self.amount_input.setFixedWidth(140)
        self.amount_input.setText(fmt_amount(self._amount, self.unit) if self._amount else "")
        self.amount_input.editingFinished.connect(self._on_editing_finished)
        layout.addWidget(self.amount_input)

        layout.addStretch()

        value_col = QVBoxLayout()
        value_col.setAlignment(Qt.AlignRight)
        self.value_label = QLabel("-")
        self.value_label.setObjectName("cardSub")
        self.value_label.setAlignment(Qt.AlignRight)
        value_col.addWidget(self.value_label)
        self.rate_label = QLabel("")
        self.rate_label.setObjectName("hintText")
        self.rate_label.setAlignment(Qt.AlignRight)
        value_col.addWidget(self.rate_label)
        value_col_widget = QWidget()
        value_col_widget.setLayout(value_col)
        value_col_widget.setMinimumWidth(120)
        layout.addWidget(value_col_widget)

    def _on_editing_finished(self):
        text = self.amount_input.text().strip()
        if not text:
            amount = 0.0
        else:
            try:
                amount = parse_decimal(text)
            except ValueError:
                QMessageBox.warning(self, "Geçersiz değer", "Miktar sayısal olmalı.")
                self.amount_input.setText(fmt_amount(self._amount, self.unit) if self._amount else "")
                return
        self._amount = amount
        self.amount_input.setText(fmt_amount(amount, self.unit) if amount else "")
        self._on_amount_committed(self.asset_type_id, amount)

    def refresh_value(self, rates: dict):
        value = asset_repo.compute_try_value(self.unit, self._amount, rates)
        self.value_label.setText("-" if value is None else fmt_try(value))

        rate_key = RATE_KEY_BY_UNIT.get(self.unit)
        if rate_key and rates.get(rate_key) is not None:
            unit_name = "gr" if self.unit == "gram_altin" else UNIT_LABELS.get(self.unit, "")
            self.rate_label.setText(f"1 {unit_name} = {fmt_rate(rates[rate_key])} ₺")
        else:
            self.rate_label.setText("")


class AssetsView(QWidget):
    def __init__(self):
        super().__init__()
        self.rates: dict = {}
        self.asset_rows: list[AssetRow] = []
        self.debt_rows: list[AssetRow] = []
        self._rates_worker: MarketRatesWorker | None = None

        self._build_ui()
        self._reload_all()
        self._fetch_rates()

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
        layout.addWidget(self._build_summary_section())
        layout.addWidget(self._build_segments_section())
        layout.addStretch()

    def _build_header(self) -> QWidget:
        container = QWidget()
        top_row = QHBoxLayout(container)
        top_row.setContentsMargins(0, 0, 0, 0)

        title_col = QVBoxLayout()
        title = QLabel("Varlık ve Borç")
        title.setObjectName("screenTitle")
        title_col.addWidget(title)

        self.updated_label = QLabel("Kurlar çekiliyor...")
        self.updated_label.setObjectName("hintText")
        title_col.addWidget(self.updated_label)

        top_row.addLayout(title_col)
        top_row.addStretch()

        refresh_button = QPushButton("Kurları yenile")
        refresh_button.setProperty("variant", "secondary")
        refresh_button.setCursor(Qt.PointingHandCursor)
        refresh_button.clicked.connect(self._fetch_rates)
        top_row.addWidget(refresh_button)

        manage_button = QPushButton("Segmentleri yönet")
        manage_button.setProperty("variant", "secondary")
        manage_button.setCursor(Qt.PointingHandCursor)
        manage_button.clicked.connect(self._on_manage_types_clicked)
        top_row.addWidget(manage_button)

        return container

    def _build_summary_section(self) -> QWidget:
        widget = QWidget()
        grid = QGridLayout(widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        self.card_assets = SummaryCard("Toplam varlık")
        self.card_debts = SummaryCard("Toplam borç")
        self.card_net = SummaryCard("Net varlık", highlight=True)
        self.card_ratio = SummaryCard("Tasarruf oranı")

        grid.addWidget(self.card_assets, 0, 0)
        grid.addWidget(self.card_debts, 0, 1)
        grid.addWidget(self.card_net, 0, 2)
        grid.addWidget(self.card_ratio, 0, 3)

        return widget

    def _build_segments_section(self) -> QWidget:
        """Varlıklarım (sol) ve Borçlarım (sağ) kartlarını yan yana, her biri
        sayfa genişliğinin yarısıyla sınırlı olacak şekilde yerleştirir."""
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)

        self.rows_card, self.asset_rows_layout = self._build_segment_card("Varlıklarım")
        row.addWidget(self.rows_card, 1, Qt.AlignTop)

        self.debts_card, self.debt_rows_layout = self._build_segment_card("Borçlarım")
        row.addWidget(self.debts_card, 1, Qt.AlignTop)

        return container

    def _build_segment_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("card")
        apply_card_shadow(frame)
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        outer.addWidget(title_label)

        rows_layout = QVBoxLayout()
        rows_layout.setContentsMargins(0, 6, 0, 0)
        rows_layout.setSpacing(0)
        outer.addLayout(rows_layout)

        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return frame, rows_layout

    # ---------- Yenileme ----------

    def _reload_all(self):
        self._rebuild_rows(
            self.asset_rows_layout, self.asset_rows,
            asset_repo.get_balances(kind="asset"),
        )
        self._rebuild_rows(
            self.debt_rows_layout, self.debt_rows,
            asset_repo.get_balances(kind="debt"),
        )
        self._refresh_summary()

    def _rebuild_rows(self, rows_layout: QVBoxLayout, rows: list, balances: list):
        while rows_layout.count():
            child = rows_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        rows.clear()

        for i, asset_type in enumerate(balances):
            if i > 0:
                divider = QFrame()
                divider.setFixedHeight(1)
                divider.setStyleSheet("background-color: rgba(128, 128, 128, 40);")
                rows_layout.addWidget(divider)

            row = AssetRow(asset_type, self._on_amount_committed)
            row.refresh_value(self.rates)
            rows_layout.addWidget(row)
            rows.append(row)

    def _refresh_summary(self):
        asset_balances = [{"unit": r.unit, "amount": r._amount} for r in self.asset_rows]
        debt_balances = [{"unit": r.unit, "amount": r._amount} for r in self.debt_rows]

        total_assets, missing_a = asset_repo.get_total_try(asset_balances, self.rates)
        total_debts, missing_d = asset_repo.get_total_try(debt_balances, self.rates)
        missing = missing_a + missing_d
        net = total_assets - total_debts

        usd_try = self.rates.get("usd_try")
        if usd_try:
            assets_sub = fmt_usd(total_assets / usd_try)
            debts_sub = fmt_usd(total_debts / usd_try)
            net_sub = fmt_usd(net / usd_try)
        else:
            assets_sub = debts_sub = net_sub = "-"
        if missing:
            net_sub += f" · {missing} segment için kur alınamadı"

        self.card_assets.set_value(fmt_try(total_assets), assets_sub)
        self.card_debts.set_value(fmt_try(total_debts), debts_sub)
        self.card_net.set_value(fmt_try(net), net_sub)

        self._refresh_savings_ratio(usd_try, net)

    def _refresh_savings_ratio(self, usd_try: float | None, net_try: float):
        """Tasarruf oranı: net varlığın (USD) şimdiye kadar kazanılan toplam
        net gelire (USD, tüm zamanlar) oranı. 'Şimdiye kadar ne kadar
        kazandım, bunun ne kadarı hâlâ elimde' sorusuna cevap verir."""
        total_income_usd = income_repo.get_summary()["total_net_usd"]

        if not total_income_usd:
            self.card_ratio.set_value("-", "Henüz gelir kaydı yok")
            return
        if not usd_try:
            self.card_ratio.set_value("-", "Kur bekleniyor")
            return

        net_usd = net_try / usd_try
        ratio = net_usd / total_income_usd
        self.card_ratio.set_value(
            fmt_pct(ratio), f"{fmt_usd(net_usd)} / {fmt_usd(total_income_usd)}"
        )

    def _fetch_rates(self):
        self.updated_label.setText("Kurlar çekiliyor...")
        self._rates_worker = MarketRatesWorker()
        self._rates_worker.finished.connect(self._on_rates_fetched)
        self._rates_worker.start()

    def _on_rates_fetched(self, rates: dict, errors: list):
        self.rates.update(rates)
        for row in (*self.asset_rows, *self.debt_rows):
            row.refresh_value(self.rates)
        self._refresh_summary()

        now = datetime.now().strftime("%H:%M")
        if errors:
            self.updated_label.setText(f"Son güncelleme {now} · {len(errors)} kur alınamadı")
        else:
            self.updated_label.setText(f"Son güncelleme {now}")

    # ---------- Olaylar ----------

    def _on_amount_committed(self, asset_type_id: int, amount: float):
        now_iso = datetime.now().isoformat(timespec="seconds")
        asset_repo.set_balance(asset_type_id, amount, now_iso)
        self._refresh_summary()

    def _on_manage_types_clicked(self):
        dialog = AssetTypeManagerDialog(self)
        dialog.types_changed.connect(self._reload_all)
        dialog.exec()
