"""Smoke test for the video-background feature (offscreen, synthetic frame)."""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage
from PyQt6.QtCore import QTimer
from app.control_window import ControlWindow
from app.style import DARK_QSS
from app.paths import seed_logos, seed_profiles, profiles_dir
from app.models import Profile

seed_logos(); seed_profiles()
app = QApplication(sys.argv)
app.setStyleSheet(DARK_QSS)

pf = os.path.join(profiles_dir(), "BP GVI.json")
prof = Profile.load(pf) if os.path.exists(pf) else Profile()
win = ControlWindow(prof)
win.show()
win.overlay.show()

win.serial_values.update({"EAST": "512345.67", "NORTH": "2812345.89",
                          "DEPTH": "52.30", "HEADING": "182.4"})
win.sync_overlay()

errors = []

def run():
    try:
        # Simulate a captured BGR frame (gradient) and push it to the overlay
        h, w = 576, 720
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:, :, 0] = np.linspace(0, 255, w, dtype=np.uint8)   # B gradient
        frame[:, :, 2] = 80                                       # R tint
        img = QImage(frame.data, w, h, 3 * w, QImage.Format.Format_BGR888).copy()
        win.overlay._on_frame(img)
        app.processEvents()
        win.overlay.grab().save("/home/ubuntu/ROV_Overlay/shot_video_overlay.png")

        # Verify the video bar exists and 'None (Black)' fallback works
        assert hasattr(win, "cmb_video"), "video combo missing"
        assert win.cmb_video.count() >= 1
        win.overlay._on_frame(None)   # disconnect -> black
        app.processEvents()
        assert win.overlay.current_frame is None
        win.overlay.grab().save("/home/ubuntu/ROV_Overlay/shot_video_black.png")

        # Exercise apply with None (black) and a device index (will fail-open)
        win.cmb_video.setCurrentIndex(0)  # None (Black)
        win._apply_video()
        app.processEvents()
        print("video_device after None:", win.overlay.video_device)
        print("OK: video path exercised")
    except Exception as e:
        import traceback; traceback.print_exc(); errors.append(str(e))
    win.overlay.stop_video()
    app.quit()

QTimer.singleShot(800, run)
rc = app.exec()
print("EXIT", rc, "ERRORS", errors)
sys.exit(1 if errors else 0)
