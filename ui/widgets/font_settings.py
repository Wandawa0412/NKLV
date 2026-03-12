"""Font settings dialog for customizing table display font."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QPushButton, QColorDialog, QGroupBox, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor


DEFAULT_FONT_FAMILY = "Segoe UI"
DEFAULT_FONT_SIZE = 14
DEFAULT_FONT_COLOR = "#f0f0ff"


class FontSettingsDialog(QDialog):
    """Dialog for configuring table font family, size, and color."""

    def __init__(self, current_settings: dict | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("fontSettingsDialog")
        self.setWindowTitle("Cài đặt font bảng")
        self.setMinimumWidth(400)
        self.setModal(True)

        self._color = current_settings.get("color", DEFAULT_FONT_COLOR) if current_settings else DEFAULT_FONT_COLOR

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Font family
        group = QGroupBox("Font hiển thị bảng công việc")
        group_layout = QVBoxLayout(group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Font:"))
        self.font_combo = QComboBox()
        self.font_combo.setEditable(False)
        families = [
            "Segoe UI", "Inter", "Roboto", "Consolas", "Cascadia Code",
            "Arial", "Tahoma", "Verdana", "Courier New", "Times New Roman",
        ]
        self.font_combo.addItems(families)
        if current_settings and current_settings.get("family") in families:
            self.font_combo.setCurrentText(current_settings["family"])
        row1.addWidget(self.font_combo, 1)
        group_layout.addLayout(row1)

        # Font size
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Cỡ chữ:"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(10, 24)
        self.size_spin.setValue(current_settings.get("size", DEFAULT_FONT_SIZE) if current_settings else DEFAULT_FONT_SIZE)
        self.size_spin.setSuffix(" px")
        row2.addWidget(self.size_spin)
        row2.addStretch()
        group_layout.addLayout(row2)

        # Font color
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Màu chữ:"))
        self.color_btn = QPushButton()
        self._update_color_btn()
        self.color_btn.clicked.connect(self._pick_color)
        row3.addWidget(self.color_btn)
        row3.addStretch()
        group_layout.addLayout(row3)

        layout.addWidget(group)

        # Preview — simulates actual table appearance (H07)
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)
        self.preview_line1 = QLabel("  10/03/2026  Vệ sinh máy photocopy          1        450,000      450,000")
        self.preview_line1.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.preview_line1.setMinimumHeight(32)
        self.preview_line2 = QLabel("  10/03/2026  Thay mực in HP 05A              2        350,000      700,000")
        self.preview_line2.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.preview_line2.setMinimumHeight(32)
        preview_layout.addWidget(self.preview_line1)
        preview_layout.addWidget(self.preview_line2)
        self._update_preview()
        layout.addWidget(preview_container)

        # Connect live preview
        self.font_combo.currentTextChanged.connect(lambda: self._update_preview())
        self.size_spin.valueChanged.connect(lambda: self._update_preview())

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_reset = QPushButton("Mặc định")
        btn_reset.clicked.connect(self._reset_defaults)
        btn_row.addWidget(btn_reset)

        btn_ok = QPushButton("Áp dụng")
        btn_ok.clicked.connect(self._apply)
        btn_row.addWidget(btn_ok)

        btn_cancel = QPushButton("Hủy")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        layout.addLayout(btn_row)

    def showEvent(self, event):
        """Center dialog on parent window (L08)."""
        super().showEvent(event)
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.center().x() - self.width() // 2
            y = parent_geo.center().y() - self.height() // 2
            self.move(x, y)

    def _update_color_btn(self):
        text_color = "#06101e" if QColor(self._color).lightnessF() > 0.72 else "#f8fbff"
        self.color_btn.setText(f"  {self._color}  ")
        self.color_btn.setStyleSheet(
            f"background-color: {self._color}; color: {text_color}; "
            "border: 1px solid rgba(214, 229, 255, 0.18); border-radius: 10px; "
            "padding: 6px 12px; font-weight: 700;"
        )

    def _pick_color(self):
        dialog = QColorDialog(QColor(self._color), self)
        dialog.setWindowTitle("Chọn màu chữ")
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        if dialog.exec():
            self._color = dialog.currentColor().name()
            self._update_color_btn()
            self._update_preview()

    def _update_preview(self):
        family = self.font_combo.currentText()
        size = self.size_spin.value()
        base_style = (
            f"font-family: '{family}'; font-size: {size}px; "
            f"color: {self._color}; "
            f"padding: 6px 10px;"
        )
        self.preview_line1.setStyleSheet(
            base_style +
            "background-color: rgba(10, 18, 33, 0.84); "
            "border: 1px solid rgba(214,229,255,0.08);"
        )
        self.preview_line2.setStyleSheet(
            base_style +
            "background-color: rgba(17, 28, 49, 0.78); "
            "border: 1px solid rgba(214,229,255,0.04); border-top: none;"
        )

    def _reset_defaults(self):
        self.font_combo.setCurrentText(DEFAULT_FONT_FAMILY)
        self.size_spin.setValue(DEFAULT_FONT_SIZE)
        self._color = DEFAULT_FONT_COLOR
        self._update_color_btn()
        self._update_preview()

    def _apply(self):
        self.accept()

    def get_settings(self) -> dict:
        return {
            "family": self.font_combo.currentText(),
            "size": self.size_spin.value(),
            "color": self._color,
        }
