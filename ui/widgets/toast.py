"""Animated toast notification widget for success/error/info feedback."""
from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect, QWidget
from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import QFont


class Toast(QLabel):
    """Slide-in toast notification with auto-dismiss."""

    STYLES = {
        "success": {
            "bg": "rgba(22, 101, 52, 0.9)",
            "border": "rgba(52, 211, 153, 0.4)",
            "icon": "✅",
        },
        "error": {
            "bg": "rgba(127, 29, 29, 0.9)",
            "border": "rgba(248, 113, 113, 0.4)",
            "icon": "❌",
        },
        "info": {
            "bg": "rgba(30, 58, 138, 0.9)",
            "border": "rgba(96, 165, 250, 0.4)",
            "icon": "ℹ️",
        },
        "warning": {
            "bg": "rgba(120, 83, 9, 0.9)",
            "border": "rgba(251, 191, 36, 0.4)",
            "icon": "⚠️",
        },
    }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setFixedHeight(44)
        self.setMinimumWidth(280)
        self.setMaximumWidth(500)

        # M04: Use app default font instead of hardcoded family
        font = self.font()
        font.setPointSize(13)
        font.setWeight(QFont.Weight.DemiBold)
        self.setFont(font)

        # Opacity effect for fade
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self.hide()

        # Timers
        self._show_timer = QTimer(self)
        self._show_timer.setSingleShot(True)
        self._show_timer.timeout.connect(self._start_hide)

    def show_toast(self, message: str, style: str = "success", duration_ms: int = 2500):
        """Display toast with animation."""
        s = self.STYLES.get(style, self.STYLES["info"])
        self.setText(f"  {s['icon']}  {message}")
        self.setStyleSheet(
            f"background-color: {s['bg']}; "
            f"border: 1px solid {s['border']}; "
            f"border-radius: 10px; "
            f"color: #ffffff; "
            f"padding: 8px 16px; "
            f"font-size: 13px; "
        )

        # Position at bottom-center of parent
        p = self.parent()
        if p is not None and isinstance(p, QWidget):
            pw = p.width()
            ph = p.height()
            # Use font metrics for accurate width calculation (handles Vietnamese + emoji)
            fm = self.fontMetrics()
            text_width = fm.horizontalAdvance(f"  {s['icon']}  {message}") + 40  # + padding
            w = min(max(text_width, 280), 500)
            self.setFixedWidth(w)
            x = (pw - w) // 2
            self.move(x, ph - 60)

        self.show()
        self.raise_()

        # Fade in
        self._fade_in = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_in.start()

        self._show_timer.start(duration_ms)

    def _start_hide(self):
        """Fade out and hide."""
        self._fade_out = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_out.setDuration(400)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out.finished.connect(self.hide)
        self._fade_out.start()
