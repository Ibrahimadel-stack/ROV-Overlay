"""ROV Video Overlay - application entry point.

A modern replacement for the legacy VB overlay tool. Renders a black-background
overlay (captured by OBS / fed to a hardware compositor) driven by live serial
navigation data, with a dark-themed control UI for full configuration.
"""
import os
import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from app.control_window import ControlWindow
from app.style import DARK_QSS
from app.paths import seed_logos, seed_profiles, profiles_dir, resource_dir
from app.models import Profile


def _load_startup_profile() -> Profile:
    """Load the last-used / first available profile, else a blank one."""
    try:
        d = profiles_dir()
        files = sorted(f for f in os.listdir(d) if f.lower().endswith(".json"))
        if files:
            return Profile.load(os.path.join(d, files[0]))
    except Exception:
        pass
    return Profile()


def main():
    # Seed bundled logos into the writable Logos folder on first run.
    try:
        seed_logos()
        seed_profiles()
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("ROV Video Overlay")
    app.setStyleSheet(DARK_QSS)

    icon_path = os.path.join(resource_dir(), "resources", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    profile = _load_startup_profile()
    win = ControlWindow(profile)
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
