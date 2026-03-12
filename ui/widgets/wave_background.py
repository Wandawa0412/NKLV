"""Animated wave background widget — multi-layer sine waves with QPainter.

Paints 4 translucent sine wave layers with different frequencies,
amplitudes, speeds, and colors. Runs at 30fps for smooth animation
with minimal CPU overhead (pure QPainter — no images, no OpenGL).

Includes optional rubber duck sprites that float on the wave surface.
"""
import math
import os
import random
import sys
import time
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Qt, QRectF
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QTransform,
)


class WaveConfig:
    """Configuration for a single wave layer."""
    __slots__ = ("amplitude", "frequency", "speed", "phase", "y_offset",
                 "color_top", "color_bot", "thickness")

    def __init__(self, amplitude: float, frequency: float, speed: float,
                 phase: float, y_offset: float,
                 color_top: str, color_bot: str, thickness: float = 0):
        self.amplitude = amplitude
        self.frequency = frequency
        self.speed = speed
        self.phase = phase
        self.y_offset = y_offset  # 0.0 = top, 1.0 = bottom (fraction of height)
        self.color_top = color_top
        self.color_bot = color_bot
        self.thickness = thickness  # 0 = filled to bottom, >0 = stroke only


# Default wave layers — midnight blue palette for glassmorphism UI
DEFAULT_WAVES = [
    # Layer 1: Large slow wave at bottom
    WaveConfig(
        amplitude=35, frequency=0.006, speed=0.4, phase=0,
        y_offset=0.75,
        color_top="rgba(34, 64, 112, 0.14)",
        color_bot="rgba(8, 20, 44, 0.26)",
    ),
    # Layer 2: Mid wave
    WaveConfig(
        amplitude=25, frequency=0.009, speed=0.6, phase=1.2,
        y_offset=0.80,
        color_top="rgba(72, 124, 196, 0.10)",
        color_bot="rgba(24, 48, 92, 0.18)",
    ),
    # Layer 3: Faster ripple
    WaveConfig(
        amplitude=15, frequency=0.014, speed=0.9, phase=2.5,
        y_offset=0.85,
        color_top="rgba(82, 156, 182, 0.08)",
        color_bot="rgba(20, 62, 72, 0.12)",
    ),
    # Layer 4: Subtle fast shimmer near the top
    WaveConfig(
        amplitude=8, frequency=0.020, speed=1.3, phase=4.0,
        y_offset=0.18,
        color_top="rgba(196, 224, 255, 0.10)",
        color_bot="rgba(196, 224, 255, 0.00)",
        thickness=1.5,
    ),
]


class DuckSprite:
    """A rubber duck that floats on the wave surface."""
    __slots__ = ("x", "speed", "size", "wave_idx", "opacity", "bob_phase")

    def __init__(self, x: float, speed: float, size: int,
                 wave_idx: int, opacity: float, bob_phase: float):
        self.x = x            # horizontal position (pixels)
        self.speed = speed    # pixels per frame (negative = left-to-right)
        self.size = size      # rendered size in pixels
        self.wave_idx = wave_idx  # which wave layer to ride on (0-2)
        self.opacity = opacity    # 0.0 - 1.0
        self.bob_phase = bob_phase  # offset for gentle bobbing


