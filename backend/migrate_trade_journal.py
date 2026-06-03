"""
Migration script: add company_name, mood, updated_at columns to trade_journal table.
Run once: python migrate_trade_journal.py
Safe to run multiple times — uses ALTER TABLE … ADD COLUMN which is ignored if column exists.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "stockapp.db"

MIGRATIONS = [
    "ALTER TABLE trade_journal ADD COLUMN company_name TEXT",
    "ALTER TABLE trade_journal ADD COLUMN mood TEXT",
    "ALTER TABLE trade_journal ADD COLUMN updated_at DATETIME",
]


def run():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for sql in MIGRATIONS:
        col_name = sql.split("ADD COLUMN")[1].strip().split()[0]
        # Check if column already exists
        cur.execute("PRAGMA table_info(trade_journal)")
        existing_cols = [row[1] for row in cur.fetchall()]
        if col_name in existing_cols:
            print(f"[SKIP] Column '{col_name}' already exists.")
        else:
            cur.execute(sql)
            print(f"[OK]   Added column '{col_name}' to trade_journal.")
    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    run()
