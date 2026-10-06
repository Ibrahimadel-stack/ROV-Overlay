"""Overlay Editor tab: visual canvas + field property panel + toolbar."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QLineEdit,
    QComboBox, QSpinBox, QCheckBox, QGroupBox, QFormLayout, QScrollArea,
    QFileDialog, QFrame, QSizePolicy,
)

from ..canvas import EditorCanvas
from ..widgets import ColorButton
from ..models import (
    Field, TYPE_STATIC, TYPE_SERIAL, TYPE_DATE, TYPE_TIME, TYPE_IMAGE,
    TYPE_TEXTFILE, SERIAL_FIELDS, LABEL_LEFT, LABEL_RIGHT, LABEL_ABOVE,
    LABEL_BELOW, LABEL_NONE,
)

LABEL_POSITIONS = [LABEL_LEFT, LABEL_RIGHT, LABEL_ABOVE, LABEL_BELOW, LABEL_NONE]
FONT_CHOICES = ["Arial", "Segoe UI", "Tahoma", "Verdana", "Calibri",
                "Times New Roman", "Courier New", "Consolas", "Impact"]


class EditorTab(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self._loading = False
        self._build()

    # ------------------------------------------------------------------
    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        # Left: toolbar + canvas
        left = QVBoxLayout()

        toolbar = QHBoxLayout()
        self.btn_add_text = QPushButton("\u2795  Text Field")
        self.btn_add_serial = QPushButton("\U0001F4E1  Live Data")
        self.btn_add_logo = QPushButton("\U0001F5BC  Logo")
        self.btn_add_date = QPushButton("\U0001F4C5  Date")
        self.btn_add_time = QPushButton("\u23F1  Time")
        self.btn_add_textfile = QPushButton("\U0001F4C4  Text File")
        self.btn_delete = QPushButton("\u2715  Delete")
        self.btn_delete.setObjectName("danger")
        for b in (self.btn_add_text, self.btn_add_serial, self.btn_add_logo,
                  self.btn_add_date, self.btn_add_time, self.btn_add_textfile,
                  self.btn_delete):
            toolbar.addWidget(b)
        toolbar.addStretch()
        self.btn_show_output = QPushButton("\u25B6  Show Live Output Window")
        self.btn_show_output.setObjectName("accent")
        toolbar.addWidget(self.btn_show_output)
        left.addLayout(toolbar)

        self.canvas = EditorCanvas()
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left.addWidget(self.canvas, 1)

        hint = QLabel("Click a field to select \u2022 drag to reposition \u2022 edit properties on the right")
        hint.setObjectName("subtle")
        left.addWidget(hint)

        root.addLayout(left, 3)

        # Right: properties panel (scrollable)
        self.prop_panel = self._build_properties()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(320)
        scroll.setWidget(self.prop_panel)
        root.addWidget(scroll)

        # Wire up
        self.btn_add_text.clicked.connect(lambda: self._add_field(TYPE_STATIC))
        self.btn_add_serial.clicked.connect(lambda: self._add_field(TYPE_SERIAL))
        self.btn_add_logo.clicked.connect(self._add_logo)
        self.btn_add_date.clicked.connect(lambda: self._add_field(TYPE_DATE))
        self.btn_add_time.clicked.connect(lambda: self._add_field(TYPE_TIME))
        self.btn_add_textfile.clicked.connect(lambda: self._add_field(TYPE_TEXTFILE))
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_show_output.clicked.connect(self.main.toggle_overlay_window)

        self.canvas.field_selected.connect(self._on_select)
        self.canvas.field_moved.connect(self._on_moved)

        self._set_enabled(False)

    def _build_properties(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(4, 4, 4, 4)

        title = QLabel("Field Properties")
        title.setObjectName("heading")
        lay.addWidget(title)

        box = QGroupBox("General")
        form = QFormLayout(box)
        self.in_name = QLineEdit()
        self.in_type = QLabel("-")
        self.in_label = QLineEdit()
        self.in_label_pos = QComboBox(); self.in_label_pos.addItems(LABEL_POSITIONS)
        self.in_value = QLineEdit()
        self.in_visible = QCheckBox("Visible")
        form.addRow("Name", self.in_name)
        form.addRow("Type", self.in_type)
        form.addRow("Label", self.in_label)
        form.addRow("Label Pos", self.in_label_pos)
        self.lbl_value_row = QLabel("Value")
        form.addRow(self.lbl_value_row, self.in_value)
        form.addRow("", self.in_visible)
        lay.addWidget(box)

        # Serial-specific
        self.box_serial = QGroupBox("Live Data")
        sform = QFormLayout(self.box_serial)
        self.in_serial_field = QComboBox(); self.in_serial_field.addItems(SERIAL_FIELDS)
        self.in_format = QLineEdit()
        sform.addRow("Maps To", self.in_serial_field)
        sform.addRow("Number Fmt", self.in_format)
        lay.addWidget(self.box_serial)

        # Image-specific
        self.box_image = QGroupBox("Image")
        iform = QFormLayout(self.box_image)
        self.in_image_path = QLineEdit()
        self.btn_browse_img = QPushButton("Browse\u2026")
        self.in_img_w = QSpinBox(); self.in_img_w.setRange(1, 4000)
        self.in_img_h = QSpinBox(); self.in_img_h.setRange(1, 4000)
        img_path_row = QHBoxLayout()
        pw = QWidget(); pw.setLayout(img_path_row)
        img_path_row.setContentsMargins(0, 0, 0, 0)
        img_path_row.addWidget(self.in_image_path)
        img_path_row.addWidget(self.btn_browse_img)
        iform.addRow("File", pw)
        iform.addRow("Width", self.in_img_w)
        iform.addRow("Height", self.in_img_h)
        lay.addWidget(self.box_image)

        # Font / colour
        self.box_font = QGroupBox("Font & Color")
        fform = QFormLayout(self.box_font)
        self.in_font = QComboBox(); self.in_font.addItems(FONT_CHOICES)
        self.in_font_size = QSpinBox(); self.in_font_size.setRange(6, 200)
        self.in_bold = QCheckBox("Bold")
        self.in_color = ColorButton([255, 255, 0])
        self.in_label_size = QSpinBox(); self.in_label_size.setRange(6, 200)
        self.in_label_color = ColorButton([255, 255, 255])
        fform.addRow("Font", self.in_font)
        fform.addRow("Size", self.in_font_size)
        fform.addRow("", self.in_bold)
        fform.addRow("Value Color", self.in_color)
        fform.addRow("Label Size", self.in_label_size)
        fform.addRow("Label Color", self.in_label_color)
        lay.addWidget(self.box_font)

        # Background
        self.box_bg = QGroupBox("Background")
        bform = QFormLayout(self.box_bg)
        self.in_bg_enabled = QCheckBox("Enabled")
        self.in_bg_color = ColorButton([0, 0, 0])
        bform.addRow("", self.in_bg_enabled)
        bform.addRow("Color", self.in_bg_color)
        lay.addWidget(self.box_bg)

        # Position
        self.box_pos = QGroupBox("Position (design px)")
        pform = QFormLayout(self.box_pos)
        self.in_x = QSpinBox(); self.in_x.setRange(0, 4000)
        self.in_y = QSpinBox(); self.in_y.setRange(0, 4000)
        pform.addRow("X", self.in_x)
        pform.addRow("Y", self.in_y)
        lay.addWidget(self.box_pos)

        lay.addStretch()

        # Connect edits
        self.in_name.editingFinished.connect(self._apply)
        self.in_label.editingFinished.connect(self._apply)
        self.in_value.editingFinished.connect(self._apply)
        self.in_label_pos.currentIndexChanged.connect(self._apply)
        self.in_visible.stateChanged.connect(self._apply)
        self.in_serial_field.currentIndexChanged.connect(self._apply)
        self.in_format.editingFinished.connect(self._apply)
        self.in_image_path.editingFinished.connect(self._apply)
        self.btn_browse_img.clicked.connect(self._browse_image)
        self.in_img_w.valueChanged.connect(self._apply)
        self.in_img_h.valueChanged.connect(self._apply)
        self.in_font.currentIndexChanged.connect(self._apply)
        self.in_font_size.valueChanged.connect(self._apply)
        self.in_bold.stateChanged.connect(self._apply)
        self.in_color.color_changed.connect(lambda _: self._apply())
        self.in_label_size.valueChanged.connect(self._apply)
        self.in_label_color.color_changed.connect(lambda _: self._apply())
        self.in_bg_enabled.stateChanged.connect(self._apply)
        self.in_bg_color.color_changed.connect(lambda _: self._apply())
        self.in_x.valueChanged.connect(self._apply)
        self.in_y.valueChanged.connect(self._apply)

        return panel

    # ------------------------------------------------------------------
    @property
    def profile(self):
        return self.main.profile

    def refresh(self):
        """Reload canvas from the current profile."""
        w, h = self.profile.resolution
        self.canvas.set_design_size(w, h)
        self.canvas.set_fields(self.profile.fields)
        self.canvas.set_serial_values(self.main.serial_values)

    def set_serial_values(self, values):
        self.canvas.set_serial_values(values)

    # ------------------------------------------------------------------
    def _add_field(self, ftype: str):
        count = len(self.profile.fields) + 1
        names = {TYPE_STATIC: "Text", TYPE_SERIAL: "Live", TYPE_DATE: "Date",
                 TYPE_TIME: "Time", TYPE_TEXTFILE: "TextFile"}
        f = Field(name=f"{names.get(ftype, 'Field')}{count}", type=ftype,
                  x=200, y=200)
        if ftype == TYPE_STATIC:
            f.value = "New Text"
            f.label = ""
            f.label_position = LABEL_NONE
        elif ftype == TYPE_SERIAL:
            f.serial_field = "DEPTH"
            f.label = "Depth"
            f.value = "#0.00"
            f.format_string = "#0.00"
        elif ftype == TYPE_DATE:
            f.label = "Date:"
        elif ftype == TYPE_TIME:
            f.label = "Time:"
        elif ftype == TYPE_TEXTFILE:
            f.label = ""
            f.label_position = LABEL_NONE
        self.profile.fields.append(f)
        self.main.on_fields_changed()
        self.canvas.select_field(f)

    def _add_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if not path:
            return
        import os
        from ..paths import logos_dir
        import shutil
        dest = os.path.join(logos_dir(), os.path.basename(path))
        try:
            if os.path.abspath(path) != os.path.abspath(dest):
                shutil.copy2(path, dest)
        except Exception:
            dest = path
        f = Field(name=f"Logo{len(self.profile.fields)+1}", type=TYPE_IMAGE,
                  image_path=os.path.basename(dest), x=100, y=40,
                  width=200, height=90, label="Logo")
        self.profile.fields.append(f)
        self.main.on_fields_changed()
        self.canvas.select_field(f)

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            import os, shutil
            from ..paths import logos_dir
            dest = os.path.join(logos_dir(), os.path.basename(path))
            try:
                if os.path.abspath(path) != os.path.abspath(dest):
                    shutil.copy2(path, dest)
            except Exception:
                dest = path
            self.in_image_path.setText(os.path.basename(dest))
            self._apply()

    def _delete_selected(self):
        f = self.canvas.selected
        if f and f in self.profile.fields:
            self.profile.fields.remove(f)
            self.canvas.select_field(None)
            self.main.on_fields_changed()

    # ------------------------------------------------------------------
    def _on_select(self, f: Optional[Field]):
        self._load_field(f)

    def _on_moved(self, f: Field):
        if f is self._current():
            self._loading = True
            self.in_x.setValue(int(f.x))
            self.in_y.setValue(int(f.y))
            self._loading = False
        self.main.sync_overlay()

    _current_field: Optional[Field] = None

    def _current(self):
        return self._current_field

    def _set_enabled(self, on: bool):
        self.prop_panel.setEnabled(on)

    def _load_field(self, f: Optional[Field]):
        self._current_field = f
        if f is None:
            self._set_enabled(False)
            return
        self._set_enabled(True)
        self._loading = True
        self.in_name.setText(f.name)
        self.in_type.setText(f.type)
        self.in_label.setText(f.label)
        self.in_label_pos.setCurrentText(f.label_position)
        self.in_value.setText(f.value)
        self.in_visible.setChecked(f.visible)
        self.in_serial_field.setCurrentText(f.serial_field or "DEPTH")
        self.in_format.setText(f.format_string)
        self.in_image_path.setText(f.image_path)
        self.in_img_w.setValue(int(f.width))
        self.in_img_h.setValue(int(f.height))
        self.in_font.setCurrentText(f.font_name)
        self.in_font_size.setValue(int(f.font_size))
        self.in_bold.setChecked(f.bold)
        self.in_color.set_color(f.font_color)
        self.in_label_size.setValue(int(f.label_font_size))
        self.in_label_color.set_color(f.label_color)
        self.in_bg_enabled.setChecked(f.bg_enabled)
        self.in_bg_color.set_color(f.bg_color)
        self.in_x.setValue(int(f.x))
        self.in_y.setValue(int(f.y))

        # Toggle type-specific boxes
        is_serial = f.type == TYPE_SERIAL
        is_image = f.type == TYPE_IMAGE
        self.box_serial.setVisible(is_serial)
        self.box_image.setVisible(is_image)
        self.box_font.setVisible(not is_image)
        self.box_bg.setVisible(not is_image)
        if f.type in (TYPE_DATE, TYPE_TIME):
            self.lbl_value_row.setText("Value (auto)")
            self.in_value.setEnabled(False)
        elif f.type == TYPE_TEXTFILE:
            self.lbl_value_row.setText("File Path")
            self.in_value.setEnabled(True)
        else:
            self.lbl_value_row.setText("Value")
            self.in_value.setEnabled(True)
        self._loading = False

    def _apply(self):
        if self._loading:
            return
        f = self._current()
        if f is None:
            return
        f.name = self.in_name.text()
        f.label = self.in_label.text()
        f.label_position = self.in_label_pos.currentText()
        if self.in_value.isEnabled():
            f.value = self.in_value.text()
        f.visible = self.in_visible.isChecked()
        f.serial_field = self.in_serial_field.currentText()
        f.format_string = self.in_format.text()
        f.image_path = self.in_image_path.text()
        f.width = self.in_img_w.value()
        f.height = self.in_img_h.value()
        f.font_name = self.in_font.currentText()
        f.font_size = self.in_font_size.value()
        f.bold = self.in_bold.isChecked()
        f.font_color = self.in_color.color()
        f.label_font_size = self.in_label_size.value()
        f.label_color = self.in_label_color.color()
        f.bg_enabled = self.in_bg_enabled.isChecked()
        f.bg_color = self.in_bg_color.color()
        f.x = self.in_x.value()
        f.y = self.in_y.value()
        from .. import render
        render.clear_pixmap_cache()
        self.canvas.update()
        self.main.sync_overlay()
