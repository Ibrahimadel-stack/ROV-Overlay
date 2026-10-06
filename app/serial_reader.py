"""Serial port reading and configurable string parsing."""
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

try:
    import serial
    import serial.tools.list_ports as list_ports
    HAVE_SERIAL = True
except Exception:  # pragma: no cover - pyserial always expected
    HAVE_SERIAL = False

from .models import SerialStringFormat


def available_ports() -> List[str]:
    """Return a list of available serial port device names."""
    if not HAVE_SERIAL:
        return []
    try:
        return [p.device for p in list_ports.comports()]
    except Exception:
        return []


def parse_line(line: str, fmt: SerialStringFormat) -> Optional[Dict[str, str]]:
    """Parse one raw serial line using a SerialStringFormat rule.

    Returns a dict mapping serial field names (EAST, NORTH, ...) to their raw
    string values, or None if the line does not match the prefix.
    """
    line = line.strip()
    if not line:
        return None
    prefix = (fmt.prefix or "").strip()
    delim = fmt.delimiter or ","
    if prefix and not line.startswith(prefix):
        return None

    parts = line.split(delim)
    result: Dict[str, str] = {}
    for idx, mapped in enumerate(fmt.field_map):
        if mapped in ("IGNORE", "PREFIX", ""):
            continue
        if idx < len(parts):
            result[mapped] = parts[idx].strip()
    return result


def parse_with_formats(line: str, formats: List[SerialStringFormat]) -> Optional[Dict[str, str]]:
    """Try each configured format rule until one matches."""
    for fmt in formats:
        res = parse_line(line, fmt)
        if res is not None:
            return res
    return None


class SerialReader(QThread):
    """Background thread that reads lines from a serial port and emits them."""

    line_received = pyqtSignal(str)                 # raw line
    data_parsed = pyqtSignal(dict)                  # {field: value}
    connection_changed = pyqtSignal(bool, str)      # connected, message

    def __init__(self, port: str, baud: int, formats: List[SerialStringFormat]):
        super().__init__()
        self.port = port
        self.baud = baud
        self.formats = formats
        self._running = False
        self._serial = None

    def update_formats(self, formats: List[SerialStringFormat]) -> None:
        self.formats = formats

    def run(self) -> None:
        if not HAVE_SERIAL:
            self.connection_changed.emit(False, "pyserial not available")
            return
        try:
            self._serial = serial.Serial(self.port, self.baud, timeout=1)
        except Exception as exc:
            self.connection_changed.emit(False, f"Could not open {self.port}: {exc}")
            return

        self._running = True
        self.connection_changed.emit(True, f"Connected to {self.port} @ {self.baud}")
        buffer = ""
        while self._running:
            try:
                data = self._serial.read(256)
                if data:
                    buffer += data.decode("latin-1", errors="replace")
                    while "\n" in buffer or "\r" in buffer:
                        # split on first line terminator
                        for term in ("\r\n", "\n", "\r"):
                            if term in buffer:
                                line, buffer = buffer.split(term, 1)
                                break
                        else:
                            break
                        if line.strip():
                            self.line_received.emit(line)
                            parsed = parse_with_formats(line, self.formats)
                            if parsed:
                                self.data_parsed.emit(parsed)
            except Exception as exc:
                self.connection_changed.emit(False, f"Serial error: {exc}")
                break

        try:
            if self._serial:
                self._serial.close()
        except Exception:
            pass
        self.connection_changed.emit(False, "Disconnected")

    def stop(self) -> None:
        self._running = False
        self.wait(1500)
