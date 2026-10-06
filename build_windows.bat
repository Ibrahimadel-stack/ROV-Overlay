@echo off
REM ============================================================
REM  ROV Video Overlay - Windows build script
REM  Run this on a Windows 10/11 PC with Python 3.9+ installed.
REM  It produces dist\ROV_Overlay\ROV_Overlay.exe
REM ============================================================

echo.
echo === Creating / using virtual environment ===
python -m venv .venv
call .venv\Scripts\activate.bat

echo.
echo === Installing dependencies ===
python -m pip install --upgrade pip
pip install PyQt6 pyserial pyinstaller pillow

echo.
echo === Building the executable ===
pyinstaller --clean --noconfirm ROV_Overlay.spec

echo.
echo === Done ===
echo The application is in:  dist\ROV_Overlay\
echo Run:                    dist\ROV_Overlay\ROV_Overlay.exe
echo.
pause
