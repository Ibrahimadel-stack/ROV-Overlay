"""Main control window with the four tabs and shared application state."""
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel, QStatusBar,
)

from .models import Profile, SerialStringFormat
from .overlay_window import OverlayWindow
from .serial_reader import SerialReader
from .tabs.editor_tab import EditorTab
from .tabs.profiles_tab import ProfilesTab
from .tabs.serial_tab import SerialTab
from .tabs.logo_tab import LogoTab


class ControlWindow(QMainWindow):
    def __init__(self, profile: Optional[Profile] = None):
        super().__init__()
        self.profile = profile or Profile()
        self.serial_values: Dict[str, str] = {}
        self.serial_reader: Optional[SerialReader] = None

        self.overlay = OverlayWindow()
        self.overlay.set_fields(self.profile.fields)

        self.setWindowTitle("ROV Video Overlay \u2014 Control")
        self.resize(1200, 760)

        self.tabs = QTabWidget()
        self.editor_tab = EditorTab(self)
        self.profiles_tab = ProfilesTab(self)
        self.serial_tab = SerialTab(self)
        self.logo_tab = LogoTab(self)
        self.tabs.addTab(self.editor_tab, "\U0001F3AC  Overlay Editor")
        self.tabs.addTab(self.profiles_tab, "\U0001F4C1  Profiles")
        self.tabs.addTab(self.serial_tab, "\U0001F4E1  Serial Settings")
        self.tabs.addTab(self.logo_tab, "\U0001F5BC  Logo Manager")
        self.setCentralWidget(self.tabs)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

        self.refresh_all()

        # push serial values to overlay/canvas periodically
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._push_values)
        self._tick.start(100)

    # ------------------------------------------------------------------
    # Shared state operations
    # ------------------------------------------------------------------
    def set_profile(self, profile: Profile):
        self.profile = profile
        self.overlay.set_resolution(*profile.resolution)
        self.overlay.set_fields(profile.fields)

    def update_title(self):
        self.setWindowTitle(f"ROV Video Overlay \u2014 {self.profile.profile_name}")

    def refresh_all(self):
        self.editor_tab.refresh()
        self.serial_tab.load_from_profile()
        if hasattr(self, "logo_tab"):
            self.logo_tab.refresh_grid()
        self.update_title()
        self.sync_overlay()

    def on_fields_changed(self):
        self.editor_tab.refresh()
        self.sync_overlay()

    def sync_overlay(self):
        self.overlay.set_fields(self.profile.fields)
        self.overlay.set_serial_values(self.serial_values)

    def _push_values(self):
        self.overlay.set_serial_values(self.serial_values)
        self.editor_tab.set_serial_values(self.serial_values)

    # ------------------------------------------------------------------
    # Overlay window control
    # ------------------------------------------------------------------
    def toggle_overlay_window(self):
        if self.overlay.isVisible():
            self.overlay.hide()
            self.editor_tab.btn_show_output.setText("\u25B6  Show Live Output Window")
        else:
            screens = QGuiApplication.screens()
            self.overlay.set_resolution(*self.profile.resolution)
            if len(screens) > 1:
                self.overlay.move_to_monitor(1)
            self.overlay.show()
            self.editor_tab.btn_show_output.setText("\u25A0  Hide Live Output Window")

    # ------------------------------------------------------------------
    # Serial control
    # ------------------------------------------------------------------
    def start_serial(self, port: str, baud: int, formats: List[SerialStringFormat]):
        self.stop_serial()
        self.serial_reader = SerialReader(port, baud, formats)
        self.serial_reader.line_received.connect(self._on_line)
        self.serial_reader.data_parsed.connect(self._on_parsed)
        self.serial_reader.connection_changed.connect(self._on_conn)
        self.serial_reader.start()

    def stop_serial(self):
        if self.serial_reader:
            try:
                self.serial_reader.stop()
            except Exception:
                pass
            self.serial_reader = None

    def _on_line(self, line: str):
        self.serial_tab.append_monitor(line)

    def _on_parsed(self, values: dict):
        self.serial_values.update(values)

    def _on_conn(self, connected: bool, message: str):
        self.serial_tab.set_status(connected, message)
        self.statusBar().showMessage(message)

    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self.stop_serial()
        self.overlay.close()
        super().closeEvent(event)
