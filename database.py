import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "prices.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT    NOT NULL UNIQUE,
                name        TEXT    NOT NULL,
                target_price REAL   NOT NULL,
                current_price REAL,
                currency    TEXT    NOT NULL DEFAULT '$',
                is_active   INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                last_checked TEXT
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL REFERENCES products(id),
                price      REAL    NOT NULL,
                checked_at TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);
            CREATE INDEX IF NOT EXISTS idx_history_product ON price_history(product_id);
        """)


def add_product(url: str, name: str, target_price: float,
                current_price: Optional[float] = None,
                currency: str = "$") -> int:
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO products (url, name, target_price, current_price, currency)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                name          = excluded.name,
                target_price  = excluded.target_price,
                current_price = excluded.current_price,
                is_active     = 1
        """, (url, name, target_price, current_price, currency))
        product_id = cursor.lastrowid
        if current_price is not None:
            conn.execute("""
                INSERT INTO price_history (product_id, price)
                VALUES (?, ?)
            """, (product_id, current_price))
        return product_id


def get_active_products() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT * FROM products WHERE is_active = 1
        """).fetchall()


def get_product_by_id(product_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT * FROM products WHERE id = ?
        """, (product_id,)).fetchone()


def update_price(product_id: int, price: float) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute("""
            UPDATE products
            SET current_price = ?, last_checked = ?
            WHERE id = ?
        """, (price, now, product_id))
        conn.execute("""
            INSERT INTO price_history (product_id, price)
            VALUES (?, ?)
        """, (product_id, price))


def get_price_history(product_id: int, limit: int = 10) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT price, checked_at
            FROM price_history
            WHERE product_id = ?
            ORDER BY checked_at DESC
            LIMIT ?
        """, (product_id, limit)).fetchall()


def deactivate_product(product_id: int) -> None:
    with get_connection() as conn:
        conn.execute("""
            UPDATE products SET is_active = 0 WHERE id = ?
        """, (product_id,))


def remove_product(product_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM price_history WHERE product_id = ?", (product_id,))
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))


def get_all_products() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("""
            SELECT * FROM products ORDER BY created_at DESC
        """).fetchall()
