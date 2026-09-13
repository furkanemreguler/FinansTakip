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