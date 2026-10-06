"""The black-background overlay output window captured by OBS / fed to VGA."""
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QColor, QPainter, QAction, QGuiApplication
from PyQt6.QtWidgets import QWidget, QMenu

from .models import Field
from . import render


class OverlayWindow(QWidget):
    """Borderless, pure-black window that renders every active field."""

    def __init__(self):
        super().__init__()
        self.fields: List[Field] = []
        self.serial_values: Dict[str, str] = {}
        self._resolution = (1280, 1024)
        self._always_on_top = True
        self._drag_pos: Optional[QPoint] = None

        self.setWindowTitle("ROV Overlay Output")
        self._apply_flags()
        self.setAutoFillBackground(True)
        self.resize(*self._resolution)

        # Refresh timer ~10 fps
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(100)

    # ------------------------------------------------------------------
    def _apply_flags(self):
        flags = Qt.WindowType.FramelessWindowHint
        if self._always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def set_resolution(self, w: int, h: int):
        self._resolution = (w, h)
        self.resize(w, h)

    def set_always_on_top(self, on: bool):
        self._always_on_top = on
        was_visible = self.isVisible()
        self._apply_flags()
        if was_visible:
            self.show()

    def set_fields(self, fields: List[Field]):
        self.fields = fields
        self.update()

    def set_serial_values(self, values: Dict[str, str]):
        self.serial_values = values

    def move_to_monitor(self, index: int):
        screens = QGuiApplication.screens()
        if 0 <= index < len(screens):
            geo = screens[index].geometry()
            self.move(geo.x(), geo.y())
            self.resize(*self._resolution)

    # ------------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        # Pure black background
        painter.fillRect(self.rect(), QColor(0, 0, 0))

        # Scale design-space (resolution) to the current window size
        dw, dh = self._resolution
        sx = self.width() / dw if dw else 1
        sy = self.height() / dh if dh else 1
        painter.scale(sx, sy)

        for f in self.fields:
            if f.visible:
                render.paint_field(painter, f, self.serial_values)
        painter.end()

    # ------------------------------------------------------------------
    # Allow dragging the borderless window around / to another monitor
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        screens = QGuiApplication.screens()
        for i, screen in enumerate(screens):
            act = QAction(f"Move to Monitor {i + 1} ({screen.name()})", self)
            act.triggered.connect(lambda _=False, idx=i: self.move_to_monitor(idx))
            menu.addAction(act)
        menu.addSeparator()

        res_menu = menu.addMenu("Set Resolution")
        for label, (w, h) in [
            ("1280 x 1024", (1280, 1024)),
            ("1920 x 1080", (1920, 1080)),
            ("720 x 576", (720, 576)),
            ("1024 x 768", (1024, 768)),
        ]:
            a = QAction(label, self)
            a.triggered.connect(lambda _=False, ww=w, hh=h: self.set_resolution(ww, hh))
            res_menu.addAction(a)

        top_act = QAction("Always On Top", self)
        top_act.setCheckable(True)
        top_act.setChecked(self._always_on_top)
        top_act.triggered.connect(lambda checked: self.set_always_on_top(checked))
        menu.addAction(top_act)

        menu.addSeparator()
        hide_act = QAction("Hide Overlay Window", self)
        hide_act.triggered.connect(self.hide)
        menu.addAction(hide_act)

        menu.exec(event.globalPos())