class WaveBackground(QWidget):
    """Transparent overlay widget that paints animated sine waves
    with optional floating rubber duck sprites.
    """

    def __init__(
        self,
        waves: list[WaveConfig] | None = None,
        duck_count: int = 3,
        duck_size_range: tuple[int, int] = (12, 26),
        duck_opacity_range: tuple[float, float] = (0.18, 0.40),
        backdrop_alpha_scale: float = 1.0,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._waves = waves or DEFAULT_WAVES
        self._start_time = time.monotonic()
        self._duck_size_range = duck_size_range
        self._duck_opacity_range = duck_opacity_range
        self._backdrop_alpha_scale = max(0.0, backdrop_alpha_scale)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setObjectName("waveBackground")

        # Load duck pixmap
        self._duck_pixmap: QPixmap | None = None
        self._load_duck_icon()

        # Spawn duck sprites
        self._ducks: list[DuckSprite] = []
        self._duck_count = duck_count
        self._spawn_initial_ducks()

        # 30fps animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)  # ~30fps

    def _load_duck_icon(self):
        """Try to load rubber-duck.png from the icon folder."""
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "icon", "rubber-duck.png"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "icon", "rubber-duck.png"),
        ]
        for path in candidates:
            if os.path.exists(path):
                # Flip horizontally so duck faces right (travel direction)
                self._duck_pixmap = QPixmap(path).transformed(
                    QTransform().scale(-1, 1)
                )
                return

    def _spawn_initial_ducks(self):
        """Create the initial set of duck sprites at random positions."""
        for _ in range(self._duck_count):
            self._ducks.append(self._make_duck(random_x=True))

    def _make_duck(self, random_x: bool = False) -> DuckSprite:
        """Create a new duck sprite, optionally at a random x position."""
        w = max(self.width(), 1280)
        return DuckSprite(
            x=random.uniform(0, w) if random_x else random.uniform(-100, -40),
            speed=random.uniform(0.225, 0.6),  # slow drift right (25% slower)
            size=random.randint(*self._duck_size_range),
            wave_idx=random.randint(0, min(2, len(self._waves) - 1)),
            opacity=random.uniform(*self._duck_opacity_range),
            bob_phase=random.uniform(0, math.tau),
        )

    def _tick(self):
        """Advance duck positions and repaint."""
        w = self.width()
        for duck in self._ducks:
            duck.x += duck.speed
            # If duck floated off the right edge, respawn from left
            if duck.x > w + 60:
                duck.x = random.uniform(-120, -40)
                duck.speed = random.uniform(0.225, 0.6)
                duck.opacity = random.uniform(*self._duck_opacity_range)
                duck.bob_phase = random.uniform(0, math.tau)
        self.update()

    def paintEvent(self, event):
        """Render wave layers and duck sprites."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = self.width()
        h = self.height()
        t = time.monotonic() - self._start_time

        self._draw_backdrop(painter, w, h)

        # Draw wave layers
        for wave in self._waves:
            self._draw_wave(painter, wave, w, h, t)

        # Draw ducks on top of waves
        if self._duck_pixmap and not self._duck_pixmap.isNull():
            for duck in self._ducks:
                self._draw_duck(painter, duck, w, h, t)

        painter.end()

    def _draw_backdrop(self, painter: QPainter, w: int, h: int):
        base = QLinearGradient(0, 0, 0, h)
        base.setColorAt(0.0, self._scaled_color(QColor(5, 12, 24, 255)))
        base.setColorAt(0.45, self._scaled_color(QColor(9, 18, 34, 255)))
        base.setColorAt(1.0, self._scaled_color(QColor(4, 9, 19, 255)))
        painter.fillRect(self.rect(), base)

        top_glow = QRadialGradient(w * 0.22, h * 0.14, max(w, h) * 0.42)
        top_glow.setColorAt(0.0, self._scaled_color(QColor(95, 141, 227, 56)))
        top_glow.setColorAt(0.5, self._scaled_color(QColor(58, 102, 184, 20)))
        top_glow.setColorAt(1.0, self._scaled_color(QColor(0, 0, 0, 0)))
        painter.fillRect(self.rect(), top_glow)

        side_glow = QRadialGradient(w * 0.88, h * 0.22, max(w, h) * 0.24)
        side_glow.setColorAt(0.0, self._scaled_color(QColor(93, 172, 180, 28)))
        side_glow.setColorAt(1.0, self._scaled_color(QColor(0, 0, 0, 0)))
        painter.fillRect(self.rect(), side_glow)

    def _scaled_color(self, color: QColor) -> QColor:
        if self._backdrop_alpha_scale == 1.0:
            return color
        scaled = QColor(color)
        scaled.setAlpha(max(0, min(255, int(color.alpha() * self._backdrop_alpha_scale))))
        return scaled

    def _draw_duck(self, painter: QPainter, duck: DuckSprite,
                   w: int, h: int, t: float):
        """Draw a single duck sprite riding on its wave."""
        wave = self._waves[duck.wave_idx]
        # Calculate wave Y at duck's X position
        y = h * wave.y_offset + wave.amplitude * math.sin(
            wave.frequency * duck.x + wave.speed * t + wave.phase
        )
        y += (wave.amplitude * 0.3) * math.sin(
            wave.frequency * 1.7 * duck.x + wave.speed * 0.8 * t + wave.phase + 1.0
        )
        # Gentle vertical bobbing
        y += 3 * math.sin(t * 1.5 + duck.bob_phase)
        # Slight tilt based on wave slope
        tilt = 5 * math.cos(wave.frequency * duck.x + wave.speed * t + wave.phase)

        painter.save()
        painter.setOpacity(duck.opacity)
        painter.translate(duck.x, y - duck.size * 0.7)  # offset up so duck sits ON wave
        painter.rotate(tilt)
        target = QRectF(-duck.size / 2, -duck.size / 2, duck.size, duck.size)
        painter.drawPixmap(target, self._duck_pixmap,
                           QRectF(0, 0, self._duck_pixmap.width(), self._duck_pixmap.height()))
        painter.restore()

    def _draw_wave(self, painter: QPainter, wave: WaveConfig,
                   w: int, h: int, t: float):
        """Draw a single wave layer using QPainterPath."""
        path = QPainterPath()
        base_y = h * wave.y_offset
        step = 3  # pixel step for smoothness (lower = smoother but more CPU)

        # Start path at left edge
        x = 0
        y = base_y + wave.amplitude * math.sin(
            wave.frequency * x + wave.speed * t + wave.phase
        )
        path.moveTo(x, y)

        # Build sine curve
        while x <= w:
            y = base_y + wave.amplitude * math.sin(
                wave.frequency * x + wave.speed * t + wave.phase
            )
            # Add subtle secondary harmonic for natural feel
            y += (wave.amplitude * 0.3) * math.sin(
                wave.frequency * 1.7 * x + wave.speed * 0.8 * t + wave.phase + 1.0
            )
            path.lineTo(x, y)
            x += step

        if wave.thickness > 0:
            # Stroke-only wave (thin shimmer line)
            color = _parse_rgba(wave.color_top)
            pen = QPen(color, wave.thickness)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
        else:
            # Filled wave — close path to bottom
            path.lineTo(w, h)
            path.lineTo(0, h)
            path.closeSubpath()

            # Gradient fill
            gradient = QLinearGradient(0, base_y - wave.amplitude, 0, h)
            gradient.setColorAt(0, _parse_rgba(wave.color_top))
            gradient.setColorAt(1, _parse_rgba(wave.color_bot))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawPath(path)


def _parse_rgba(rgba_str: str) -> QColor:
    """Parse 'rgba(r, g, b, a)' string to QColor."""
    try:
        inner = rgba_str.strip().removeprefix("rgba(").removesuffix(")")
        parts = [p.strip() for p in inner.split(",")]
        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        a = float(parts[3])
        color = QColor(r, g, b)
        color.setAlphaF(a)
        return color
    except (ValueError, IndexError):
        return QColor(0, 0, 0, 0)
