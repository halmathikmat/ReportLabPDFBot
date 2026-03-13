"""
Database module — SQLite-backed persistent storage.
Handles users, companies, invoices, subscriptions, and discount campaigns.
"""

import sqlite3
import json
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "invoice_bot.db")

FREE_LIMIT = 5  # invoices allowed on free tier


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id        INTEGER PRIMARY KEY,
                    name      TEXT,
                    username  TEXT,
                    currency  TEXT    DEFAULT 'USD',
                    plan      TEXT    DEFAULT 'free',
                    pro_since TEXT,
                    created   TEXT
                );

                CREATE TABLE IF NOT EXISTS companies (
                    user_id   INTEGER PRIMARY KEY,
                    name      TEXT,
                    address   TEXT,
                    email     TEXT,
                    phone     TEXT,
                    website   TEXT,
                    tax_id    TEXT
                );

                CREATE TABLE IF NOT EXISTS invoices (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id        INTEGER,
                    type           TEXT,
                    number         TEXT,
                    date           TEXT,
                    due_date       TEXT,
                    currency       TEXT,
                    page_size      TEXT    DEFAULT 'A4',
                    client_name    TEXT,
                    client_address TEXT,
                    client_email   TEXT,
                    client_phone   TEXT,
                    tax_rate       REAL    DEFAULT 0,
                    discount       REAL    DEFAULT 0,
                    notes          TEXT,
                    items          TEXT,
                    company        TEXT,
                    created        TEXT
                );

                CREATE TABLE IF NOT EXISTS discount_campaigns (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    stars_price  INTEGER NOT NULL,
                    discount_pct INTEGER NOT NULL,
                    starts_at    TEXT    NOT NULL,
                    ends_at      TEXT    NOT NULL,
                    created_by   INTEGER,
                    active       INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS payments (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       INTEGER,
                    stars_paid    INTEGER,
                    campaign_id   INTEGER,
                    created       TEXT
                );
            """)

    # -- Users -----------------------------------------------------------------

    def ensure_user(self, user_id: int, name: str, username: str = ""):
        with self._conn() as conn:
            existing = conn.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO users (id, name, username, created) VALUES (?,?,?,?)",
                    (user_id, name, username or "", datetime.now().isoformat()),
                )
            else:
                conn.execute(
                    "UPDATE users SET name=?, username=? WHERE id=?",
                    (name, username or "", user_id),
                )

    def get_user(self, user_id: int):
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def get_all_free_users(self):
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM users WHERE plan='free'").fetchall()
            return [dict(r) for r in rows]

    def get_all_users(self):
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM users").fetchall()
            return [dict(r) for r in rows]

    def get_user_currency(self, user_id: int) -> str:
        with self._conn() as conn:
            row = conn.execute("SELECT currency FROM users WHERE id=?", (user_id,)).fetchone()
            return row["currency"] if row else "USD"

    def set_user_currency(self, user_id: int, currency: str):
        with self._conn() as conn:
            conn.execute("UPDATE users SET currency=? WHERE id=?", (currency, user_id))

    def get_user_plan(self, user_id: int) -> str:
        with self._conn() as conn:
            row = conn.execute("SELECT plan FROM users WHERE id=?", (user_id,)).fetchone()
            return row["plan"] if row else "free"

    def upgrade_to_pro(self, user_id: int):
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET plan='pro', pro_since=? WHERE id=?",
                (datetime.now().isoformat(), user_id),
            )

    def get_user_invoice_count(self, user_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM invoices WHERE user_id=?", (user_id,)
            ).fetchone()
            return row["c"] if row else 0

    def can_create_invoice(self, user_id: int):
        """Returns (allowed: bool, remaining: int). remaining=-1 means unlimited."""
        plan = self.get_user_plan(user_id)
        if plan == "pro":
            return True, -1
        count = self.get_user_invoice_count(user_id)
        remaining = FREE_LIMIT - count
        return remaining > 0, max(remaining, 0)

    # -- Companies -------------------------------------------------------------

    def save_company(self, user_id: int, data: dict):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO companies (user_id, name, address, email, phone, website, tax_id)
                VALUES (:uid,:name,:address,:email,:phone,:website,:tax_id)
                ON CONFLICT(user_id) DO UPDATE SET
                    name=:name, address=:address, email=:email,
                    phone=:phone, website=:website, tax_id=:tax_id
            """, {
                "uid":     user_id,
                "name":    data.get("name", ""),
                "address": data.get("address", ""),
                "email":   data.get("email", ""),
                "phone":   data.get("phone", ""),
                "website": data.get("website", ""),
                "tax_id":  data.get("tax_id", ""),
            })

    def get_company(self, user_id: int):
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM companies WHERE user_id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    # -- Invoices --------------------------------------------------------------

    def save_invoice(self, user_id: int, inv: dict) -> int:
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO invoices
                    (user_id, type, number, date, due_date, currency, page_size,
                     client_name, client_address, client_email, client_phone,
                     tax_rate, discount, notes, items, company, created)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                user_id,
                inv.get("type", "Invoice"),
                inv.get("number", ""),
                inv.get("date", ""),
                inv.get("due_date", ""),
                inv.get("currency", "USD"),
                inv.get("page_size", "A4"),
                inv.get("client_name", ""),
                inv.get("client_address", ""),
                inv.get("client_email", ""),
                inv.get("client_phone", ""),
                inv.get("tax_rate", 0),
                inv.get("discount", 0),
                inv.get("notes", ""),
                json.dumps(inv.get("items", [])),
                json.dumps(inv.get("company", {})),
                datetime.now().isoformat(),
            ))
            return cur.lastrowid

    def get_invoices(self, user_id: int):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM invoices WHERE user_id=? ORDER BY id DESC LIMIT 50",
                (user_id,),
            ).fetchall()
            return [self._parse_invoice(r) for r in rows]

    def get_invoice(self, inv_id):
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM invoices WHERE id=?", (int(inv_id),)).fetchone()
            return self._parse_invoice(row) if row else None

    def delete_invoice(self, inv_id):
        with self._conn() as conn:
            conn.execute("DELETE FROM invoices WHERE id=?", (int(inv_id),))

    @staticmethod
    def _parse_invoice(row) -> dict:
        d = dict(row)
        d["items"]   = json.loads(d.get("items") or "[]")
        d["company"] = json.loads(d.get("company") or "{}")
        return d

    # -- Discount Campaigns ----------------------------------------------------

    def create_campaign(self, stars_price: int, discount_pct: int,
                        starts_at: str, ends_at: str, admin_id: int) -> int:
        with self._conn() as conn:
            conn.execute("UPDATE discount_campaigns SET active=0 WHERE active=1")
            cur = conn.execute("""
                INSERT INTO discount_campaigns
                    (stars_price, discount_pct, starts_at, ends_at, created_by, active)
                VALUES (?,?,?,?,?,1)
            """, (stars_price, discount_pct, starts_at, ends_at, admin_id))
            return cur.lastrowid

    def get_active_campaign(self):
        """Return campaign only if currently within its time window."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            row = conn.execute("""
                SELECT * FROM discount_campaigns
                WHERE active=1 AND starts_at <= ? AND ends_at >= ?
                ORDER BY id DESC LIMIT 1
            """, (now, now)).fetchone()
            return dict(row) if row else None

    def get_pending_campaign(self):
        """Return active campaign regardless of time (admin preview)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM discount_campaigns WHERE active=1 ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def cancel_campaign(self) -> bool:
        with self._conn() as conn:
            cur = conn.execute("UPDATE discount_campaigns SET active=0 WHERE active=1")
            return cur.rowcount > 0

    def get_campaign_history(self):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM discount_campaigns ORDER BY id DESC LIMIT 20"
            ).fetchall()
            return [dict(r) for r in rows]

    # -- Payments --------------------------------------------------------------

    def record_payment(self, user_id: int, stars_paid: int, campaign_id=None):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO payments (user_id, stars_paid, campaign_id, created) VALUES (?,?,?,?)",
                (user_id, stars_paid, campaign_id, datetime.now().isoformat()),
            )

    def get_stats(self) -> dict:
        with self._conn() as conn:
            total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            pro_users   = conn.execute("SELECT COUNT(*) FROM users WHERE plan='pro'").fetchone()[0]
            total_inv   = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
            total_stars = conn.execute(
                "SELECT COALESCE(SUM(stars_paid),0) FROM payments"
            ).fetchone()[0]
            return {
                "total_users":    total_users,
                "pro_users":      pro_users,
                "free_users":     total_users - pro_users,
                "total_invoices": total_inv,
                "total_stars":    total_stars,
            }
