"""Headless smoke test: build the UI, load a profile, render, screenshot, quit."""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from app.control_window import ControlWindow
from app.style import DARK_QSS
from app.paths import seed_logos, seed_profiles, profiles_dir
from app.models import Profile

seed_logos(); seed_profiles()
app = QApplication(sys.argv)
app.setStyleSheet(DARK_QSS)

# load a converted sample profile
pf = os.path.join(profiles_dir(), "BP GVI.json")
prof = Profile.load(pf) if os.path.exists(pf) else Profile()
win = ControlWindow(prof)
win.show()

# inject fake live serial values
win.serial_values.update({
    "EAST": "512345.67", "NORTH": "2812345.89", "HEADING": "182.4",
    "DEPTH": "52.30", "ALTITUDE": "2.10", "KP": "1.234", "CP": "-0.850",
})
win.sync_overlay()
win.overlay.show()

errors = []

def shoot():
    try:
        win.grab().save("/home/ubuntu/ROV_Overlay/shot_control.png")
        win.overlay.grab().save("/home/ubuntu/ROV_Overlay/shot_overlay.png")
        # exercise tabs
        for i in range(win.tabs.count()):
            win.tabs.setCurrentIndex(i)
            app.processEvents()
        win.tabs.setCurrentIndex(2)  # serial tab
        win.serial_tab.build_table_from_format()
        win.serial_tab.test_parse()
        win.tabs.setCurrentIndex(0)
        win.grab().save("/home/ubuntu/ROV_Overlay/shot_control2.png")
        print("PARSE_TEST_OUTPUT:")
        print(win.serial_tab.out_test.toPlainText())
        print("OK fields:", len(prof.fields))
    except Exception as e:
        import traceback; traceback.print_exc(); errors.append(str(e))
    app.quit()

QTimer.singleShot(1200, shoot)
rc = app.exec()
print("EXIT", rc, "ERRORS", errors)
sys.exit(1 if errors else 0)
