"""Shared rendering helpers used by the overlay window and the editor canvas."""
from __future__ import annotations

import datetime
import os
from typing import Dict, Optional

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap, QFontMetrics

from .models import (
    Field, TYPE_STATIC, TYPE_DATE, TYPE_TIME, TYPE_SERIAL, TYPE_IMAGE,
    TYPE_TEXTFILE,
)
from .paths import resolve_logo

# cache for scaled pixmaps keyed by (path, w, h)
_pix_cache: Dict[str, QPixmap] = {}


def _qcolor(rgb) -> QColor:
    try:
        return QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]))
    except Exception:
        return QColor(255, 255, 255)


def format_number(raw: str, fmt: str) -> str:
    """Apply a legacy-style numeric format like ``#0.00`` or ``#0.000V``."""
    if raw is None:
        return ""
    raw = str(raw).strip()
    if not fmt:
        return raw
    # Count decimals requested
    suffix = ""
    core = fmt
    # trailing non-format chars become suffix (e.g. the 'V' in #0.0000V)
    while core and core[-1] not in "0#.":
        suffix = core[-1] + suffix
        core = core[:-1]
    decimals = 0
    if "." in core:
        decimals = len(core.split(".", 1)[1].replace("#", "0"))
    try:
        val = float(raw)
        return f"{val:.{decimals}f}{suffix}"
    except (ValueError, TypeError):
        return raw + suffix


def resolve_value(f: Field, serial_values: Optional[Dict[str, str]] = None,
                  now: Optional[datetime.datetime] = None) -> str:
    """Compute the display value (without the label) for a field."""
    now = now or datetime.datetime.now()
    if f.type == TYPE_DATE:
        return now.strftime("%d/%m/%Y")
    if f.type == TYPE_TIME:
        return now.strftime("%H:%M:%S")
    if f.type == TYPE_SERIAL:
        sv = (serial_values or {}).get(f.serial_field)
        if sv is None or sv == "":
            # Show a formatted placeholder zero so layout is visible
            return format_number("0", f.format_string)
        return format_number(sv, f.format_string)
    if f.type == TYPE_TEXTFILE:
        path = f.value
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="latin-1") as fh:
                    return fh.read()
            except Exception:
                return ""
        return f.value
    # static
    return f.value


def _get_pixmap(path: str, w: int, h: int) -> Optional[QPixmap]:
    real = resolve_logo(path)
    if not real or not os.path.exists(real):
        return None
    key = f"{real}|{w}|{h}"
    if key in _pix_cache:
        return _pix_cache[key]
    pm = QPixmap(real)
    if pm.isNull():
        return None
    scaled = pm.scaled(max(1, w), max(1, h), Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
    _pix_cache[key] = scaled
    return scaled


def clear_pixmap_cache() -> None:
    _pix_cache.clear()


def field_bounds(painter_font_provider, f: Field, serial_values=None):
    """Return (w, h) bounding size estimate for a field (in design pixels)."""
    if f.type == TYPE_IMAGE:
        return (f.width, f.height)
    font = QFont(f.font_name, f.font_size)
    font.setBold(f.bold)
    fm = QFontMetrics(font)
    value = resolve_value(f, serial_values)
    label = f.label if f.label_position != "none" else ""

    text = value
    if label:
        if f.label_position in ("left", "right"):
            text = f"{label} {value}" if f.label_position == "left" else f"{value} {label}"
        # above/below -> width is max, height double
    w = fm.horizontalAdvance(text) + 10
    h = fm.height() + 6
    if label and f.label_position in ("above", "below"):
        lf = QFont(f.font_name, f.label_font_size)
        lf.setBold(f.bold)
        lfm = QFontMetrics(lf)
        w = max(w, lfm.horizontalAdvance(label) + 10)
        h += lfm.height()
    return (w, h)


def paint_field(painter: QPainter, f: Field, serial_values=None,
                now=None) -> QRectF:
    """Paint one field at its design coordinates. Returns the bounding rect."""
    if not f.visible:
        return QRectF(f.x, f.y, 0, 0)

    if f.type == TYPE_IMAGE:
        pm = _get_pixmap(f.image_path, f.width, f.height)
        if pm is not None:
            painter.drawPixmap(int(f.x), int(f.y), pm)
            return QRectF(f.x, f.y, pm.width(), pm.height())
        # placeholder box when logo missing
        painter.save()
        painter.setPen(QColor(120, 120, 120))
        painter.setBrush(QColor(40, 40, 40))
        rect = QRectF(f.x, f.y, f.width, f.height)
        painter.drawRect(rect)
        painter.setPen(QColor(180, 180, 180))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f.label or "LOGO")
        painter.restore()
        return rect

    value = resolve_value(f, serial_values, now)
    label = f.label if f.label_position != "none" else ""

    value_font = QFont(f.font_name, f.font_size)
    value_font.setBold(f.bold)
    label_font = QFont(f.font_name, f.label_font_size)
    label_font.setBold(f.bold)

    vfm = QFontMetrics(value_font)
    lfm = QFontMetrics(label_font)

    # Multi-line (text file) handling
    if "\n" in value:
        painter.save()
        painter.setFont(value_font)
        painter.setPen(_qcolor(f.font_color))
        lines = value.split("\n")
        y = f.y + vfm.ascent()
        max_w = 0
        for ln in lines:
            painter.drawText(int(f.x), int(y), ln)
            max_w = max(max_w, vfm.horizontalAdvance(ln))
            y += vfm.height()
        painter.restore()
        return QRectF(f.x, f.y, max_w, vfm.height() * len(lines))

    # Compose label + value positions
    gap = 8
    label_w = lfm.horizontalAdvance(label) if label else 0
    value_w = vfm.horizontalAdvance(value)

    if f.bg_enabled:
        total_w = value_w + (label_w + gap if label and f.label_position in ("left", "right") else 0)
        total_h = max(vfm.height(), lfm.height())
        painter.save()
        bg = _qcolor(f.bg_color)
        bg.setAlpha(200)
        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(f.x - 3, f.y - 2, total_w + 6, total_h + 4))
        painter.restore()

    vx = f.x
    vy = f.y + vfm.ascent()

    # Draw label
    if label:
        painter.setFont(label_font)
        painter.setPen(_qcolor(f.label_color))
        if f.label_position == "left":
            painter.drawText(int(f.x), int(f.y + lfm.ascent()), label)
            vx = f.x + label_w + gap
        elif f.label_position == "right":
            painter.drawText(int(f.x + value_w + gap), int(f.y + lfm.ascent()), label)
        elif f.label_position == "above":
            painter.drawText(int(f.x), int(f.y + lfm.ascent()), label)
            vy = f.y + lfm.height() + vfm.ascent()
        elif f.label_position == "below":
            painter.drawText(int(f.x), int(f.y + vfm.height() + lfm.ascent()), label)

    # Draw value
    painter.setFont(value_font)
    painter.setPen(_qcolor(f.font_color))
    painter.drawText(int(vx), int(vy), value)

    w = (label_w + gap + value_w) if (label and f.label_position in ("left", "right")) else max(value_w, label_w)
    h = vfm.height() + (lfm.height() if label and f.label_position in ("above", "below") else 0)
    return QRectF(f.x, f.y, w, h)
