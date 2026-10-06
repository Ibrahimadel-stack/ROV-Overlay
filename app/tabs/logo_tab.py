"""Logo Manager tab: grid of logos, add/remove, assign to slots."""
from __future__ import annotations

import os
import shutil

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QGroupBox, QFileDialog, QMessageBox, QComboBox,
)

from ..paths import logos_dir
from ..models import Field, TYPE_IMAGE

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif")


class LogoTab(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self._build()
        self.refresh_grid()

    def _build(self):
        root = QHBoxLayout(self)

        left = QVBoxLayout()
        left.addWidget(QLabel("Logo Library", objectName="heading"))
        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.ViewMode.IconMode)
        self.grid.setIconSize(QSize(120, 90))
        self.grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.grid.setSpacing(12)
        self.grid.setMovement(QListWidget.Movement.Static)
        left.addWidget(self.grid, 1)

        btns = QHBoxLayout()
        self.btn_add = QPushButton("\u2795 Add Logo"); self.btn_add.setObjectName("accent")
        self.btn_remove = QPushButton("\u2715 Remove"); self.btn_remove.setObjectName("danger")
        self.btn_place = QPushButton("\U0001F4CC Place On Overlay")
        btns.addWidget(self.btn_add); btns.addWidget(self.btn_remove)
        btns.addWidget(self.btn_place)
        left.addLayout(btns)
        root.addLayout(left, 2)

        # Right: slot assignment
        right = QVBoxLayout()
        slot_box = QGroupBox("Assign Logo Slots")
        sv = QVBoxLayout(slot_box)
        sv.addWidget(QLabel("Pick a library logo then assign to a slot.\n"
                            "Assigning adds/updates the logo on the overlay.",
                            objectName="subtle"))
        self.btn_client = QPushButton("Set as CLIENT Logo (top-right)")
        self.btn_contractor = QPushButton("Set as CONTRACTOR Logo (top-left)")
        self.btn_extra = QPushButton("Set as EXTRA Logo")
        for b in (self.btn_client, self.btn_contractor, self.btn_extra):
            sv.addWidget(b)
        right.addWidget(slot_box)

        info = QGroupBox("Selected Logo")
        iv = QVBoxLayout(info)
        self.preview = QLabel("No logo selected")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(160)
        self.preview.setStyleSheet("background:#000; border:1px solid #0f3460; border-radius:6px;")
        iv.addWidget(self.preview)
        self.lbl_name = QLabel("-", objectName="subtle")
        iv.addWidget(self.lbl_name)
        right.addWidget(info)
        right.addStretch()
        root.addLayout(right, 1)

        self.btn_add.clicked.connect(self.add_logo)
        self.btn_remove.clicked.connect(self.remove_logo)
        self.btn_place.clicked.connect(lambda: self.assign_slot("Extra"))
        self.btn_client.clicked.connect(lambda: self.assign_slot("Client"))
        self.btn_contractor.clicked.connect(lambda: self.assign_slot("Contractor"))
        self.btn_extra.clicked.connect(lambda: self.assign_slot("Extra"))
        self.grid.itemSelectionChanged.connect(self.on_select)

    # ------------------------------------------------------------------
    def refresh_grid(self):
        self.grid.clear()
        d = logos_dir()
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith(IMAGE_EXTS) and fn.lower() != "thumbs.db":
                path = os.path.join(d, fn)
                pm = QPixmap(path)
                if pm.isNull():
                    # empty/corrupt file placeholder
                    icon = QIcon()
                else:
                    icon = QIcon(pm)
                item = QListWidgetItem(icon, fn)
                item.setData(Qt.ItemDataRole.UserRole, fn)
                item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
                self.grid.addItem(item)

    def _selected_name(self):
        item = self.grid.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def on_select(self):
        name = self._selected_name()
        if not name:
            self.preview.setText("No logo selected")
            self.lbl_name.setText("-")
            return
        path = os.path.join(logos_dir(), name)
        pm = QPixmap(path)
        if pm.isNull():
            self.preview.setText("(empty / unreadable image)")
        else:
            self.preview.setPixmap(pm.scaled(240, 150, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))
        self.lbl_name.setText(name)

    def add_logo(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Logo(s)", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        for path in paths:
            try:
                shutil.copy2(path, os.path.join(logos_dir(), os.path.basename(path)))
            except Exception as exc:
                QMessageBox.warning(self, "Copy failed", str(exc))
        if paths:
            self.refresh_grid()

    def remove_logo(self):
        name = self._selected_name()
        if not name:
            return
        if QMessageBox.question(self, "Remove", f"Delete logo file '{name}'?") \
                != QMessageBox.StandardButton.Yes:
            return
        try:
            os.remove(os.path.join(logos_dir(), name))
        except OSError as exc:
            QMessageBox.warning(self, "Delete failed", str(exc))
        self.refresh_grid()

    def assign_slot(self, slot: str):
        name = self._selected_name()
        if not name:
            QMessageBox.information(self, "No selection", "Select a logo first.")
            return
        # Find existing field for this slot (by label) or create one
        target = None
        for f in self.profile.fields:
            if f.type == TYPE_IMAGE and f.label.lower() == slot.lower():
                target = f
                break
        if target is None:
            positions = {"Client": (1050, 10), "Contractor": (60, 30), "Extra": (550, 20)}
            x, y = positions.get(slot, (400, 20))
            target = Field(name=f"{slot}Logo", type=TYPE_IMAGE, label=slot,
                           x=x, y=y, width=200, height=90)
            self.profile.fields.append(target)
        target.image_path = name
        self.main.on_fields_changed()
        QMessageBox.information(self, "Assigned",
                               f"'{name}' assigned to {slot} slot.\n"
                               "Reposition/resize it on the Overlay Editor tab.")

    @property
    def profile(self):
        return self.main.profile
