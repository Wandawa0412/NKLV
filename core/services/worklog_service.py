"""Work log orchestration and validation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime

from core.database import Database
from core.models import WorkItem, WorkLog


@dataclass(slots=True)
class AutoFillData:
    customers: list[str]
    contents: list[str]
    price_map: dict[str, float]


class WorkLogService:
    def __init__(self, db: Database):
        self.db = db

    def list_logs(
        self,
        search: str = "",
        is_sent: bool | None = None,
        month: str | None = None,
    ) -> list[dict]:
        if search.strip():
            return self.db.search_work_logs(search.strip(), is_sent=is_sent, month=month)
        return self.db.get_filtered_work_logs(is_sent=is_sent, month=month)

    def get_log(self, log_id: int) -> WorkLog | None:
        return self.db.get_work_log(log_id)

    def save_log(
        self,
        *,
        customer_name: str,
        work_date: date,
        items: list[WorkItem],
        is_sent: bool,
        source_path: str,
        log_id: int | None = None,
    ) -> WorkLog:
        customer = customer_name.strip()
        if not customer:
            raise ValueError("Vui lòng nhập tên khách hàng.")

        persisted = WorkLog(
            id=log_id,
            customer_name=customer,
            items=self._sanitize_items(items),
            work_date=work_date,
            created_at=self._resolve_created_at(log_id),
            is_sent=is_sent,
            source_path=source_path,
        )
        saved_id = self.db.save_work_log(persisted)
        saved = self.db.get_work_log(saved_id)
        if saved is None:
            raise RuntimeError("Không thể tải lại phiếu vừa lưu.")
        return saved

    def delete_log(self, log_id: int) -> None:
        self.db.delete_work_log(log_id)

    def close(self) -> None:
        """Close the underlying database connection."""
        self.db.close()

    def duplicate_log(self, log: WorkLog) -> WorkLog:
        return WorkLog(
            customer_name=log.customer_name,
            items=[deepcopy(item) for item in log.items],
            work_date=date.today(),
            created_at=datetime.now(),
            is_sent=log.is_sent,
            source_path=log.source_path,
        )

    def get_autofill_data(self, customer_name: str = "") -> AutoFillData:
        customers = [row["name"] for row in self.db.get_customers()]
        customer = customer_name.strip()
        ranked_rows = self.db.get_ranked_work_contents(
            customer if customer in set(customers) else ""
        )
        price_map = {
            row["content"]: row["unit_price"]
            for row in ranked_rows
        }
        return AutoFillData(
            customers=customers,
            contents=[row["content"] for row in ranked_rows],
            price_map=price_map,
        )

    def get_unsent_logs(self) -> list[WorkLog]:
        log_rows = self.db.get_filtered_work_logs(is_sent=False)
        log_ids = [row["id"] for row in log_rows]
        return self.db.get_work_logs_batch(log_ids)

    def _resolve_created_at(self, log_id: int | None) -> datetime:
        if not log_id:
            return datetime.now()
        return self.db.get_log_created_at(log_id) or datetime.now()

    @staticmethod
    def _sanitize_items(items: list[WorkItem]) -> list[WorkItem]:
        sanitized: list[WorkItem] = []
        for item in items:
            if not item.content.strip():
                continue
            sanitized.append(
                WorkItem(
                    date=item.date.strip(),
                    content=item.content.strip(),
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    nvkt=item.nvkt.strip(),
                    id=item.id,
                )
            )
        return sanitized
