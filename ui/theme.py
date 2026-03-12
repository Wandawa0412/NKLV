"""Centralized application theme bootstrap."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def build_app_palette() -> QPalette:
    palette = QPalette()

    window = QColor("#06101e")
    base = QColor("#091728")
    alt_base = QColor("#0d1d33")
    text = QColor("#ecf3ff")
    muted = QColor("#96abca")
    button = QColor("#11233f")
    highlight = QColor("#5d92f2")
    highlighted_text = QColor("#f8fbff")

    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, alt_base)
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#101c31"))
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, button)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, muted)
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, highlighted_text)
    palette.setColor(QPalette.ColorRole.Light, QColor("#2d4367"))
    palette.setColor(QPalette.ColorRole.Midlight, QColor("#20324f"))
    palette.setColor(QPalette.ColorRole.Dark, QColor("#050c16"))
    palette.setColor(QPalette.ColorRole.Mid, QColor("#16253c"))
    palette.setColor(QPalette.ColorRole.Shadow, QColor("#02060c"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#86b8ff"))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor("#c0d4ff"))

    disabled_text = QColor("#6f82a1")
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_text)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor("#27405f"))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.HighlightedText,
        QColor("#a7b8d1"),
    )

    return palette


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setPalette(build_app_palette())

    style_path = Path(__file__).with_name("styles.qss")
    if style_path.exists():
        app.setStyleSheet(style_path.read_text(encoding="utf-8"))
