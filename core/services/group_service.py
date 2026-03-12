"""Group and tree operations."""
from __future__ import annotations

from core.database import Database


class GroupService:
    def __init__(self, db: Database):
        self.db = db

    def get_all_groups(self) -> list[dict]:
        return self.db.get_all_groups()

    def create_group(
        self,
        name: str,
        parent_id: int | None = None,
        color: str = "#6c63ff",
        icon: str = "📁",
    ) -> int:
        return self.db.create_group(name=name, parent_id=parent_id, color=color, icon=icon)

    def rename_group(self, group_id: int, name: str) -> None:
        self.db.update_group(group_id, name=name)

    def set_group_color(self, group_id: int, color: str) -> None:
        self.db.update_group(group_id, color=color)

    def set_group_icon(self, group_id: int, icon: str) -> None:
        self.db.update_group(group_id, icon=icon)

    def delete_group(self, group_id: int) -> None:
        self.db.delete_group(group_id)

    def move_group(self, group_id: int, new_parent_id: int | None) -> bool:
        return self.db.move_group(group_id, new_parent_id)

    def move_log(self, log_id: int, group_id: int | None) -> bool:
        return self.db.move_log_to_group(log_id, group_id)
