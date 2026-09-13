"""
SQLite veritabanı bağlantısı ve şema kurulumu.

Tablolar:
- income_items: gelir kalemleri (Maaş, Yemek Kartı, Prim vb.). Silinmez,
  is_active=0 ile arşivlenir; geçmiş kayıtlar bozulmadan kalır.
- income_records: her bir gelir kaydı. Kur, kayıt anında saklanır (rate),
  böylece geçmişe dönük kur değişimlerinden etkilenmez.

Brüt USD, Net USD, net/brüt oranı, cutoff — bunlar TABLODA TUTULMAZ,
her zaman income_records.py içindeki fonksiyonlarla anlık hesaplanır.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "finans.sqlite"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS income_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS income_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,              -- ISO format: YYYY-MM-DD
            item_id INTEGER NOT NULL,
            gross_try REAL NOT NULL,
            net_try REAL NOT NULL,
            rate REAL NOT NULL,              -- kayıt anındaki USD/TRY kuru
            FOREIGN KEY (item_id) REFERENCES income_items (id)
        )
        """
    )
    conn.commit()

    # İlk kurulumda hiç kalem yoksa, "Maaş" varsayılan olarak eklensin
    existing = conn.execute("SELECT COUNT(*) AS c FROM income_items").fetchone()
    if existing["c"] == 0:
        conn.execute("INSERT INTO income_items (name, is_active) VALUES ('Maaş', 1)")
        conn.commit()

    conn.close()