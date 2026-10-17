"""SQLite database layer for credit card transactions."""
import sqlite3
import os
from contextlib import contextmanager
from datetime import date

DB_PATH = os.environ.get("DB_PATH", "/app/data/credit_cards.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS statements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card TEXT NOT NULL,
            statement_date TEXT NOT NULL,
            opening_date TEXT,
            closing_date TEXT,
            cardholder TEXT,
            total_spend REAL DEFAULT 0,
            total_points INTEGER DEFAULT 0,
            filename TEXT,
            uploaded_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            statement_id INTEGER NOT NULL,
            card TEXT NOT NULL,
            transaction_date TEXT NOT NULL,
            posting_date TEXT,
            cardholder TEXT,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            points INTEGER DEFAULT 0,
            points_rate INTEGER DEFAULT 0,
            points_category TEXT DEFAULT '',
            FOREIGN KEY (statement_id) REFERENCES statements(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(transaction_date);
        CREATE INDEX IF NOT EXISTS idx_txn_card ON transactions(card);
        CREATE INDEX IF NOT EXISTS idx_txn_category ON transactions(points_category);
        CREATE INDEX IF NOT EXISTS idx_txn_statement ON transactions(statement_id);
        """)


def insert_statement(conn: sqlite3.Connection, data: dict) -> int:
    cur = conn.execute(
        """INSERT INTO statements (card, statement_date, opening_date, closing_date,
           cardholder, total_spend, total_points, filename)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["card"],
            data["statement_date"],
            data.get("opening_date"),
            data.get("closing_date"),
            data.get("cardholder"),
            data.get("total_spend", 0),
            data.get("total_points", 0),
            data.get("filename"),
        ),
    )
    return cur.lastrowid


def insert_transactions(conn: sqlite3.Connection, statement_id: int, card: str, txns: list[dict]):
    conn.executemany(
        """INSERT INTO transactions
           (statement_id, card, transaction_date, posting_date, cardholder,
            description, amount, points, points_rate, points_category)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                statement_id,
                card,
                t["transaction_date"],
                t.get("posting_date", ""),
                t.get("cardholder", ""),
                t["description"],
                t["amount"],
                t.get("points", 0),
                t.get("points_rate", 0),
                t.get("points_category", ""),
            )
            for t in txns
        ],
    )


def get_transactions(
    conn: sqlite3.Connection,
    start_date: str = None,
    end_date: str = None,
    card: str = None,
    category: str = None,
    vendor: str = None,
    limit: int = 5000,
    offset: int = 0,
) -> list[dict]:
    conditions = []
    params = []
    if start_date:
        conditions.append("t.transaction_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("t.transaction_date <= ?")
        params.append(end_date)
    if card:
        conditions.append("t.card = ?")
        params.append(card)
    if category:
        conditions.append("t.points_category = ?")
        params.append(category)
    if vendor:
        conditions.append("UPPER(t.description) LIKE ?")
        params.append(f"%{vendor.upper()}%")

    where = " AND ".join(conditions) if conditions else "1=1"
    params.extend([limit, offset])

    rows = conn.execute(
        f"""SELECT t.id, t.transaction_date, t.posting_date, t.cardholder,
                   t.description, t.amount, t.points, t.points_rate,
                   t.points_category, t.card
            FROM transactions t
            WHERE {where}
            ORDER BY t.transaction_date DESC, t.id DESC
            LIMIT ? OFFSET ?""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_daily_spending(conn: sqlite3.Connection, start_date: str = None, end_date: str = None, card: str = None) -> list[dict]:
    conditions = ["t.amount > 0"]
    params = []
    if start_date:
        conditions.append("t.transaction_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("t.transaction_date <= ?")
        params.append(end_date)
    if card:
        conditions.append("t.card = ?")
        params.append(card)

    where = " AND ".join(conditions)
    rows = conn.execute(
        f"""SELECT t.transaction_date as date, SUM(t.amount) as total
            FROM transactions t
            WHERE {where}
            GROUP BY t.transaction_date
            ORDER BY t.transaction_date""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_spending_by_category(conn: sqlite3.Connection, start_date: str = None, end_date: str = None) -> list[dict]:
    conditions = ["t.amount > 0"]
    params = []
    if start_date:
        conditions.append("t.transaction_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("t.transaction_date <= ?")
        params.append(end_date)

    where = " AND ".join(conditions)
    rows = conn.execute(
        f"""SELECT t.points_category as category, t.points_rate as rate,
                   t.transaction_date as date, SUM(t.amount) as total
            FROM transactions t
            WHERE {where}
            GROUP BY t.points_category, t.transaction_date
            ORDER BY t.transaction_date""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_spending_by_vendor(conn: sqlite3.Connection, start_date: str = None, end_date: str = None, top_n: int = 15) -> list[dict]:
    conditions = ["t.amount > 0"]
    params = []
    if start_date:
        conditions.append("t.transaction_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("t.transaction_date <= ?")
        params.append(end_date)

    where = " AND ".join(conditions)

    # Get top vendors by total spend
    top_vendors = conn.execute(
        f"""SELECT t.description as vendor, SUM(t.amount) as total
            FROM transactions t
            WHERE {where}
            GROUP BY t.description
            ORDER BY total DESC
            LIMIT ?""",
        params + [top_n],
    ).fetchall()
    vendor_names = [r["vendor"] for r in top_vendors]

    if not vendor_names:
        return []

    placeholders = ",".join(["?"] * len(vendor_names))
    rows = conn.execute(
        f"""SELECT t.description as vendor, t.transaction_date as date, SUM(t.amount) as total
            FROM transactions t
            WHERE {where} AND t.description IN ({placeholders})
            GROUP BY t.description, t.transaction_date
            ORDER BY t.transaction_date""",
        params + vendor_names,
    ).fetchall()
    return [dict(r) for r in rows]


def get_points_over_time(conn: sqlite3.Connection, start_date: str = None, end_date: str = None) -> list[dict]:
    conditions = ["t.points > 0"]
    params = []
    if start_date:
        conditions.append("t.transaction_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("t.transaction_date <= ?")
        params.append(end_date)

    where = " AND ".join(conditions)
    rows = conn.execute(
        f"""SELECT t.transaction_date as date, SUM(t.points) as points,
                   t.points_category as category
            FROM transactions t
            WHERE {where}
            GROUP BY t.transaction_date, t.points_category
            ORDER BY t.transaction_date""",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_statements(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM statements ORDER BY statement_date DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def delete_statement(conn: sqlite3.Connection, statement_id: int):
    conn.execute("DELETE FROM statements WHERE id = ?", (statement_id,))


def get_transaction_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]