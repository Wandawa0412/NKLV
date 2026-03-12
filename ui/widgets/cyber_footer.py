"""Animated hash-decode footer tuned for the glass UI."""

from __future__ import annotations

import random

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QWidget

GLITCH_CHARS = "0123456789abcdef##@%&*+=?/\\[]{}<>:;"


class CyberFooter(QLabel):
    """Animated footer that periodically decodes into the final message."""

    def __init__(
        self,
        text: str = "Copyright Sang@ecos minuszero369@gmail.com",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._target_text = text
        self._current_chars: list[str] = list(text)
        self._locked: list[bool] = [False] * len(text)
        self._reveal_index = 0
        self._phase = "scramble"
        self._scramble_ticks = 0
        self._idle_ticks = 0
        self._glow_direction = 1
        self._glow_value = 80

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setObjectName("cyberFooter")
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setMinimumHeight(24)

        self._base_family = "Cascadia Code"
        self.apply_layout_mode("wide")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(42)

        self._reshuffle_timer = QTimer(self)
        self._reshuffle_timer.timeout.connect(self._start_scramble)
        self._reshuffle_timer.start(18_000)

        self._start_scramble()

    def apply_layout_mode(self, mode: str) -> None:
        if mode == "compact":
            size = 9
            spacing = 1.1
        elif mode == "medium":
            size = 9
            spacing = 1.4
        else:
            size = 10
            spacing = 1.8

        font = QFont(self._base_family, size)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
        self.setFont(font)

    def _start_scramble(self):
        self._phase = "scramble"
        self._locked = [False] * len(self._target_text)
        self._reveal_index = 0
        self._scramble_ticks = 0
        self._current_chars = [
            char if char == " " else random.choice(GLITCH_CHARS)
            for char in self._target_text
        ]
        self._render()

    def _tick(self):
        if self._phase == "scramble":
            self._tick_scramble()
        elif self._phase == "reveal":
            self._tick_reveal()
        elif self._phase == "idle":
            self._tick_idle()

    def _tick_scramble(self):
        self._scramble_ticks += 1
        for index, char in enumerate(self._target_text):
            if char != " " and not self._locked[index]:
                self._current_chars[index] = random.choice(GLITCH_CHARS)
        self._render()
        if self._scramble_ticks >= 16:
            self._phase = "reveal"

    def _tick_reveal(self):
        for _ in range(2):
            if self._reveal_index < len(self._target_text):
                self._locked[self._reveal_index] = True
                self._current_chars[self._reveal_index] = self._target_text[self._reveal_index]
                self._reveal_index += 1

        for index, char in enumerate(self._target_text):
            if char != " " and not self._locked[index]:
                self._current_chars[index] = random.choice(GLITCH_CHARS)

        self._render()
        if self._reveal_index >= len(self._target_text):
            self._phase = "idle"
            self._idle_ticks = 0

    def _tick_idle(self):
        self._idle_ticks += 1
        self._glow_value += self._glow_direction * 2
        if self._glow_value >= 100:
            self._glow_direction = -1
        elif self._glow_value <= 60:
            self._glow_direction = 1
        self._render()

    def _render(self):
        parts: list[str] = []
        for index, char in enumerate(self._current_chars):
            if char == " ":
                parts.append("&nbsp;")
                continue

            if self._locked[index]:
                locked_alpha = min(0.96, 0.58 + (self._glow_value / 100) * 0.34)
                locked_color = "214, 231, 255" if index % 7 else "188, 226, 255"
                parts.append(
                    f'<span style="color: rgba({locked_color}, {locked_alpha:.2f});">{_esc(char)}</span>'
                )
            else:
                glitch_alpha = random.randint(18, 46) / 100
                glitch_color = "144, 191, 255" if index % 3 else "118, 224, 221"
                parts.append(
                    f'<span style="color: rgba({glitch_color}, {glitch_alpha:.2f});">{_esc(char)}</span>'
                )

        html = (
            '<div style="letter-spacing: 1.8px; font-family: '
            "'Cascadia Code', 'Consolas', monospace;\">"
            + "".join(parts)
            + "</div>"
        )
        self.setText(html)


def _esc(char: str) -> str:
    return char.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
