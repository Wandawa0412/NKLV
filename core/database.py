"""SQLite database for persisting work logs, customers, and work content history."""
import sqlite3
import os
from datetime import datetime
from core.models import WorkItem, WorkLog
from core.app_paths import DB_PATH
from core.date_utils import format_storage_date, parse_date


class Database:
    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS work_contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL UNIQUE,
                unit_price REAL DEFAULT 0,
                usage_count INTEGER DEFAULT 1,
                last_used TEXT
            );

            CREATE TABLE IF NOT EXISTS work_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                nvkt TEXT DEFAULT '',
                work_date TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                is_sent INTEGER DEFAULT 0,
                source_path TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS work_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_id INTEGER NOT NULL,
                date TEXT DEFAULT '',
                content TEXT DEFAULT '',
                quantity INTEGER DEFAULT 1,
                unit_price REAL DEFAULT 0,
                FOREIGN KEY (log_id) REFERENCES work_logs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS export_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_id INTEGER,
                export_path TEXT NOT NULL,
                exported_at TEXT NOT NULL,
                FOREIGN KEY (log_id) REFERENCES work_logs(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS log_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER DEFAULT NULL,
                color TEXT DEFAULT '#6c63ff',
                icon TEXT DEFAULT '📁',
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (parent_id) REFERENCES log_groups(id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()
        self._migrate_add_is_sent()
        self._migrate_add_group_id()
        self._migrate_add_work_date()
        self._migrate_add_nvkt()
        self._ensure_indexes()
        self._ensure_work_contents_unique()

    def _ensure_indexes(self):
        """Create performance indexes for large databases."""
        self.conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_work_items_log_id
                ON work_items(log_id);
            CREATE INDEX IF NOT EXISTS idx_work_items_content
                ON work_items(content);
            CREATE INDEX IF NOT EXISTS idx_work_logs_is_sent
                ON work_logs(is_sent);
            CREATE INDEX IF NOT EXISTS idx_work_logs_created_at
                ON work_logs(created_at);
            CREATE INDEX IF NOT EXISTS idx_work_logs_work_date
                ON work_logs(work_date);
            CREATE INDEX IF NOT EXISTS idx_work_logs_customer_name
                ON work_logs(customer_name);
            CREATE INDEX IF NOT EXISTS idx_export_history_log_id_exported_at
                ON export_history(log_id, exported_at DESC);
        """)
        self.conn.commit()

    def _migrate_add_is_sent(self):
        """Add is_sent and source_path columns if they don't exist."""
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT is_sent FROM work_logs LIMIT 1")
        except sqlite3.OperationalError:
            cur.execute("ALTER TABLE work_logs ADD COLUMN is_sent INTEGER DEFAULT 0")
            self.conn.commit()
        try:
            cur.execute("SELECT source_path FROM work_logs LIMIT 1")
        except sqlite3.OperationalError:
            cur.execute("ALTER TABLE work_logs ADD COLUMN source_path TEXT DEFAULT ''")
            self.conn.commit()

    def _migrate_add_group_id(self):
        """Add group_id column to work_logs if it doesn't exist."""
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT group_id FROM work_logs LIMIT 1")
        except sqlite3.OperationalError:
            cur.execute(
                "ALTER TABLE work_logs ADD COLUMN group_id INTEGER DEFAULT NULL "
                "REFERENCES log_groups(id) ON DELETE SET NULL"
            )
            self.conn.commit()

    def _migrate_add_work_date(self):
        """Add work_date column and backfill from item dates or created_at."""
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT work_date FROM work_logs LIMIT 1")
        except sqlite3.OperationalError:
            cur.execute("ALTER TABLE work_logs ADD COLUMN work_date TEXT DEFAULT ''")
            self.conn.commit()

        cur.execute(
            "SELECT id, created_at FROM work_logs WHERE work_date IS NULL OR TRIM(work_date)=''"
        )
        rows = cur.fetchall()
        for row in rows:
            derived = self._derive_work_date_for_log(row["id"], row["created_at"])
            cur.execute(
                "UPDATE work_logs SET work_date=? WHERE id=?",
                (derived, row["id"]),
            )
        if rows:
            self.conn.commit()

    def _migrate_add_nvkt(self):
        """Add nvkt column to work_logs (legacy) and work_items."""
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT nvkt FROM work_logs LIMIT 1")
        except sqlite3.OperationalError:
            cur.execute("ALTER TABLE work_logs ADD COLUMN nvkt TEXT DEFAULT ''")
            self.conn.commit()
        # --- v2.2: nvkt moves to work_items ---
        try:
            cur.execute("SELECT nvkt FROM work_items LIMIT 1")
        except sqlite3.OperationalError:
            cur.execute("ALTER TABLE work_items ADD COLUMN nvkt TEXT DEFAULT ''")
            self.conn.commit()

    # --- Log Group CRUD ---
    def create_group(self, name: str, parent_id: int | None = None,
                     color: str = '#6c63ff', icon: str = '📁') -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO log_groups (name, parent_id, color, icon) VALUES (?, ?, ?, ?)",
            (name, parent_id, color, icon),
        )
        self.conn.commit()
        gid = cur.lastrowid
        if gid is None:
            raise RuntimeError("Failed to create group")
        return gid

    def update_group(self, group_id: int, name: str | None = None,
                     color: str | None = None, icon: str | None = None) -> None:
        updates = []
        params: list[str | int] = []
        if name is not None:
            updates.append("name=?")
            params.append(name)
        if color is not None:
            updates.append("color=?")
            params.append(color)
        if icon is not None:
            updates.append("icon=?")
            params.append(icon)
        if not updates:
            return
        params.append(group_id)
        self.conn.execute(
            f"UPDATE log_groups SET {', '.join(updates)} WHERE id=?", params
        )
        self.conn.commit()

    def delete_group(self, group_id: int) -> None:
        """Delete group. CASCADE removes child groups; logs get group_id=NULL."""
        self.conn.execute("DELETE FROM log_groups WHERE id=?", (group_id,))
        self.conn.commit()

    def move_group(self, group_id: int, new_parent_id: int | None) -> bool:
        # Prevent circular reference: new_parent must not be a descendant
        if new_parent_id is not None:
            if new_parent_id == group_id:
                return False  # Cannot parent to self
            # Walk ancestors of new_parent_id to ensure group_id is not among them
            cur = self.conn.cursor()
            check_id: int | None = new_parent_id
            while check_id is not None:
                cur.execute("SELECT parent_id FROM log_groups WHERE id=?", (check_id,))
                row = cur.fetchone()
                if not row:
                    break
                check_id = row["parent_id"]
                if check_id == group_id:
                    return False  # Circular reference detected — abort
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE log_groups SET parent_id=? WHERE id=?",
            (new_parent_id, group_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_all_groups(self) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM log_groups ORDER BY sort_order, name")
        return [dict(row) for row in cur.fetchall()]

    def move_log_to_group(self, log_id: int, group_id: int | None) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE work_logs SET group_id=? WHERE id=?",
            (group_id, log_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_log_group_id(self, log_id: int) -> int | None:
        cur = self.conn.cursor()
        cur.execute("SELECT group_id FROM work_logs WHERE id=?", (log_id,))
        row = cur.fetchone()
        return row["group_id"] if row else None

    def _derive_work_date_for_log(self, log_id: int, created_at_text: str) -> str:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT date FROM work_items WHERE log_id=? ORDER BY id",
            (log_id,),
        )
        item_dates = [
            parsed
            for row in cur.fetchall()
            if (parsed := parse_date(row["date"])) is not None
        ]
        if item_dates:
            return format_storage_date(min(item_dates))

        created_at = datetime.fromisoformat(created_at_text)
        return format_storage_date(created_at.date())

    # --- Customer CRUD ---
    def get_customers(self, search: str = "") -> list[dict]:
        cur = self.conn.cursor()
        if search:
            cur.execute(
                "SELECT * FROM customers WHERE name LIKE ? ORDER BY name LIMIT 20",
                (f"%{search}%",),
            )
        else:
            cur.execute("SELECT * FROM customers ORDER BY name")
        return [dict(row) for row in cur.fetchall()]

    def upsert_customer(self, name: str) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO customers (name) VALUES (?) "
            "ON CONFLICT(name) DO NOTHING",
            (name,),
        )
        self.conn.commit()
        cur.execute("SELECT id FROM customers WHERE name=?", (name,))
        row = cur.fetchone()
        return row["id"] if row else 0

    # --- Work Content History ---
    def get_work_contents(self, search: str = "") -> list[dict]:
        cur = self.conn.cursor()
        if search:
            cur.execute(
                "SELECT * FROM work_contents WHERE content LIKE ? "
                "ORDER BY usage_count DESC LIMIT 20",
                (f"%{search}%",),
            )
        else:
            cur.execute(
                "SELECT * FROM work_contents ORDER BY usage_count DESC LIMIT 50"
            )
        return [dict(row) for row in cur.fetchall()]

    def get_ranked_work_contents(self, customer_name: str = "") -> list[dict]:
        """Get ranked work contents with optional customer-first ordering."""
        customer = customer_name.strip()
        ranked_rows: list[dict] = []
        seen_contents: set[str] = set()

        if customer:
            for row in self._get_customer_ranked_work_contents(customer):
                content = str(row["content"]).strip()
                if not content or content in seen_contents:
                    continue
                seen_contents.add(content)
                ranked_rows.append(dict(row))

        for row in self._get_global_ranked_work_contents():
            content = str(row["content"]).strip()
            if not content or content in seen_contents:
                continue
            seen_contents.add(content)
            ranked_rows.append(dict(row))

        return ranked_rows

    def upsert_work_content(self, content: str, unit_price: float,
                            _commit: bool = True) -> None:
        cur = self.conn.cursor()
        now = datetime.now().isoformat()
        # Check if content exists
        cur.execute("SELECT id, usage_count FROM work_contents WHERE content=?", (content,))
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE work_contents SET unit_price=?, usage_count=?, last_used=? WHERE id=?",
                (unit_price, row["usage_count"] + 1, now, row["id"]),
            )
        else:
            cur.execute(
                "INSERT INTO work_contents (content, unit_price, usage_count, last_used) "
                "VALUES (?, ?, 1, ?)",
                (content, unit_price, now),
            )
        if _commit:
            self.conn.commit()

    def get_unit_price_for_content(self, content: str) -> float | None:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT unit_price FROM work_contents WHERE content=?", (content,)
        )
        row = cur.fetchone()
        return row["unit_price"] if row else None

    # --- Work Content uniqueness fix ---
    def _ensure_work_contents_unique(self):
        cur = self.conn.cursor()
        try:
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_work_contents_content "
                "ON work_contents(content)"
            )
            self.conn.commit()
        except sqlite3.OperationalError:
            # Duplicates exist — deduplicate keeping highest usage_count per content
            cur.execute(
                "DELETE FROM work_contents WHERE id NOT IN ("
                "  SELECT id FROM ("
                "    SELECT id, ROW_NUMBER() OVER ("
                "      PARTITION BY content ORDER BY usage_count DESC, id ASC"
                "    ) as rn FROM work_contents"
                "  ) WHERE rn = 1"
                ")"
            )
            self.conn.commit()
            try:
                cur.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_work_contents_content "
                    "ON work_contents(content)"
                )
                self.conn.commit()
            except sqlite3.OperationalError:
                pass  # Still fails — leave as-is to avoid data loss

    # --- Work Log CRUD ---
    def save_work_log(self, log: WorkLog) -> int:
        cur = self.conn.cursor()
        now = log.created_at.isoformat()
        work_date = format_storage_date(log.work_date)

        try:
            # Upsert customer (defer commit)
            cur.execute(
                "INSERT INTO customers (name) VALUES (?) "
                "ON CONFLICT(name) DO NOTHING",
                (log.customer_name,),
            )

            is_sent_int = 1 if log.is_sent else 0
            if log.id:
                # Preserve created_at on update; group_id remains untouched by the UPDATE.
                cur.execute("SELECT created_at FROM work_logs WHERE id=?", (log.id,))
                existing = cur.fetchone()
                created_at_val = existing["created_at"] if existing else now
                cur.execute(
                    "UPDATE work_logs SET customer_name=?, work_date=?, "
                    "created_at=?, is_sent=?, source_path=? WHERE id=?",
                    (
                        log.customer_name,
                        work_date,
                        created_at_val,
                        is_sent_int,
                        log.source_path,
                        log.id,
                    ),
                )
                cur.execute("DELETE FROM work_items WHERE log_id=?", (log.id,))
                log_id = log.id
            else:
                cur.execute(
                    "INSERT INTO work_logs (customer_name, work_date, created_at, is_sent, source_path) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (log.customer_name, work_date, now, is_sent_int, log.source_path),
                )
                log_id = cur.lastrowid
                if log_id is None:
                    raise RuntimeError("Failed to insert work log")

            for item in log.items:
                cur.execute(
                    "INSERT INTO work_items (log_id, date, content, quantity, unit_price, nvkt) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (log_id, item.date, item.content, item.quantity, item.unit_price, item.nvkt),
                )
                # Update work content history for auto-fill (no intermediate commit)
                if item.content.strip():
                    self.upsert_work_content(item.content, item.unit_price, _commit=False)

            self.conn.commit()
            return log_id
        except Exception:
            self.conn.rollback()
            raise

    def get_work_log(self, log_id: int) -> WorkLog | None:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM work_logs WHERE id=?", (log_id,))
        row = cur.fetchone()
        if not row:
            return None

        log = WorkLog(
            id=row["id"],
            customer_name=row["customer_name"],
            work_date=parse_date(row["work_date"]) or datetime.fromisoformat(row["created_at"]).date(),
            created_at=datetime.fromisoformat(row["created_at"]),
            is_sent=bool(row["is_sent"]) if "is_sent" in row.keys() else False,
            source_path=row["source_path"] if "source_path" in row.keys() else "",
        )

        cur.execute(
            "SELECT * FROM work_items WHERE log_id=? ORDER BY id", (log_id,)
        )
        for item_row in cur.fetchall():
            log.items.append(
                WorkItem(
                    id=item_row["id"],
                    date=item_row["date"],
                    content=item_row["content"],
                    quantity=item_row["quantity"],
                    unit_price=item_row["unit_price"],
                    nvkt=item_row["nvkt"] if "nvkt" in item_row.keys() else "",
                )
            )
        return log

    def get_all_work_logs(self) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT wl.id, wl.customer_name, wl.nvkt, wl.work_date, wl.created_at, wl.is_sent, wl.source_path, "
            "wl.group_id, "
            "COUNT(wi.id) as item_count, "
            "COALESCE(SUM(wi.quantity * wi.unit_price), 0) as total "
            "FROM work_logs wl "
            "LEFT JOIN work_items wi ON wi.log_id = wl.id "
            "GROUP BY wl.id "
            "ORDER BY wl.work_date DESC, wl.created_at DESC"
        )
        return [dict(row) for row in cur.fetchall()]

    def delete_work_log(self, log_id: int) -> None:
        cur = self.conn.cursor()
        # CASCADE handles work_items deletion via PRAGMA foreign_keys = ON
        cur.execute("DELETE FROM work_logs WHERE id=?", (log_id,))
        self.conn.commit()

    def get_work_logs_batch(self, log_ids: list[int]) -> list[WorkLog]:
        """Load multiple WorkLogs in 2 queries instead of N+1.

        Production-safe for large batches (100+ logs).
        """
        if not log_ids:
            return []

        cur = self.conn.cursor()
        placeholders = ",".join("?" * len(log_ids))

        # Query 1: all log rows
        cur.execute(
            f"SELECT * FROM work_logs WHERE id IN ({placeholders})",
            log_ids,
        )
        log_rows = cur.fetchall()

        # Query 2: all items for all logs
        cur.execute(
            f"SELECT * FROM work_items WHERE log_id IN ({placeholders}) ORDER BY id",
            log_ids,
        )
        item_rows = cur.fetchall()

        # Group items by log_id
        items_by_log: dict[int, list[WorkItem]] = {}
        for item_row in item_rows:
            lid = item_row["log_id"]
            if lid not in items_by_log:
                items_by_log[lid] = []
            items_by_log[lid].append(
                WorkItem(
                    id=item_row["id"],
                    date=item_row["date"],
                    content=item_row["content"],
                    quantity=item_row["quantity"],
                    unit_price=item_row["unit_price"],
                    nvkt=item_row["nvkt"] if "nvkt" in item_row.keys() else "",
                )
            )

        # Build WorkLog objects
        logs = []
        for row in log_rows:
            log = WorkLog(
                id=row["id"],
                customer_name=row["customer_name"],
                work_date=parse_date(row["work_date"]) or datetime.fromisoformat(row["created_at"]).date(),
                created_at=datetime.fromisoformat(row["created_at"]),
                is_sent=bool(row["is_sent"]) if "is_sent" in row.keys() else False,
                source_path=row["source_path"] if "source_path" in row.keys() else "",
            )
            log.items = items_by_log.get(row["id"], [])
            logs.append(log)

        return logs

    def search_work_logs(self, query: str, is_sent: bool | None = None,
                         month: str | None = None) -> list[dict]:
        cur = self.conn.cursor()
        # Search both customer_name AND work_items.content (M01)
        conditions = [
            "(wl.customer_name LIKE ? OR wl.id IN "
            "(SELECT log_id FROM work_items WHERE content LIKE ? OR nvkt LIKE ?))"
        ]
        params: list[str | int] = [f"%{query}%", f"%{query}%", f"%{query}%"]

        if is_sent is not None:
            conditions.append("wl.is_sent = ?")
            params.append(1 if is_sent else 0)
        if month:
            conditions.append("wl.work_date LIKE ?")
            params.append(f"{month}%")

        where = f"WHERE {' AND '.join(conditions)}"
        cur.execute(
            f"SELECT wl.id, wl.customer_name, wl.nvkt, wl.work_date, wl.created_at, wl.is_sent, wl.source_path, "
            f"wl.group_id, "
            f"COUNT(wi.id) as item_count, "
            f"COALESCE(SUM(wi.quantity * wi.unit_price), 0) as total "
            f"FROM work_logs wl "
            f"LEFT JOIN work_items wi ON wi.log_id = wl.id "
            f"{where} "
            f"GROUP BY wl.id "
            f"ORDER BY wl.work_date DESC, wl.created_at DESC",
            params,
        )
        return [dict(row) for row in cur.fetchall()]

    def close(self):
        self.conn.close()

    # --- Content + Price batch query (avoids N+1) ---
    def get_content_price_map(self) -> dict[str, float]:
        """Get all content names with their prices in a single query."""
        return {
            row["content"]: row["unit_price"]
            for row in self._get_global_ranked_work_contents()
        }

    def _get_global_ranked_work_contents(self) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT
                content,
                unit_price,
                usage_count,
                COALESCE(last_used, '') AS last_used
            FROM work_contents
            WHERE TRIM(content) <> ''
            ORDER BY usage_count DESC, COALESCE(last_used, '') DESC, content ASC
            """
        )
        return [dict(row) for row in cur.fetchall()]

    def _get_customer_ranked_work_contents(self, customer_name: str) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute(
            """
            WITH customer_usage AS (
                SELECT
                    wi.content AS content,
                    COUNT(*) AS usage_count,
                    MAX(
                        CASE
                            WHEN TRIM(wl.work_date) <> '' THEN wl.work_date
                            ELSE substr(wl.created_at, 1, 10)
                        END
                    ) AS last_used
                FROM work_items wi
                JOIN work_logs wl ON wl.id = wi.log_id
                WHERE wl.customer_name = ? AND TRIM(wi.content) <> ''
                GROUP BY wi.content
            ),
            customer_recent_price AS (
                SELECT content, unit_price
                FROM (
                    SELECT
                        wi.content AS content,
                        wi.unit_price AS unit_price,
                        ROW_NUMBER() OVER (
                            PARTITION BY wi.content
                            ORDER BY
                                CASE
                                    WHEN TRIM(wl.work_date) <> '' THEN wl.work_date
                                    ELSE substr(wl.created_at, 1, 10)
                                END DESC,
                                wl.created_at DESC,
                                wi.id DESC
                        ) AS rank_no
                    FROM work_items wi
                    JOIN work_logs wl ON wl.id = wi.log_id
                    WHERE wl.customer_name = ? AND TRIM(wi.content) <> ''
                ) ranked
                WHERE rank_no = 1
            )
            SELECT
                customer_usage.content,
                customer_recent_price.unit_price,
                customer_usage.usage_count,
                customer_usage.last_used
            FROM customer_usage
            JOIN customer_recent_price
                ON customer_recent_price.content = customer_usage.content
            ORDER BY
                customer_usage.usage_count DESC,
                customer_usage.last_used DESC,
                customer_usage.content ASC
            """,
            (customer_name, customer_name),
        )
        return [dict(row) for row in cur.fetchall()]

    def get_log_created_at(self, log_id: int) -> datetime | None:
        """Get only the created_at timestamp without loading items (M03)."""
        cur = self.conn.cursor()
        cur.execute("SELECT created_at FROM work_logs WHERE id=?", (log_id,))
        row = cur.fetchone()
        return datetime.fromisoformat(row["created_at"]) if row else None

    def get_last_export_dir(self, log_id: int | None) -> str | None:
        """Return the directory of the most recent export for a log."""
        if not log_id:
            return None

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT export_path
            FROM export_history
            WHERE log_id=?
            ORDER BY exported_at DESC, id DESC
            LIMIT 1
            """,
            (log_id,),
        )
        row = cur.fetchone()
        if not row:
            return None

        export_path = (row["export_path"] or "").strip()
        if not export_path:
            return None

        return os.path.dirname(os.path.abspath(export_path))

    # --- Export History ---
    def log_export(self, log_id: int | None, export_path: str) -> None:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO export_history (log_id, export_path, exported_at) VALUES (?, ?, ?)",
            (log_id, export_path, datetime.now().isoformat()),
        )
        self.conn.commit()

    # --- Filtered Work Logs ---
    def get_filtered_work_logs(
        self, is_sent: bool | None = None, month: str | None = None
    ) -> list[dict]:
        """Get work logs with optional filters.
        month format: 'YYYY-MM'
        """
        cur = self.conn.cursor()
        conditions = []
        params: list[str | int] = []

        if is_sent is not None:
            conditions.append("wl.is_sent = ?")
            params.append(1 if is_sent else 0)
        if month:
            conditions.append("wl.work_date LIKE ?")
            params.append(f"{month}%")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cur.execute(
            f"SELECT wl.id, wl.customer_name, wl.nvkt, wl.work_date, wl.created_at, wl.is_sent, wl.source_path, "
            f"wl.group_id, "
            f"COUNT(wi.id) as item_count, "
            f"COALESCE(SUM(wi.quantity * wi.unit_price), 0) as total "
            f"FROM work_logs wl "
            f"LEFT JOIN work_items wi ON wi.log_id = wl.id "
            f"{where} "
            f"GROUP BY wl.id "
            f"ORDER BY wl.work_date DESC, wl.created_at DESC",
            params,
        )
        return [dict(row) for row in cur.fetchall()]

    # --- App Configuration ---
    def get_config(self, key: str, default: str = "") -> str:
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM app_config WHERE key=?", (key,))
        row = cur.fetchone()
        return row["value"] if row else default

    def set_config(self, key: str, value: str) -> None:
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO app_config (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()
