"""Interactive editor canvas: scaled overlay preview with click-select & drag."""
from __future__ import annotations

from typing import List, Optional, Dict

from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from .models import Field
from . import render


class EditorCanvas(QWidget):
    """Shows the overlay at preview scale and lets the user move fields."""

    field_selected = pyqtSignal(object)   # Field or None
    field_moved = pyqtSignal(object)      # Field (position changed)
    field_changed = pyqtSignal()          # generic repaint request upstream

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fields: List[Field] = []
        self.serial_values: Dict[str, str] = {}
        self.design_size = (1280, 1024)
        self.selected: Optional[Field] = None
        self._dragging = False
        self._drag_offset = QPointF(0, 0)
        self._field_rects: Dict[str, QRectF] = {}   # id -> rect in widget coords
        self.setMinimumSize(640, 512)
        self.setMouseTracking(True)
        self.setStyleSheet("background:#000;")

    # ------------------------------------------------------------------
    def set_fields(self, fields: List[Field]):
        self.fields = fields
        if self.selected and self.selected not in fields:
            self.selected = None
            self.field_selected.emit(None)
        self.update()

    def set_design_size(self, w: int, h: int):
        self.design_size = (w, h)
        self.update()

    def set_serial_values(self, values: Dict[str, str]):
        self.serial_values = values
        self.update()

    def select_field(self, f: Optional[Field]):
        self.selected = f
        self.field_selected.emit(f)
        self.update()

    # ------------------------------------------------------------------
    def _scale(self):
        dw, dh = self.design_size
        return min(self.width() / dw, self.height() / dh)

    def _offset(self, scale):
        dw, dh = self.design_size
        ox = (self.width() - dw * scale) / 2
        oy = (self.height() - dh * scale) / 2
        return ox, oy

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.fillRect(self.rect(), QColor(20, 20, 20))

        scale = self._scale()
        ox, oy = self._offset(scale)
        dw, dh = self.design_size

        # Draw the black overlay area
        painter.save()
        painter.translate(ox, oy)
        painter.scale(scale, scale)
        painter.fillRect(QRectF(0, 0, dw, dh), QColor(0, 0, 0))
        # subtle border of the design area
        painter.setPen(QPen(QColor(60, 60, 90), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(0, 0, dw, dh))

        self._field_rects = {}
        for f in self.fields:
            rect = render.paint_field(painter, f, self.serial_values)
            # Store the rect in widget coordinates for hit-testing
            wr = QRectF(ox + rect.x() * scale, oy + rect.y() * scale,
                        max(rect.width(), 10) * scale, max(rect.height(), 10) * scale)
            self._field_rects[f.id] = wr
        painter.restore()

        # Selection handles (draw in widget coordinates)
        if self.selected and self.selected.id in self._field_rects:
            r = self._field_rects[self.selected.id]
            pen = QPen(QColor(0, 160, 255), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r.adjusted(-3, -3, 3, 3))
            # corner handles
            painter.setBrush(QColor(0, 160, 255))
            painter.setPen(Qt.PenStyle.NoPen)
            hs = 4
            for cx, cy in [(r.left(), r.top()), (r.right(), r.top()),
                           (r.left(), r.bottom()), (r.right(), r.bottom())]:
                painter.drawRect(QRectF(cx - hs, cy - hs, hs * 2, hs * 2))
        painter.end()

    # ------------------------------------------------------------------
    def _field_at(self, pos: QPointF) -> Optional[Field]:
        # iterate in reverse so top-most (last drawn) wins
        for f in reversed(self.fields):
            r = self._field_rects.get(f.id)
            if r and r.adjusted(-3, -3, 3, 3).contains(pos):
                return f
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            f = self._field_at(pos)
            self.select_field(f)
            if f is not None:
                self._dragging = True
                scale = self._scale()
                ox, oy = self._offset(scale)
                fx_widget = ox + f.x * scale
                fy_widget = oy + f.y * scale
                self._drag_offset = QPointF(pos.x() - fx_widget, pos.y() - fy_widget)

    def mouseMoveEvent(self, event):
        if self._dragging and self.selected is not None:
            scale = self._scale()
            ox, oy = self._offset(scale)
            pos = event.position()
            new_x = (pos.x() - self._drag_offset.x() - ox) / scale
            new_y = (pos.y() - self._drag_offset.y() - oy) / scale
            dw, dh = self.design_size
            self.selected.x = int(max(0, min(dw, new_x)))
            self.selected.y = int(max(0, min(dh, new_y)))
            self.field_moved.emit(self.selected)
            self.update()

    def mouseReleaseEvent(self, event):
        self._dragging = False
