"""Live video capture worker for the overlay background (SDI capture card).

Reads frames from a capture device with OpenCV in a background QThread and
emits each frame as a QImage. On Windows the DirectShow backend is used with a
1-frame buffer to keep latency to a minimum, so the ROV pilot sees the live
feed with the overlay data composited on top in near real time.
"""
from __future__ import annotations

import sys
from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

try:
    import cv2
    HAVE_CV2 = True
except Exception:  # pragma: no cover - opencv optional at runtime
    HAVE_CV2 = False


def _open_capture(index: int):
    """Open a VideoCapture using the lowest-latency backend for the platform."""
    if not HAVE_CV2:
        return None
    if sys.platform.startswith("win"):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(index)
    if cap is not None and cap.isOpened():
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # minimise buffer delay
        except Exception:
            pass
    return cap


def detect_devices(max_index: int = 5) -> List[dict]:
    """Probe device indices 0..max_index and return the ones that open.

    Each entry: {"index": int, "width": int, "height": int}.
    """
    found: List[dict] = []
    if not HAVE_CV2:
        return found
    for idx in range(max_index + 1):
        cap = _open_capture(idx)
        try:
            if cap is not None and cap.isOpened():
                ok, frame = cap.read()
                if ok and frame is not None:
                    h, w = frame.shape[:2]
                    found.append({"index": idx, "width": int(w), "height": int(h)})
        finally:
            if cap is not None:
                cap.release()
    return found


class VideoCaptureThread(QThread):
    """Background capture thread that emits QImage frames."""

    frame_ready = pyqtSignal(object)        # QImage, or None on failure/disconnect
    status_changed = pyqtSignal(bool, str)  # opened, message

    def __init__(self, device_index: int = 0):
        super().__init__()
        self.device_index = device_index
        self._running = False
        self._cap = None

    def run(self) -> None:
        if not HAVE_CV2:
            self.status_changed.emit(False, "opencv (cv2) not available")
            self.frame_ready.emit(None)
            return

        self._cap = _open_capture(self.device_index)
        if self._cap is None or not self._cap.isOpened():
            self.status_changed.emit(
                False, f"Could not open video device {self.device_index}")
            self.frame_ready.emit(None)  # fall back to black
            return

        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        self.status_changed.emit(
            True, f"Video device {self.device_index} open ({w}x{h})")

        self._running = True
        fail_count = 0
        while self._running:
            try:
                ok, frame = self._cap.read()
            except Exception as exc:
                self.status_changed.emit(False, f"Capture error: {exc}")
                self.frame_ready.emit(None)
                break

            if not ok or frame is None:
                fail_count += 1
                if fail_count >= 15:
                    # Treat as disconnect -> black background
                    self.status_changed.emit(
                        False, f"Device {self.device_index} disconnected")
                    self.frame_ready.emit(None)
                    break
                self.msleep(10)
                continue
            fail_count = 0

            # Convert the BGR numpy frame to a QImage. Copy so the buffer stays
            # valid after the numpy array is garbage-collected.
            fh, fw = frame.shape[:2]
            if frame.ndim == 3 and frame.shape[2] == 3:
                bytes_per_line = 3 * fw
                image = QImage(frame.data, fw, fh, bytes_per_line,
                               QImage.Format.Format_BGR888).copy()
            else:
                # grayscale or other: let Qt handle as grayscale
                bytes_per_line = fw
                image = QImage(frame.data, fw, fh, bytes_per_line,
                               QImage.Format.Format_Grayscale8).copy()

            self.frame_ready.emit(image)
            # Yield briefly; capture is bounded by the device frame rate anyway.
            self.msleep(1)

        try:
            if self._cap is not None:
                self._cap.release()
        except Exception:
            pass
        self._cap = None

    def stop(self) -> None:
        self._running = False
        self.wait(1500)
