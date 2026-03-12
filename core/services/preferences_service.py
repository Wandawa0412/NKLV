"""User preferences and lightweight app settings."""
from __future__ import annotations

import json

from core.database import Database


class PreferencesService:
    def __init__(self, db: Database):
        self.db = db

    def get_working_directory(self) -> str:
        return self.db.get_config("working_directory", "")

    def set_working_directory(self, path: str) -> None:
        self.db.set_config("working_directory", path)

    def get_table_font_settings(self) -> dict | None:
        raw = self.db.get_config("table_font_settings", "")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_table_font_settings(self, settings: dict) -> None:
        self.db.set_config("table_font_settings", json.dumps(settings))
