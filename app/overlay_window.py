"""The black-background overlay output window captured by OBS / fed to VGA."""
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QColor, QPainter, QAction, QGuiApplication, QImage
from PyQt6.QtWidgets import QWidget, QMenu

from .models import Field
from . import render
from .video_capture import VideoCaptureThread


class OverlayWindow(QWidget):
    """Borderless overlay window.

    Background is the live SDI video feed when a capture device is selected,
    otherwise a pure-black fill. Overlay fields are always painted on top.
    """

    def __init__(self):
        super().__init__()
        self.fields: List[Field] = []
        self.serial_values: Dict[str, str] = {}
        self._resolution = (1280, 1024)
        self._always_on_top = True
        self._drag_pos: Optional[QPoint] = None

        # Video background state
        self.video_thread: Optional[VideoCaptureThread] = None
        self.current_frame: Optional[QImage] = None
        self.video_device: Optional[int] = None
        self.keep_aspect = False  # fill the whole window by default

        self.setWindowTitle("ROV Overlay Output")
        self._apply_flags()
        self.setAutoFillBackground(True)
        self.resize(*self._resolution)

        # Repaint timer at ~25 fps (40 ms), independent of the capture speed.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(40)

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

    # ------------------------------------------------------------------
    # Video background control
    # ------------------------------------------------------------------
    def set_video_source(self, device_index: Optional[int]):
        """Start capturing from a device, or clear to a black background.

        Pass None (or a negative index) to disable video and revert to black.
        """
        self.stop_video()
        if device_index is None or device_index < 0:
            self.video_device = None
            self.current_frame = None
            self.update()
            return
        self.video_device = device_index
        self.video_thread = VideoCaptureThread(device_index)
        self.video_thread.frame_ready.connect(self._on_frame)
        self.video_thread.status_changed.connect(self._on_video_status)
        self.video_thread.start()

    def stop_video(self):
        if self.video_thread is not None:
            try:
                self.video_thread.frame_ready.disconnect(self._on_frame)
                self.video_thread.status_changed.disconnect(self._on_video_status)
            except Exception:
                pass
            try:
                self.video_thread.stop()
            except Exception:
                pass
            self.video_thread = None
        self.current_frame = None

    def _on_frame(self, image):
        # image is a QImage, or None on failure/disconnect -> black background
        self.current_frame = image if isinstance(image, QImage) else None

    def _on_video_status(self, opened: bool, message: str):
        # Expose status via a Qt signal-free hook; ControlWindow may connect
        # to the thread directly. Keep a simple attribute for diagnostics.
        self._video_status = (opened, message)
        if not opened:
            self.current_frame = None

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
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Layer 1 (background): live video frame if available, else black.
        painter.fillRect(self.rect(), QColor(0, 0, 0))
        frame = self.current_frame
        if frame is not None and not frame.isNull():
            if self.keep_aspect:
                scaled = frame.scaled(
                    self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                x = (self.width() - scaled.width()) // 2
                y = (self.height() - scaled.height()) // 2
                painter.drawImage(x, y, scaled)
            else:
                # Fill the whole window (IgnoreAspectRatio) for the pilot view.
                painter.drawImage(self.rect(), frame)

        # Layer 2 (foreground): overlay fields.
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

        aspect_act = QAction("Keep Video Aspect Ratio", self)
        aspect_act.setCheckable(True)
        aspect_act.setChecked(self.keep_aspect)
        aspect_act.triggered.connect(self._set_keep_aspect)
        menu.addAction(aspect_act)

        menu.addSeparator()
        hide_act = QAction("Hide Overlay Window", self)
        hide_act.triggered.connect(self.hide)
        menu.addAction(hide_act)

        menu.exec(event.globalPos())

    def _set_keep_aspect(self, on: bool):
        self.keep_aspect = on
        self.update()

    def closeEvent(self, event):
        self.stop_video()
        super().closeEvent(event)
