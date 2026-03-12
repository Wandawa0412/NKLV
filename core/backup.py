"""Auto-backup for the work log database.

Creates daily backups in the writable app data directory, keeping the last 7.
"""
import os
import sqlite3
from datetime import datetime
from core.app_paths import TEMP_DIR


BACKUP_DIR = os.path.join(TEMP_DIR, "backups")
MAX_BACKUPS = 7


def auto_backup(db_path: str) -> str | None:
    """Create a daily backup of the database file.

    Returns the backup path if created, None if already exists today.
    Uses SQLite backup API for safe copy (handles WAL mode correctly).
    """
    if not os.path.exists(db_path):
        return None

    os.makedirs(BACKUP_DIR, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    backup_name = f"worklog_{today}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    # Skip if today's backup already exists
    if os.path.exists(backup_path):
        return None

    # Use SQLite backup API instead of file copy — safe for active databases
    try:
        source = sqlite3.connect(db_path)
        dest = sqlite3.connect(backup_path)
        source.backup(dest)
        dest.close()
        source.close()
    except sqlite3.Error:
        # Fallback: if backup API fails, skip silently
        return None

    # Cleanup old backups (keep latest MAX_BACKUPS)
    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith("worklog_") and f.endswith(".db")],
        reverse=True,
    )
    for old in backups[MAX_BACKUPS:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old))
        except OSError:
            pass

    return backup_path

