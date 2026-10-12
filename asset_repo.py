"""
Varlık VE borç segmentleri (asset_types) ve bunların güncel bakiyeleri
(asset_balances) için CRUD işlemleri. Gelir tarafındaki income_repo'dan
farklı olarak burada ledger yok — her segment için TEK bir güncel bakiye
tutulur. kind='asset' varlıkları, kind='debt' borçları temsil eder; ikisi
de aynı tabloda, aynı unit/bakiye mekaniğini paylaşır.
"""
from typing import Optional
from db import get_connection

VALID_UNITS = ("try", "usd", "eur", "gram_altin")
VALID_KINDS = ("asset", "debt")
CUSTOM_SORT_ORDER = 1000


# ---------- Segmentler ----------

def get_asset_types(kind: Optional[str] = None, include_archived: bool = False) -> list:
    conn = get_connection()
    query = "SELECT * FROM asset_types WHERE 1=1"
    params: list = []
    if not include_archived:
        query += " AND is_active = 1"
    if kind:
        query += " AND kind = ?"
        params.append(kind)
    query += " ORDER BY sort_order ASC, name ASC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def add_asset_type(name: str, unit: str, kind: str = "asset") -> int:
    name = name.strip()
    if unit not in VALID_UNITS:
        raise ValueError(f"Geçersiz birim: {unit}")
    if kind not in VALID_KINDS:
        raise ValueError(f"Geçersiz tür: {kind}")
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO asset_types (name, unit, kind, is_active, sort_order) VALUES (?, ?, ?, 1, ?)",
        (name, unit, kind, CUSTOM_SORT_ORDER),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def set_asset_type_active(asset_type_id: int, is_active: bool) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE asset_types SET is_active = ? WHERE id = ?",
        (int(is_active), asset_type_id),
    )
    conn.commit()
    conn.close()


# ---------- Bakiyeler ----------

def set_balance(asset_type_id: int, amount: float, updated_at: str) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO asset_balances (asset_type_id, amount, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(asset_type_id) DO UPDATE SET
            amount = excluded.amount,
            updated_at = excluded.updated_at
        """,
        (asset_type_id, amount, updated_at),
    )
    conn.commit()
    conn.close()


def get_balances(kind: Optional[str] = None) -> list:
    """
    Aktif her segment için {id, name, unit, kind, amount, updated_at} döner.
    Hiç bakiye girilmemişse amount=0, updated_at=None olur.
    """
    conn = get_connection()
    query = """
        SELECT t.id, t.name, t.unit, t.kind,
               COALESCE(b.amount, 0) AS amount,
               b.updated_at AS updated_at
        FROM asset_types t
        LEFT JOIN asset_balances b ON b.asset_type_id = t.id
        WHERE t.is_active = 1
    """
    params: list = []
    if kind:
        query += " AND t.kind = ?"
        params.append(kind)
    query += " ORDER BY t.sort_order ASC, t.name ASC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def compute_try_value(unit: str, amount: float, rates: dict) -> Optional[float]:
    """unit='try' ise direkt amount; aksi halde rates içindeki ilgili kur ile çarpar.
    Kur yoksa (henüz çekilmemiş/başarısız) None döner."""
    if unit == "try":
        return amount
    rate_key = {"usd": "usd_try", "eur": "eur_try", "gram_altin": "gram_altin_try"}.get(unit)
    rate = rates.get(rate_key) if rate_key else None
    if rate is None:
        return None
    return amount * rate


def get_total_try(balances: list, rates: dict) -> tuple:
    """Dönüş: (toplam_try, eksik_sayisi). eksik_sayisi, kuru alınamadığı için
    toplama katılamayan segment sayısıdır."""
    total = 0.0
    missing = 0
    for b in balances:
        value = compute_try_value(b["unit"], b["amount"], rates)
        if value is None:
            missing += 1
        else:
            total += value
    return total, missing
