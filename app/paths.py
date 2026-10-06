"""Resource / data path resolution (works both in dev and PyInstaller build)."""
from __future__ import annotations

import os
import sys


def app_base_dir() -> str:
    """Directory where the executable / main script lives.

    Used for *writable* data (profiles, user logos) that should sit next to
    the .exe so the user can manage them.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_dir() -> str:
    """Directory of *bundled read-only* resources.

    PyInstaller unpacks data files to sys._MEIPASS.
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", app_base_dir())
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def logos_dir() -> str:
    """Writable logos folder next to the executable.

    Seeded from bundled resources on first run.
    """
    d = os.path.join(app_base_dir(), "Logos")
    os.makedirs(d, exist_ok=True)
    return d


def bundled_logos_dir() -> str:
    return os.path.join(resource_dir(), "resources", "logos")


def profiles_dir() -> str:
    d = os.path.join(app_base_dir(), "Profiles")
    os.makedirs(d, exist_ok=True)
    return d


def resolve_logo(name_or_path: str) -> str:
    """Resolve a logo reference (filename or absolute path) to an existing file."""
    if not name_or_path:
        return ""
    # Absolute and exists
    if os.path.isabs(name_or_path) and os.path.exists(name_or_path):
        return name_or_path
    base = os.path.basename(name_or_path.replace("\\", "/"))
    # user logos folder first, then bundled
    for folder in (logos_dir(), bundled_logos_dir()):
        candidate = os.path.join(folder, base)
        if os.path.exists(candidate):
            return candidate
    # case-insensitive match in logos dir
    for folder in (logos_dir(), bundled_logos_dir()):
        if os.path.isdir(folder):
            for fn in os.listdir(folder):
                if fn.lower() == base.lower():
                    return os.path.join(folder, fn)
    return name_or_path


def bundled_profiles_dir() -> str:
    return os.path.join(resource_dir(), "resources", "profiles")


def seed_profiles() -> None:
    """Copy bundled sample profiles into the writable Profiles folder once."""
    import shutil
    src = bundled_profiles_dir()
    dst = profiles_dir()
    if not os.path.isdir(src):
        return
    for fn in os.listdir(src):
        s = os.path.join(src, fn)
        d = os.path.join(dst, fn)
        if os.path.isfile(s) and not os.path.exists(d):
            try:
                shutil.copy2(s, d)
            except Exception:
                pass


def seed_logos() -> None:
    """Copy bundled logos into the writable Logos folder on first run."""
    import shutil
    src = bundled_logos_dir()
    dst = logos_dir()
    if not os.path.isdir(src):
        return
    for fn in os.listdir(src):
        s = os.path.join(src, fn)
        d = os.path.join(dst, fn)
        if os.path.isfile(s) and not os.path.exists(d):
            try:
                shutil.copy2(s, d)
            except Exception:
                pass
