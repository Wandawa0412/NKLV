# NKLV ECOS@2026

[![CI](https://github.com/Wandawa0412/NKLV/actions/workflows/ci.yml/badge.svg)](https://github.com/Wandawa0412/NKLV/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB.svg)](https://www.python.org/)

Ứng dụng desktop Windows quản lý phiếu công việc (nhật ký làm việc), hỗ trợ nhập/xuất Excel và tổ chức phiếu theo cây nhóm lồng nhau.

## Tính năng

- **Quản lý phiếu công việc** — tạo, sửa, xóa phiếu với thông tin khách hàng, nội dung công việc, số lượng, đơn giá.
- **Import/Export Excel** — nhập phiếu từ file Excel, xuất ra file Excel theo template chuẩn. Hỗ trợ xuất đơn lẻ, xuất hàng loạt, và xuất nhiều sheet.
- **Cây nhóm lồng nhau** — tổ chức phiếu theo thư mục, hỗ trợ drag-drop đổi vị trí.
- **Tự gợi ý thông minh** — gợi ý khách hàng, nội dung và đơn giá từ dữ liệu lịch sử.
- **Lọc và tìm kiếm** — lọc theo trạng thái (đã gửi/chưa gửi), theo tháng, tìm kiếm tự do.
- **Auto-backup** — sao lưu database SQLite hàng ngày, giữ 7 bản gần nhất.
- **Giao diện hiện đại** — theme tối với hiệu ứng sóng động, responsive layout.

## Kiến trúc

```
NKLV/
├── main.py                  # Entry point
├── core/
│   ├── app_metadata.py      # Tên, version, publisher
│   ├── app_paths.py         # Đường dẫn runtime (dev / frozen)
│   ├── backup.py            # Auto-backup logic
│   ├── database.py          # SQLite persistence + migrations
│   ├── date_utils.py        # Xử lý ngày tháng
│   ├── excel_engine.py      # Import/export Excel (openpyxl)
│   ├── models.py            # WorkLog, WorkItem dataclasses
│   └── services/
│       ├── group_service.py          # Nghiệp vụ nhóm
│       ├── import_export_service.py  # Orchestration import/export
│       ├── preferences_service.py    # Cài đặt người dùng
│       └── worklog_service.py        # Nghiệp vụ phiếu
├── ui/
│   ├── main_window.py       # Cửa sổ chính (1134 dòng)
│   ├── styles.qss           # QSS stylesheet
│   ├── theme.py             # Theme engine
│   └── widgets/
│       ├── autocomplete_combo.py  # Dropdown gợi ý
│       ├── cyber_footer.py        # Footer hiệu ứng
│       ├── font_settings.py       # Tùy chỉnh font
│       ├── group_tree.py          # Cây nhóm
│       ├── item_table.py          # Bảng công việc
│       ├── toast.py               # Thông báo popup
│       └── wave_background.py     # Nền sóng động
├── icon/                    # Icon ứng dụng
├── installer/               # Inno Setup script
├── scripts/                 # Build pipeline
├── Template excel/          # Template Excel đóng gói
└── requirements.txt
```

## Yêu cầu

- Windows 10+
- Python 3.12+
- PySide6 ≥ 6.6.0
- openpyxl ≥ 3.1.0

## Chạy ứng dụng

```powershell
pip install -r requirements.txt
python main.py
```

## Build release

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_release.ps1
```

Pipeline: `ruff check` → `compileall` → `pytest` → `PyInstaller` → `Inno Setup`

## Thông tin

- **Version**: 2.2.0
- **Publisher**: Sang@ecos
- **Runtime data**: `.temp/worklog.db` (cạnh source hoặc cạnh `.exe`)
