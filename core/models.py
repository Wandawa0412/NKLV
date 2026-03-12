"""Data models for Work Log Manager."""
from dataclasses import dataclass, field
from datetime import date, datetime

from core.date_utils import format_display_date


@dataclass
class WorkItem:
    """Single work item in a work log."""
    date: str = ""
    content: str = ""
    quantity: int = 1
    unit_price: float = 0.0
    nvkt: str = ""
    id: int | None = None

    @property
    def total(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class WorkLog:
    """A complete work log for one customer."""
    customer_name: str = ""
    items: list[WorkItem] = field(default_factory=list)
    work_date: date = field(default_factory=date.today)
    created_at: datetime = field(default_factory=datetime.now)
    is_sent: bool = False
    source_path: str = ""  # directory where the file was imported from
    id: int | None = None

    @property
    def grand_total(self) -> float:
        return sum(item.total for item in self.items)

    @property
    def work_date_display(self) -> str:
        return format_display_date(self.work_date)

    def add_item(self, item: WorkItem) -> None:
        self.items.append(item)

    def remove_item(self, index: int) -> None:
        if 0 <= index < len(self.items):
            self.items.pop(index)
