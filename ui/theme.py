"""
Tüm renkler bu dosyadaki iki sözlükten (LIGHT, DARK) gelir — kod içinde
başka hiçbir yerde hex renk kodu yazılmaz. Tema değişimi tek bir yerden
(build_stylesheet) tüm uygulamaya yayılır.

Görsel dil: soğuk nötr gri yüzeyler, tek mavi vurgu rengi, ferah yoğunluk,
14px yuvarlatılmış kartlar. Kartlar çerçeve yerine yumuşak gölgeyle
(apply_card_shadow) ayrışır; kenarlıklar sadece odak/etkileşim anında
belirir, sürekli görünmez.
"""
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget
from PySide6.QtGui import QColor

LIGHT = {
    "bg": "#f4f5f7",
    "surface": "#ffffff",
    "surface_alt": "#eef0f3",
    "border": "#dde1e6",
    "text_primary": "#1c1f24",
    "text_secondary": "#6b7280",
    "text_muted": "#9aa1ab",
    "accent": "#3b6ea5",
    "accent_hover": "#2f5980",
    "accent_soft": "#e6edf4",
    "danger": "#c0392b",
    "danger_hover": "#a3301f",
    "warning_bg": "#fdf3d8",
    "warning_border": "#e8c766",
    "warning_text": "#7a5c12",
}

DARK = {
    "bg": "#15171b",
    "surface": "#1d2025",
    "surface_alt": "#24272d",
    "border": "#30343b",
    "text_primary": "#e8e9ec",
    "text_secondary": "#9aa1ab",
    "text_muted": "#6b7280",
    "accent": "#6f9cc4",
    "accent_hover": "#5686ab",
    "accent_soft": "#22313d",
    "danger": "#e05c4c",
    "danger_hover": "#c0392b",
    "warning_bg": "#3a301a",
    "warning_border": "#7a5c12",
    "warning_text": "#e8c766",
}

FONT_FAMILY = '"Geist", -apple-system, "Segoe UI", sans-serif'
MONO_FONT_FAMILY = '"Geist Mono", "SF Mono", Menlo, monospace'


def apply_card_shadow(widget: QWidget, strength: float = 1.0) -> None:
    """Kartlara çerçeve yerine yumuşak bir gölge verir (kaldırma/elevation hissi)."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(28 * strength)
    shadow.setOffset(0, 3)
    shadow.setColor(QColor(15, 18, 24, int(50 * strength)))
    widget.setGraphicsEffect(shadow)


def build_stylesheet(t: dict) -> str:
    return f"""
QWidget {{
    background-color: {t['bg']};
    color: {t['text_primary']};
    font-family: {FONT_FAMILY};
    font-size: 13px;
}}

QLabel {{
    background: transparent;
    color: {t['text_primary']};
}}

QLabel[role="numeric"] {{
    font-family: {MONO_FONT_FAMILY};
}}

QFrame {{
    background-color: transparent;
    border: none;
}}

QFrame#card {{
    background-color: {t['surface']};
    border: none;
    border-radius: 14px;
}}

QFrame#topBar {{
    border: none;
    border-bottom: 1px solid {t['border']};
    background-color: {t['surface']};
}}

QFrame#tabBar {{
    border: none;
    border-bottom: 1px solid {t['border']};
    background-color: {t['bg']};
}}

QFrame#warningPanel {{
    background-color: {t['warning_bg']};
    border: 1px solid {t['warning_border']};
    border-radius: 10px;
}}

QLabel#warningText {{
    color: {t['warning_text']};
}}

QLineEdit, QDateEdit, QComboBox {{
    background-color: {t['surface_alt']};
    color: {t['text_primary']};
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 7px 11px;
    min-height: 20px;
    selection-background-color: {t['accent']};
}}

QLineEdit:hover, QDateEdit:hover, QComboBox:hover {{
    background-color: {t['border']};
}}

QLineEdit:focus, QDateEdit:focus, QComboBox:focus {{
    background-color: {t['surface']};
    border: 1px solid {t['accent']};
}}

QComboBox::drop-down, QDateEdit::drop-down {{
    border: none;
    width: 22px;
}}

QPushButton {{
    background-color: {t['accent']};
    color: #ffffff;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 8px 16px;
    min-height: 20px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {t['accent_hover']};
}}

QPushButton:pressed {{
    background-color: {t['accent_hover']};
    padding-top: 9px;
    padding-bottom: 7px;
}}

