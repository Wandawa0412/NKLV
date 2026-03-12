"""Import/export workflows around Excel files."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from core.app_paths import OUTPUT_DIR
from core.database import Database
from core.excel_engine import ExcelEngine
from core.models import WorkLog
from core.date_utils import format_storage_date


@dataclass(slots=True)
class ImportBatchResult:
    imported_ids: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def imported_count(self) -> int:
        return len(self.imported_ids)


class ImportExportService:
    def __init__(self, db: Database, excel: ExcelEngine):
        self.db = db
        self.excel = excel

    def default_filename(self, log: WorkLog) -> str:
        safe_name = (
            log.customer_name.replace("/", "-").replace("\\", "-").replace(":", "-").strip()
        ) or "khong_ro"
        return f"NKLV_{safe_name}_{format_storage_date(log.work_date).replace('-', '')}.xlsx"

    def _fallback_output_dir(self) -> str:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        return OUTPUT_DIR

    @staticmethod
    def _existing_dir(path: str | None) -> str | None:
        if not path:
            return None

        normalized = os.path.abspath(path)
        if os.path.isdir(normalized):
            return normalized
        return None

    def resolve_export_dir(self, log: WorkLog) -> str:
        last_export_dir = self.db.get_last_export_dir(log.id)
        for candidate in (last_export_dir, log.source_path):
            resolved = self._existing_dir(candidate)
            if resolved:
                return resolved
        return self._fallback_output_dir()

    def resolve_batch_export_dir(
        self, logs: list[WorkLog], current_log_id: int | None = None
    ) -> str:
        if not logs:
            return self._fallback_output_dir()

        resolved_dirs = {
            log.id: self.resolve_export_dir(log)
            for log in logs
        }
        unique_dirs = {path for path in resolved_dirs.values() if path}
        if len(unique_dirs) == 1:
            return next(iter(unique_dirs))

        if current_log_id in resolved_dirs:
            return resolved_dirs[current_log_id]

        return self._fallback_output_dir()

    def export_log(self, log: WorkLog, output_path: str) -> str:
        path = self.excel.export_single(log, output_path=output_path)
        self.db.log_export(log.id, path)
        return path

    def export_logs(self, logs: list[WorkLog], output_dir: str) -> list[str]:
        paths = self.excel.export_batch(logs, output_dir=output_dir)
        for log, path in zip(logs, paths):
            self.db.log_export(log.id, path)
        return paths

    def export_logs_multi_sheet(self, logs: list[WorkLog], output_path: str) -> str:
        path = self.excel.export_multi_sheet(logs, output_path=output_path)
        for log in logs:
            self.db.log_export(log.id, path)
        return path

    def import_files(self, files: list[str]) -> ImportBatchResult:
        result = ImportBatchResult()
        for file_path in files:
            try:
                log = self.excel.import_from_excel(file_path)
                if not log.customer_name:
                    result.errors.append(
                        f"{os.path.basename(file_path)}: Không tìm thấy tên khách hàng"
                    )
                    continue
                if not log.items:
                    result.errors.append(
                        f"{os.path.basename(file_path)}: Không có dữ liệu công việc"
                    )
                    continue
                log.source_path = os.path.dirname(os.path.abspath(file_path))
                saved_id = self.db.save_work_log(log)
                result.imported_ids.append(saved_id)
            except (ValueError, KeyError, OSError, IndexError) as exc:
                result.errors.append(f"{os.path.basename(file_path)}: {exc}")
        return result
