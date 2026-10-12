"""
Yatırım araçları (investment_items) ve alım/satım işlemleri
(investment_transactions) için CRUD işlemleri. income_records gibi bir
ledger'dır — her satır manuel girilen bir işlemdir, fiyat kayıt anında
saklanır ve sonradan değişmez.
"""
from typing import Optional
from db import get_connection

BUY = "buy"
SELL = "sell"


# ---------- Araçlar ----------

def get_items(include_archived: bool = False) -> list:
    conn = get_connection()
    if include_archived:
        rows = conn.execute("SELECT * FROM investment_items ORDER BY name ASC").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM investment_items WHERE is_active = 1 ORDER BY name ASC"
        ).fetchall()
    conn.close()
    return rows


def add_item(name: str) -> int:
    name = name.strip()
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO investment_items (name, is_active) VALUES (?, 1)", (name,)
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def set_item_active(item_id: int, is_active: bool) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE investment_items SET is_active = ? WHERE id = ?", (int(is_active), item_id)
    )
    conn.commit()
    conn.close()


# ---------- İşlemler ----------

def add_transaction(date: str, item_id: int, side: str, quantity: float, price_try: float) -> int:
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO investment_transactions (date, item_id, side, quantity, price_try)
        VALUES (?, ?, ?, ?, ?)
        """,
        (date, item_id, side, quantity, price_try),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def delete_transaction(transaction_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM investment_transactions WHERE id = ?", (transaction_id,))
    conn.commit()
    conn.close()


def get_transactions(item_id: Optional[int] = None) -> list:
    """Her satıra total_try (quantity * price_try) ve item_name eklenir. En yeni üstte."""
    conn = get_connection()
    query = """
        SELECT t.*, i.name AS item_name
        FROM investment_transactions t
        JOIN investment_items i ON i.id = t.item_id
        WHERE 1=1
    """
    params: list = []
    if item_id:
        query += " AND t.item_id = ?"
        params.append(item_id)
    query += " ORDER BY t.date DESC, t.id DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    result = []
    for row in rows:
        d = dict(row)
        d["total_try"] = d["quantity"] * d["price_try"]
        result.append(d)
    return result


def get_summary(item_id: Optional[int] = None) -> dict:
    txs = get_transactions(item_id)
    total_buy = sum(t["total_try"] for t in txs if t["side"] == BUY)
    total_sell = sum(t["total_try"] for t in txs if t["side"] == SELL)
    return {
        "total_buy_try": total_buy,
        "total_sell_try": total_sell,
        "net_try": total_buy - total_sell,
        "count": len(txs),
    }
