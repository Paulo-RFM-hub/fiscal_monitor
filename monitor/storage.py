import csv
import json
import os
import sqlite3
from datetime import datetime


DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "data", "monitor.db")


class MonitorStorage:
    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB
        self._ensure_database()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_database(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS monitors ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "name TEXT NOT NULL,"
                "url TEXT NOT NULL,"
                "selector TEXT,"
                "last_hash TEXT,"
                "last_status TEXT,"
                "last_checked TEXT,"
                "last_error TEXT"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS history ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "monitor_id INTEGER NOT NULL,"
                "checked_at TEXT NOT NULL,"
                "status TEXT NOT NULL,"
                "hash TEXT,"
                "error TEXT,"
                "FOREIGN KEY(monitor_id) REFERENCES monitors(id)"
                ")"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS config ("
                "key TEXT PRIMARY KEY,"
                "value TEXT"
                ")"
            )
            # Ensure 'color' column exists in monitors table (migration for older DBs)
            info = conn.execute("PRAGMA table_info(monitors)").fetchall()
            col_names = [row["name"] for row in info]
            if "color" not in col_names:
                conn.execute("ALTER TABLE monitors ADD COLUMN color TEXT")

    def add_monitor(self, name, url, selector=None):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO monitors (name, url, selector, last_status) VALUES (?, ?, ?, ?)",
                (name.strip(), url.strip(), selector.strip() if selector else None, "pending"),
            )

    def list_monitors(self):
        with self._connect() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM monitors ORDER BY id")]

    def get_monitor(self, monitor_id):
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM monitors WHERE id = ?", (monitor_id,)).fetchone()
            return dict(row) if row else None

    def update_check_result(self, monitor_id, status, new_hash=None, error=None):
        now = datetime.utcnow().isoformat() + "Z"
        with self._connect() as conn:
            conn.execute(
                "UPDATE monitors SET last_hash = ?, last_status = ?, last_checked = ?, last_error = ? WHERE id = ?",
                (new_hash, status, now, error, monitor_id),
            )
            conn.execute(
                "INSERT INTO history (monitor_id, checked_at, status, hash, error) VALUES (?, ?, ?, ?, ?)",
                (monitor_id, now, status, new_hash, error),
            )

    def get_history(self, monitor_id, limit=20):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM history WHERE monitor_id = ? ORDER BY checked_at DESC LIMIT ?",
                (monitor_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def import_from_csv(self, path):
        imported = 0
        with open(path, "r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            for values in reader:
                if len(values) < 2:
                    continue
                name, url = values[0].strip(), values[1].strip()
                if name.lower() in {"name", "nome"} and url.lower() in {"url", "link"}:
                    continue
                selector = values[2].strip() if len(values) > 2 and values[2].strip() else None
                if name and url:
                    self.add_monitor(name, url, selector)
                    imported += 1
        return imported

    def import_from_json(self, path):
        imported = 0
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            for item in data:
                name = item.get("name") or item.get("title")
                url = item.get("url")
                selector = item.get("selector") or item.get("sel")
                if name and url:
                    self.add_monitor(name, url, selector)
                    imported += 1
        return imported

    def delete_monitor(self, monitor_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM history WHERE monitor_id = ?", (monitor_id,))
            conn.execute("DELETE FROM monitors WHERE id = ?", (monitor_id,))

    def update_monitor(self, monitor_id, name, url, selector=None, color=None):
        with self._connect() as conn:
            conn.execute(
                "UPDATE monitors SET name = ?, url = ?, selector = ?, color = ? WHERE id = ?",
                (name.strip(), url.strip(), selector.strip() if selector else None, color.strip() if color else None, monitor_id),
            )

    def set_config(self, key, value):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value.strip()),
            )

    def get_config(self, key):
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
            return row[0] if row else None
