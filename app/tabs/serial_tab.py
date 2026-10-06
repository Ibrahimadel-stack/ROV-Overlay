"""Serial Settings tab: port/baud, configurable string parser, live monitor."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QLineEdit,
    QComboBox, QGroupBox, QFormLayout, QTableWidget, QTableWidgetItem,
    QPlainTextEdit, QHeaderView, QMessageBox,
)

from ..models import SERIAL_FIELDS, SerialStringFormat
from ..serial_reader import available_ports, SerialReader, parse_line

BAUD_RATES = ["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"]
MAP_CHOICES = ["IGNORE", "PREFIX"] + SERIAL_FIELDS


class SerialTab(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self._build()
        self.refresh_ports()
        self.load_from_profile()

    def _build(self):
        root = QVBoxLayout(self)

        # Connection row
        conn = QGroupBox("Connection")
        cg = QHBoxLayout(conn)
        cg.addWidget(QLabel("COM Port"))
        self.cmb_port = QComboBox(); self.cmb_port.setMinimumWidth(140); self.cmb_port.setEditable(True)
        cg.addWidget(self.cmb_port)
        self.btn_refresh = QPushButton("\u21BB Refresh")
        cg.addWidget(self.btn_refresh)
        cg.addWidget(QLabel("Baud"))
        self.cmb_baud = QComboBox(); self.cmb_baud.addItems(BAUD_RATES); self.cmb_baud.setCurrentText("9600")
        cg.addWidget(self.cmb_baud)
        self.btn_connect = QPushButton("\u25B6 Connect"); self.btn_connect.setObjectName("accent")
        cg.addWidget(self.btn_connect)
        self.lbl_status = QLabel("\u25CF Disconnected"); self.lbl_status.setObjectName("status_disconnected")
        cg.addWidget(self.lbl_status)
        cg.addStretch()
        root.addWidget(conn)

        mid = QHBoxLayout()

        # String format editor
        fmt_box = QGroupBox("Serial String Format")
        fv = QVBoxLayout(fmt_box)
        frow = QHBoxLayout()
        frow.addWidget(QLabel("Prefix"))
        self.in_prefix = QLineEdit("$NAV"); self.in_prefix.setMaximumWidth(90)
        frow.addWidget(self.in_prefix)
        frow.addWidget(QLabel("Delimiter"))
        self.in_delim = QLineEdit(","); self.in_delim.setMaximumWidth(50)
        frow.addWidget(self.in_delim)
        frow.addStretch()
        fv.addLayout(frow)

        fv.addWidget(QLabel("Format string (comma-separated field names):", objectName="subtle"))
        self.in_format = QLineEdit("$NAV,EAST,NORTH,HEADING,DEPTH,ALTITUDE,KP,CP")
        fv.addWidget(self.in_format)
        self.btn_parse_format = QPushButton("\u2699 Build Mapping Table From Format")
        fv.addWidget(self.btn_parse_format)

        fv.addWidget(QLabel("Position mapping (edit which position maps to which field):",
                            objectName="subtle"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Position", "Token", "Maps To"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        fv.addWidget(self.table, 1)

        trow = QHBoxLayout()
        self.btn_add_row = QPushButton("\u2795 Row")
        self.btn_del_row = QPushButton("\u2715 Row")
        self.btn_apply_map = QPushButton("\u2714 Apply Mapping"); self.btn_apply_map.setObjectName("accent")
        trow.addWidget(self.btn_add_row); trow.addWidget(self.btn_del_row)
        trow.addStretch(); trow.addWidget(self.btn_apply_map)
        fv.addLayout(trow)
        mid.addWidget(fmt_box, 2)

        # Test + monitor
        right = QVBoxLayout()
        test_box = QGroupBox("Test Parser")
        tv = QVBoxLayout(test_box)
        tv.addWidget(QLabel("Paste a sample line:", objectName="subtle"))
        self.in_test = QLineEdit("$NAV,512345.67,2812345.89,180.5,52.30,2.10,1.234,-0.850")
        tv.addWidget(self.in_test)
        self.btn_test = QPushButton("\u25B6 Parse Sample")
        tv.addWidget(self.btn_test)
        self.out_test = QPlainTextEdit(); self.out_test.setReadOnly(True); self.out_test.setMaximumHeight(160)
        tv.addWidget(self.out_test)
        right.addWidget(test_box)

        mon_box = QGroupBox("Live Serial Monitor")
        mv = QVBoxLayout(mon_box)
        self.monitor = QPlainTextEdit(); self.monitor.setReadOnly(True)
        self.monitor.setStyleSheet("font-family:Consolas,monospace; font-size:11px;")
        mv.addWidget(self.monitor)
        self.btn_clear_mon = QPushButton("Clear")
        mv.addWidget(self.btn_clear_mon)
        right.addWidget(mon_box, 1)
        mid.addLayout(right, 2)

        root.addLayout(mid, 1)

        # Wire
        self.btn_refresh.clicked.connect(self.refresh_ports)
        self.btn_connect.clicked.connect(self.toggle_connect)
        self.btn_parse_format.clicked.connect(self.build_table_from_format)
        self.btn_add_row.clicked.connect(self.add_row)
        self.btn_del_row.clicked.connect(self.del_row)
        self.btn_apply_map.clicked.connect(self.apply_mapping)
        self.btn_test.clicked.connect(self.test_parse)
        self.btn_clear_mon.clicked.connect(lambda: self.monitor.clear())
        for w in (self.in_prefix, self.in_delim):
            w.editingFinished.connect(self.apply_mapping)

    # ------------------------------------------------------------------
    @property
    def profile(self):
        return self.main.profile

    def _fmt(self) -> SerialStringFormat:
        if not self.profile.serial.formats:
            self.profile.serial.formats.append(SerialStringFormat())
        return self.profile.serial.formats[0]

    def refresh_ports(self):
        current = self.cmb_port.currentText()
        self.cmb_port.clear()
        ports = available_ports()
        if not ports:
            # still allow manual entry of COM names
            ports = [f"COM{i}" for i in range(1, 9)]
        self.cmb_port.addItems(ports)
        if current:
            self.cmb_port.setCurrentText(current)

    def load_from_profile(self):
        p = self.profile
        if p.serial.port:
            self.cmb_port.setCurrentText(p.serial.port)
        self.cmb_baud.setCurrentText(str(p.serial.baud))
        fmt = self._fmt()
        self.in_prefix.setText(fmt.prefix)
        self.in_delim.setText(fmt.delimiter)
        if fmt.raw_format:
            self.in_format.setText(fmt.raw_format)
        elif fmt.field_map:
            self.in_format.setText(fmt.delimiter.join(
                [fmt.prefix] + [m for m in fmt.field_map[1:]]))
        self.populate_table(fmt.field_map)

    def populate_table(self, field_map):
        self.table.setRowCount(0)
        for i, mapped in enumerate(field_map):
            self.add_row(position=i, mapped=mapped)

    def add_row(self, position=None, mapped="IGNORE"):
        r = self.table.rowCount()
        if position is None:
            position = r
        self.table.insertRow(r)
        pos_item = QTableWidgetItem(str(position))
        pos_item.setFlags(pos_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(r, 0, pos_item)
        self.table.setItem(r, 1, QTableWidgetItem(""))
        cmb = QComboBox(); cmb.addItems(MAP_CHOICES)
        if mapped in MAP_CHOICES:
            cmb.setCurrentText(mapped)
        self.table.setCellWidget(r, 2, cmb)

    def del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)
            self._renumber()

    def _renumber(self):
        for r in range(self.table.rowCount()):
            self.table.item(r, 0).setText(str(r))

    def build_table_from_format(self):
        text = self.in_format.text().strip()
        delim = self.in_delim.text() or ","
        tokens = text.split(delim)
        self.table.setRowCount(0)
        for i, tok in enumerate(tokens):
            tok = tok.strip()
            # Strip optional {BRACES}
            clean = tok.strip("{}").upper()
            if i == 0:
                mapped = "PREFIX"
            elif clean in SERIAL_FIELDS:
                mapped = clean
            else:
                # common aliases
                alias = {"ALT": "ALTITUDE", "HDG": "HEADING", "HEAD": "HEADING"}
                mapped = alias.get(clean, "IGNORE")
            self.add_row(position=i, mapped=mapped)
            self.table.item(i, 1).setText(tok)
        # auto-set prefix
        if tokens:
            self.in_prefix.setText(tokens[0].strip())

    def _collect_field_map(self):
        fm = []
        for r in range(self.table.rowCount()):
            cmb = self.table.cellWidget(r, 2)
            fm.append(cmb.currentText() if cmb else "IGNORE")
        return fm

    def apply_mapping(self):
        fmt = self._fmt()
        fmt.prefix = self.in_prefix.text().strip()
        fmt.delimiter = self.in_delim.text() or ","
        fmt.field_map = self._collect_field_map()
        fmt.raw_format = self.in_format.text().strip()
        self.profile.serial.port = self.cmb_port.currentText().strip()
        try:
            self.profile.serial.baud = int(self.cmb_baud.currentText())
        except ValueError:
            self.profile.serial.baud = 9600
        if self.main.serial_reader:
            self.main.serial_reader.update_formats(self.profile.serial.formats)

    def test_parse(self):
        self.apply_mapping()
        fmt = self._fmt()
        line = self.in_test.text()
        result = parse_line(line, fmt)
        if result is None:
            self.out_test.setPlainText(
                f"Line does NOT match prefix '{fmt.prefix}'.\n"
                "No values parsed.")
            return
        lines = ["Parsed values:"]
        for k in SERIAL_FIELDS:
            if k in result:
                lines.append(f"  {k:10s} = {result[k]}")
        extra = [k for k in result if k not in SERIAL_FIELDS]
        for k in extra:
            lines.append(f"  {k:10s} = {result[k]}")
        self.out_test.setPlainText("\n".join(lines))

    # ------------------------------------------------------------------
    def toggle_connect(self):
        if self.main.serial_reader and self.main.serial_reader.isRunning():
            self.main.stop_serial()
        else:
            self.apply_mapping()
            port = self.cmb_port.currentText().strip()
            try:
                baud = int(self.cmb_baud.currentText())
            except ValueError:
                baud = 9600
            if not port:
                QMessageBox.warning(self, "No port", "Select a COM port first.")
                return
            self.main.start_serial(port, baud, self.profile.serial.formats)

    def set_status(self, connected: bool, message: str):
        if connected:
            self.lbl_status.setText("\u25CF Connected")
            self.lbl_status.setObjectName("status_connected")
            self.btn_connect.setText("\u25A0 Disconnect")
        else:
            self.lbl_status.setText("\u25CF Disconnected")
            self.lbl_status.setObjectName("status_disconnected")
            self.btn_connect.setText("\u25B6 Connect")
        # re-apply stylesheet for objectName change
        self.lbl_status.style().unpolish(self.lbl_status)
        self.lbl_status.style().polish(self.lbl_status)
        if message:
            self.append_monitor(f"[{message}]")

    def append_monitor(self, text: str):
        self.monitor.appendPlainText(text)
        # cap lines
        doc = self.monitor.document()
        if doc.blockCount() > 300:
            cursor = self.monitor.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
