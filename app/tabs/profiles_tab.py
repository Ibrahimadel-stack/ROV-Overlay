"""Profiles tab: metadata editing + save/load/import/export."""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QLineEdit,
    QComboBox, QGroupBox, QFormLayout, QListWidget, QFileDialog,
    QMessageBox,
)

from ..models import Profile
from ..ovl_io import import_ovl, export_ovl
from ..paths import profiles_dir

JOB_TYPES = ["GVI", "Intervention", "Drill Support", "Pipeline Survey", "EMAT"]


class ProfilesTab(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self._build()
        self.refresh_list()
        self.load_metadata()

    def _build(self):
        root = QHBoxLayout(self)

        # Left: profile list
        left = QVBoxLayout()
        left.addWidget(QLabel("Saved Profiles", objectName="heading"))
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _: self.load_selected())
        left.addWidget(self.list, 1)
        btns = QHBoxLayout()
        self.btn_load = QPushButton("Load")
        self.btn_delete = QPushButton("Delete"); self.btn_delete.setObjectName("danger")
        btns.addWidget(self.btn_load); btns.addWidget(self.btn_delete)
        left.addLayout(btns)
        root.addLayout(left, 1)

        # Right: metadata + actions
        right = QVBoxLayout()
        meta = QGroupBox("Profile Details")
        form = QFormLayout(meta)
        self.in_name = QLineEdit()
        self.in_client = QLineEdit()
        self.in_job = QComboBox(); self.in_job.addItems(JOB_TYPES); self.in_job.setEditable(True)
        self.in_vessel = QLineEdit()
        self.in_rov = QLineEdit()
        self.in_contractor = QLineEdit()
        form.addRow("Profile Name", self.in_name)
        form.addRow("Client Name", self.in_client)
        form.addRow("Job Type", self.in_job)
        form.addRow("Vessel Name", self.in_vessel)
        form.addRow("ROV Name", self.in_rov)
        form.addRow("Contractor", self.in_contractor)
        right.addWidget(meta)

        for w in (self.in_name, self.in_client, self.in_vessel, self.in_rov,
                  self.in_contractor):
            w.editingFinished.connect(self.apply_metadata)
        self.in_job.currentTextChanged.connect(lambda _: self.apply_metadata())

        actions = QGroupBox("Actions")
        av = QVBoxLayout(actions)
        row1 = QHBoxLayout()
        self.btn_new = QPushButton("\u2795 New Profile")
        self.btn_save = QPushButton("\U0001F4BE Save Profile"); self.btn_save.setObjectName("accent")
        row1.addWidget(self.btn_new); row1.addWidget(self.btn_save)
        av.addLayout(row1)
        row2 = QHBoxLayout()
        self.btn_import = QPushButton("\u2B07 Import .ovl")
        self.btn_export_ovl = QPushButton("\u2B06 Export .ovl")
        row2.addWidget(self.btn_import); row2.addWidget(self.btn_export_ovl)
        av.addLayout(row2)
        row3 = QHBoxLayout()
        self.btn_import_json = QPushButton("\u2B07 Import .json")
        self.btn_export_json = QPushButton("\u2B06 Export .json")
        row3.addWidget(self.btn_import_json); row3.addWidget(self.btn_export_json)
        av.addLayout(row3)
        right.addWidget(actions)
        right.addStretch()
        root.addLayout(right, 1)

        # Wire
        self.btn_new.clicked.connect(self.new_profile)
        self.btn_save.clicked.connect(self.save_profile)
        self.btn_load.clicked.connect(self.load_selected)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_import.clicked.connect(self.import_ovl_file)
        self.btn_export_ovl.clicked.connect(self.export_ovl_file)
        self.btn_import_json.clicked.connect(self.import_json_file)
        self.btn_export_json.clicked.connect(self.export_json_file)

    # ------------------------------------------------------------------
    @property
    def profile(self):
        return self.main.profile

    def refresh_list(self):
        self.list.clear()
        d = profiles_dir()
        for fn in sorted(os.listdir(d)):
            if fn.lower().endswith(".json"):
                self.list.addItem(os.path.splitext(fn)[0])

    def load_metadata(self):
        p = self.profile
        self.in_name.setText(p.profile_name)
        self.in_client.setText(p.client)
        self.in_job.setCurrentText(p.job_type)
        self.in_vessel.setText(p.vessel)
        self.in_rov.setText(p.rov)
        self.in_contractor.setText(p.contractor)

    def apply_metadata(self):
        p = self.profile
        p.profile_name = self.in_name.text()
        p.client = self.in_client.text()
        p.job_type = self.in_job.currentText()
        p.vessel = self.in_vessel.text()
        p.rov = self.in_rov.text()
        p.contractor = self.in_contractor.text()
        self.main.update_title()

    # ------------------------------------------------------------------
    def new_profile(self):
        self.main.set_profile(Profile())
        self.load_metadata()
        self.main.refresh_all()

    def save_profile(self):
        self.apply_metadata()
        name = self.profile.profile_name.strip() or "Untitled"
        safe = "".join(c for c in name if c not in '\\/:*?"<>|')
        path = os.path.join(profiles_dir(), safe + ".json")
        self.profile.save(path)
        self.refresh_list()
        QMessageBox.information(self, "Saved", f"Profile saved:\n{path}")

    def load_selected(self):
        item = self.list.currentItem()
        if not item:
            return
        path = os.path.join(profiles_dir(), item.text() + ".json")
        try:
            prof = Profile.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", str(exc))
            return
        self.main.set_profile(prof)
        self.load_metadata()
        self.main.refresh_all()

    def delete_selected(self):
        item = self.list.currentItem()
        if not item:
            return
        if QMessageBox.question(self, "Delete", f"Delete profile '{item.text()}'?") \
                != QMessageBox.StandardButton.Yes:
            return
        path = os.path.join(profiles_dir(), item.text() + ".json")
        try:
            os.remove(path)
        except OSError:
            pass
        self.refresh_list()

    def import_ovl_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import .ovl Profile", "",
                                              "Overlay Profiles (*.ovl)")
        if not path:
            return
        try:
            prof = import_ovl(path)
        except Exception as exc:
            QMessageBox.critical(self, "Import error", str(exc))
            return
        self.main.set_profile(prof)
        self.load_metadata()
        self.main.refresh_all()
        QMessageBox.information(self, "Imported",
                               f"Imported '{prof.profile_name}' with "
                               f"{len(prof.fields)} fields.")

    def export_ovl_file(self):
        self.apply_metadata()
        path, _ = QFileDialog.getSaveFileName(
            self, "Export .ovl", self.profile.profile_name + ".ovl",
            "Overlay Profiles (*.ovl)")
        if not path:
            return
        export_ovl(self.profile, path)
        QMessageBox.information(self, "Exported", f"Exported to:\n{path}")

    def import_json_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import .json Profile", "",
                                              "JSON Profiles (*.json)")
        if not path:
            return
        try:
            prof = Profile.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Import error", str(exc))
            return
        self.main.set_profile(prof)
        self.load_metadata()
        self.main.refresh_all()

    def export_json_file(self):
        self.apply_metadata()
        path, _ = QFileDialog.getSaveFileName(
            self, "Export .json", self.profile.profile_name + ".json",
            "JSON Profiles (*.json)")
        if path:
            self.profile.save(path)
            QMessageBox.information(self, "Exported", f"Exported to:\n{path}")
