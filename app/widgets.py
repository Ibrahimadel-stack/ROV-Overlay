"""Small reusable widgets."""
from __future__ import annotations

from typing import List

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QPushButton, QColorDialog


class ColorButton(QPushButton):
    """A button showing a colour swatch; opens a colour dialog when clicked."""

    color_changed = pyqtSignal(list)

    def __init__(self, rgb: List[int] = None, parent=None):
        super().__init__(parent)
        self._rgb = list(rgb) if rgb else [255, 255, 255]
        self.setFixedSize(60, 28)
        self.clicked.connect(self._pick)
        self._refresh()

    def _refresh(self):
        r, g, b = self._rgb
        text_col = "#000" if (r + g + b) > 380 else "#fff"
        self.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); color:{text_col};"
            "border:1px solid #0f3460; border-radius:5px; font-size:10px;"
        )
        self.setText(f"{r},{g},{b}")

    def set_color(self, rgb: List[int]):
        self._rgb = list(rgb)
        self._refresh()

    def color(self) -> List[int]:
        return list(self._rgb)

    def _pick(self):
        c = QColorDialog.getColor(QColor(*self._rgb), self, "Select Color")
        if c.isValid():
            self._rgb = [c.red(), c.green(), c.blue()]
            self._refresh()
            self.color_changed.emit(self._rgb)
