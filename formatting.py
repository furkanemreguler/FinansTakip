"""
Türkçe format kuralları:
- TL: "142.000 ₺" (ondalıksız, binlik ayraç nokta)
- USD: "$2.951" (ondalıksız, binlik ayraç nokta)
- Yüzde: "%73,6" (bir ondalık, virgül)
"""


def fmt_try(value: float) -> str:
    return f"{value:,.0f} ₺".replace(",", ".")


def fmt_usd(value: float) -> str:
    return f"${value:,.0f}".replace(",", ".")


def fmt_pct(value: float, decimals: int = 1) -> str:
    text = f"{value * 100:.{decimals}f}"
    return f"%{text}".replace(".", ",")


def fmt_rate(value: float) -> str:
    """Kur değeri için: 37,0500 gibi 4 ondalıklı gösterim."""
    return f"{value:.4f}".replace(".", ",")


def _tr_decimal(value: float, decimals: int) -> str:
    """Binlik ayraç nokta, ondalık ayraç virgül olacak şekilde biçimler."""
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


UNIT_SYMBOLS = {"try": "₺", "usd": "$", "eur": "€", "gram_altin": "gr"}
UNIT_LABELS = {"try": "TL", "usd": "USD", "eur": "EUR", "gram_altin": "Gram altın"}


def fmt_amount(value: float, unit: str) -> str:
    """Varlık miktarını birimine göre biçimler: TL ondalıksız, döviz/gram altın 2 ondalıklı."""
    if unit == "try":
        return fmt_try(value)
    if unit == "gram_altin":
        return f"{_tr_decimal(value, 2)} gr"
    symbol = UNIT_SYMBOLS.get(unit, "")
    return f"{symbol}{_tr_decimal(value, 2)}"


def parse_decimal(text: str) -> float:
    """Türkçe biçimli sayı girdisini ("1.250,50" gibi) float'a çevirir."""
    cleaned = text.strip().replace(".", "").replace(",", ".")
    return float(cleaned)


def fmt_qty(value: float) -> str:
    """Yatırım miktarı için: tam sayıysa ondalıksız, değilse sondaki sıfırlar
    atılmış en fazla 6 ondalıklı gösterim (örn. kripto miktarları için)."""
    if value == int(value):
        text = f"{int(value):,}"
    else:
        text = f"{value:,.6f}".rstrip("0").rstrip(".")
    return text.replace(",", "X").replace(".", ",").replace("X", ".")