QPushButton:disabled {{
    background-color: {t['surface_alt']};
    color: {t['text_muted']};
}}

QPushButton[variant="secondary"] {{
    background-color: {t['surface_alt']};
    color: {t['text_primary']};
    border: 1px solid transparent;
}}

QPushButton[variant="secondary"]:hover {{
    background-color: {t['border']};
}}

QPushButton[variant="secondary"]:disabled {{
    background-color: {t['surface_alt']};
    color: {t['text_muted']};
}}

QPushButton[variant="destructive"] {{
    background-color: transparent;
    color: {t['text_secondary']};
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 6px 12px;
    min-height: 16px;
    font-weight: 500;
}}

QPushButton[variant="destructive"]:hover {{
    color: {t['danger']};
    background-color: {t['surface_alt']};
}}

QPushButton[variant="tab"] {{
    background-color: transparent;
    color: {t['text_secondary']};
    border: none;
    border-radius: 0;
    padding: 10px 16px;
    font-weight: 500;
}}

QPushButton[variant="tab"]:hover:!checked {{
    color: {t['text_primary']};
}}

QPushButton[variant="tab"]:checked {{
    color: {t['accent']};
    border-bottom: 2px solid {t['accent']};
}}

QFrame#segmentedControl {{
    background-color: {t['surface_alt']};
    border: none;
    border-radius: 10px;
}}

QPushButton[variant="segment"] {{
    background-color: transparent;
    color: {t['text_secondary']};
    border: none;
    border-radius: 8px;
    padding: 6px 14px;
    min-height: 18px;
    font-weight: 500;
}}

QPushButton[variant="segment"]:hover:!checked {{
    background-color: {t['border']};
    color: {t['text_primary']};
    border: none;
}}

QPushButton[variant="segment"]:checked {{
    background-color: {t['accent']};
    color: #ffffff;
    border: none;
}}

QPushButton[variant="segment"]:disabled {{
    color: {t['text_muted']};
    background-color: transparent;
    border: none;
}}

QPushButton[variant="page"] {{
    background-color: transparent;
    color: {t['text_secondary']};
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 4px 0px;
    min-height: 16px;
    font-weight: 500;
}}

QPushButton[variant="page"]:hover {{
    background-color: {t['surface_alt']};
    color: {t['text_primary']};
}}

QPushButton[variant="pageActive"] {{
    background-color: {t['accent_soft']};
    color: {t['accent']};
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 4px 0px;
    min-height: 16px;
    font-weight: 600;
}}

QTableWidget {{
    background-color: {t['surface']};
    border: none;
    border-radius: 14px;
    gridline-color: transparent;
    alternate-background-color: {t['surface_alt']};
    outline: none;
}}

QHeaderView::section {{
    background-color: transparent;
    color: {t['text_secondary']};
    padding: 8px;
    border: none;
    border-bottom: 1px solid {t['border']};
    font-weight: 500;
}}

QTableWidget::item {{
    padding: 8px 6px;
    border-bottom: 1px solid {t['border']};
    font-family: {MONO_FONT_FAMILY};
    outline: none;
}}

QTableWidget::item:selected {{
    background-color: {t['accent_soft']};
    color: {t['text_primary']};
}}

QTableWidget::item:focus {{
    outline: none;
    border-bottom: 1px solid {t['border']};
}}

QLabel#screenTitle {{
    font-size: 20px;
    font-weight: 600;
}}

QLabel#sectionTitle {{
    font-size: 13px;
    font-weight: 600;
    color: {t['text_secondary']};
}}

QLabel#hintText {{
    color: {t['text_muted']};
    font-size: 11px;
}}

QFrame#summaryCard {{
    background-color: {t['surface']};
    border: none;
    border-radius: 14px;
}}

QFrame#summaryCardHighlight {{
    background-color: {t['accent_soft']};
    border: none;
    border-radius: 14px;
}}

QLabel#cardTitle {{
    color: {t['text_secondary']};
    font-size: 12px;
}}

QLabel#cardValue {{
    font-size: 21px;
    font-weight: 800;
    font-family: {MONO_FONT_FAMILY};
}}

QLabel#cardSub {{
    color: {t['text_secondary']};
    font-size: 12px;
    font-family: {MONO_FONT_FAMILY};
}}

QLabel#placeholderText {{
    color: {t['text_muted']};
    font-size: 15px;
}}
"""