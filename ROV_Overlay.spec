# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ROV Video Overlay.

Bundles the logo images, sample profiles and the application icon as data
files so they are available both in dev and in the frozen build.

Build (on the TARGET OS - run on Windows to get a Windows .exe):
    pyinstaller ROV_Overlay.spec
Output: dist/ROV_Overlay/ROV_Overlay(.exe)
"""
import os

block_cipher = None
ROOT = os.path.abspath(os.getcwd())

datas = [
    (os.path.join('resources', 'logos'), os.path.join('resources', 'logos')),
    (os.path.join('resources', 'profiles'), os.path.join('resources', 'profiles')),
    (os.path.join('resources', 'icon.ico'), 'resources'),
]

a = Analysis(
    ['main.py'],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'serial', 'serial.tools', 'serial.tools.list_ports',
        'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'PySide6', 'PyQt5'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ROV_Overlay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.join('resources', 'icon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ROV_Overlay',
)
