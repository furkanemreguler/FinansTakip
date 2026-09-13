"""
Gelir kalemleri (income_items) ve gelir kayıtları (income_records) için
CRUD işlemleri, ayrıca türetilmiş alanların (USD, oranlar) hesaplanması.
"""
from typing import Optional
from db import get_connection

MAAS_KALEM_ADI = "Maaş"  # sadece bu kalemde Brüt TL alanı gösterilir


# ---------- Kalemler ----------

def get_items(include_archived: bool = False) -> list:
    conn = get_connection()
    if include_archived:
        rows = conn.execute("SELECT * FROM income_items ORDER BY name ASC").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM income_items WHERE is_active = 1 ORDER BY name ASC"
        ).fetchall()
    conn.close()
    return rows


def add_item(name: str) -> int:
    name = name.strip()
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO income_items (name, is_active) VALUES (?, 1)", (name,)
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def set_item_active(item_id: int, is_active: bool) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE income_items SET is_active = ? WHERE id = ?", (int(is_active), item_id)
    )
    conn.commit()
    conn.close()


# ---------- Kayıtlar ----------

def _derive(gross_try: float, net_try: float, rate: float) -> dict:
    gross_usd = gross_try / rate if rate else 0
    net_usd = net_try / rate if rate else 0
    net_gross_pct = net_try / gross_try if gross_try else 0
    cutoff_pct = 1 - net_gross_pct
    return {
        "gross_usd": gross_usd, "net_usd": net_usd,
        "net_gross_pct": net_gross_pct, "cutoff_pct": cutoff_pct,
    }


def add_record(date: str, item_id: int, gross_try: float, net_try: float, rate: float) -> int:
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO income_records (date, item_id, gross_try, net_try, rate)
        VALUES (?, ?, ?, ?, ?)
        """,
        (date, item_id, gross_try, net_try, rate),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_record_rate(record_id: int, new_rate: float) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE income_records SET rate = ? WHERE id = ?", (new_rate, record_id)
    )
    conn.commit()
    conn.close()


def delete_record(record_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM income_records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()


def get_earliest_record_date() -> Optional[str]:
    conn = get_connection()
    row = conn.execute("SELECT MIN(date) AS d FROM income_records").fetchone()
    conn.close()
    return row["d"] if row and row["d"] else None


def get_records(
    start_date: Optional[str] = None, end_date: Optional[str] = None,
    item_id: Optional[int] = None,
) -> list:
    """
    Her satıra türetilmiş alanları (gross_usd, net_usd, net_gross_pct, cutoff_pct)
    ve kalem adını (item_name) ekleyerek döner. En yeni tarih üstte.
    """
    conn = get_connection()
    query = """
        SELECT r.*, i.name AS item_name
        FROM income_records r
        JOIN income_items i ON i.id = r.item_id
        WHERE 1=1
    """
    params: list = []
    if start_date:
        query += " AND r.date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND r.date <= ?"
        params.append(end_date)
    if item_id:
        query += " AND r.item_id = ?"
        params.append(item_id)
    query += " ORDER BY r.date DESC, r.id DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    result = []
    for row in rows:
        d = dict(row)
        d.update(_derive(row["gross_try"], row["net_try"], row["rate"]))
        result.append(d)
    return result


def get_summary(
    start_date: Optional[str] = None, end_date: Optional[str] = None,
    item_id: Optional[int] = None,
) -> dict:
    records = get_records(start_date, end_date, item_id)
    if not records:
        return {
            "total_gross_try": 0, "total_net_try": 0,
            "total_gross_usd": 0, "total_net_usd": 0,
            "avg_net_gross_pct": 0, "avg_cutoff_pct": 0, "count": 0,
        }
    total_gross_try = sum(r["gross_try"] for r in records)
    total_net_try = sum(r["net_try"] for r in records)
    total_gross_usd = sum(r["gross_usd"] for r in records)
    total_net_usd = sum(r["net_usd"] for r in records)
    avg_pct = total_net_try / total_gross_try if total_gross_try else 0
    return {
        "total_gross_try": total_gross_try,
        "total_net_try": total_net_try,
        "total_gross_usd": total_gross_usd,
        "total_net_usd": total_net_usd,
        "avg_net_gross_pct": avg_pct,
        "avg_cutoff_pct": 1 - avg_pct,
        "count": len(records),
    }


def get_monthly_series(item_id: Optional[int] = None) -> list:
    """
    Aynı ayın tüm kayıtlarını toplayıp aylık tek bir seri döner.
    Dönüş: [{"month": "2026-01", "net_try": ..., "net_usd": ...}, ...] eskiden yeniye.

    Not: net_usd, o ay içindeki kayıtların KENDİ kurlarıyla hesaplanmış net_usd
    değerlerinin toplamıdır (her kaydın kendi kuru kullanılır, tek bir "aylık kur"
    varsayılmaz) — bu da işlem bazlı doğruluğu korur.
    """
    records = get_records(item_id=item_id)
    monthly: dict = {}
    for r in records:
        month = r["date"][:7]  # "YYYY-MM"
        if month not in monthly:
            monthly[month] = {"net_try": 0.0, "net_usd": 0.0}
        monthly[month]["net_try"] += r["net_try"]
        monthly[month]["net_usd"] += r["net_usd"]

    return [
        {"month": m, "net_try": v["net_try"], "net_usd": v["net_usd"]}
        for m, v in sorted(monthly.items())
    ]