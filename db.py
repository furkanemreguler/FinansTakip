"""
SQLite veritabanı bağlantısı ve şema kurulumu.

Tablolar:
- income_items: gelir kalemleri (Maaş, Yemek Kartı, Prim vb.). Silinmez,
  is_active=0 ile arşivlenir; geçmiş kayıtlar bozulmadan kalır.
- income_records: her bir gelir kaydı. Kur, kayıt anında saklanır (rate),
  böylece geçmişe dönük kur değişimlerinden etkilenmez.
- asset_types: varlık VE borç segmentleri (Sodexo, Nakit, Banka hesabı, Gram
  altın, Dolar, Euro, Alacak, Kredi kartı + kullanıcının eklediği ek
  kalemler). kind sütunu 'asset' | 'debt' ayrımını yapar; unit sütunu
  'try' | 'usd' | 'eur' | 'gram_altin' birimini belirler.
- asset_balances: her asset_type için TEK bir güncel bakiye (ledger değil,
  anlık görüntü). TL dışındaki birimler güncel kurla çarpılarak TL
  karşılığı anlık hesaplanır, DB'de tutulmaz. Net varlık = toplam asset
  karşılığı - toplam debt karşılığı.
- investment_items: yatırım araçları (THYAO, BTC, Altın ETF vb.), kullanıcı
  serbestçe ekler. Silinmez, is_active=0 ile arşivlenir.
- investment_transactions: manuel girilen alım/satım işlemleri (ledger).
  Fiyat kayıt anında saklanır, sonradan değişmez.

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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS asset_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            unit TEXT NOT NULL,              -- 'try' | 'usd' | 'eur' | 'gram_altin'
            kind TEXT NOT NULL DEFAULT 'asset',  -- 'asset' | 'debt'
            is_active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 1000
        )
        """
    )
    # Migration: kind sütunu eklenmeden önce kurulmuş eski veritabanlarına ekle
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(asset_types)")}
    if "kind" not in existing_cols:
        conn.execute("ALTER TABLE asset_types ADD COLUMN kind TEXT NOT NULL DEFAULT 'asset'")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS asset_balances (
            asset_type_id INTEGER PRIMARY KEY,
            amount REAL NOT NULL DEFAULT 0,
            updated_at TEXT,
            FOREIGN KEY (asset_type_id) REFERENCES asset_types (id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS investment_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS investment_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,              -- ISO format: YYYY-MM-DD
            item_id INTEGER NOT NULL,
            side TEXT NOT NULL,              -- 'buy' | 'sell'
            quantity REAL NOT NULL,
            price_try REAL NOT NULL,         -- birim fiyat, kayıt anındaki TL
            FOREIGN KEY (item_id) REFERENCES investment_items (id)
        )
        """
    )
    conn.commit()

    # İlk kurulumda hiç kalem yoksa, "Maaş" varsayılan olarak eklensin
    existing = conn.execute("SELECT COUNT(*) AS c FROM income_items").fetchone()
    if existing["c"] == 0:
        conn.execute("INSERT INTO income_items (name, is_active) VALUES ('Maaş', 1)")
        conn.commit()

    # İlk kurulumda hiç varlık segmenti yoksa, varsayılan segmentler eklensin
    existing_assets = conn.execute("SELECT COUNT(*) AS c FROM asset_types").fetchone()
    if existing_assets["c"] == 0:
        default_types = [
            ("Sodexo", "try", "asset", 10),
            ("Nakit", "try", "asset", 20),
            ("Banka hesabı", "try", "asset", 30),
            ("Gram altın", "gram_altin", "asset", 40),
            ("Dolar", "usd", "asset", 50),
            ("Euro", "eur", "asset", 60),
            ("Alacak", "try", "asset", 70),
            ("Kredi kartı", "try", "debt", 10),
        ]
        conn.executemany(
            "INSERT INTO asset_types (name, unit, kind, is_active, sort_order) VALUES (?, ?, ?, 1, ?)",
            default_types,
        )
        conn.commit()
    else:
        # Eski kurulumlarda henüz borç segmenti yoksa "Kredi kartı" eklensin
        existing_debts = conn.execute(
            "SELECT COUNT(*) AS c FROM asset_types WHERE kind = 'debt'"
        ).fetchone()
        if existing_debts["c"] == 0:
            conn.execute(
                "INSERT INTO asset_types (name, unit, kind, is_active, sort_order) "
                "VALUES ('Kredi kartı', 'try', 'debt', 1, 10)"
            )
            conn.commit()

    conn.close()