"""Application entry point."""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from core.app_metadata import APP_DISPLAY_NAME
from core.app_paths import DB_PATH
from core.backup import auto_backup
from ui.main_window import MainWindow
from ui.theme import apply_theme


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setOrganizationName("ECOS")

    auto_backup(DB_PATH)

    apply_theme(app)
    app.setFont(QFont("Segoe UI", 13))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
