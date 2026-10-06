# ROV Video Overlay

A modern replacement for the legacy VB ROV video-overlay tool. It renders a
**pure-black overlay window** (captured by OBS, or fed to a VGA output / TV One
compositor) driven by **live serial navigation data**, and provides a
dark-themed control application for full configuration.

![overview](docs_placeholder)

---

## Features

- **Two windows**
  - *Control / Editor* — dark, modern, tabbed UI.
  - *Overlay Output* — borderless, pure-black window that OBS captures.
- **Visual Overlay Editor** — scaled live preview; click to select a field,
  drag to reposition, edit every property (label, value, font, size, colour,
  background, visibility, X/Y).
- **Field types** — static text, auto date, auto time, live serial data,
  image/logo, text-file reader.
- **Fully configurable serial parser** — set COM port, baud, prefix and
  delimiter, type the string format and map *any* comma position to any overlay
  field (EAST, NORTH, HEADING, DEPTH, ALTITUDE, KP, CP, LAT, LONG, PITCH, ROLL,
  DCC or IGNORE). Includes a live "Test Parser" and a raw serial monitor.
- **Profiles** — save / load / new / delete as JSON, plus **import & export the
  legacy `.ovl` format**. All 9 existing profiles are pre-converted and bundled.
- **Logo Manager** — logo library grid, add / remove logos, assign to
  Client / Contractor / Extra slots, reposition & resize on the canvas.
- **Overlay output controls** (right-click the overlay) — move to Monitor 1/2,
  set resolution (1280×1024, 1920×1080, 720×576, 1024×768), always-on-top.

---

## Build the Windows .exe

> **Important:** a Windows `.exe` must be built **on Windows** — PyInstaller
> does not cross-compile from Linux/Mac. Everything needed is included.

On a Windows 10/11 PC with Python 3.9+:

```bat
build_windows.bat
```

This creates a virtual environment, installs dependencies, runs PyInstaller and
produces:

```
dist\ROV_Overlay\ROV_Overlay.exe
```

Copy the whole `dist\ROV_Overlay\` folder to the overlay PC and run
`ROV_Overlay.exe`. No installation required.

Manual build (equivalent):

```bat
pip install -r requirements.txt
pyinstaller --clean --noconfirm ROV_Overlay.spec
```

### Run from source (any OS, for testing)

```bash
pip install -r requirements.txt
python main.py
```

---

## How to use

1. **Serial Settings tab** — pick the COM port & baud, enter your string format
   (e.g. `$NAV,EAST,NORTH,HEADING,DEPTH,ALT,KP,CP`), click *Build Mapping Table
   From Format*, adjust any mapping, *Apply Mapping*, then *Connect*. Use *Test
   Parser* to verify a sample line.
2. **Overlay Editor tab** — add/move/edit fields; click *Show Live Output
   Window* to open the black overlay (drag it to the second monitor / VGA out,
   or right-click it → *Move to Monitor 2*).
3. **Logo Manager tab** — add logos and assign them to slots.
4. **Profiles tab** — fill in job metadata and *Save Profile*, or
   *Import .ovl* to bring in legacy profiles.

Profiles and logos live in `Profiles\` and `Logos\` folders created next to the
executable, so they are easy to back up and edit.

---

## Project layout

```
ROV_Overlay/
├─ main.py                  entry point
├─ ROV_Overlay.spec         PyInstaller build spec
├─ build_windows.bat        one-click Windows build
├─ requirements.txt
├─ app/
│  ├─ models.py             Field / Profile data model + JSON
│  ├─ ovl_io.py             legacy .ovl import / export
│  ├─ serial_reader.py      serial thread + configurable parser
│  ├─ render.py             shared field rendering
│  ├─ overlay_window.py     black output window
│  ├─ canvas.py             interactive editor canvas
│  ├─ control_window.py     main window + state
│  ├─ style.py              dark theme
│  ├─ widgets.py            colour picker button
│  ├─ paths.py              resource/data paths (dev + frozen)
│  └─ tabs/                 editor / profiles / serial / logo tabs
└─ resources/
   ├─ logos/                bundled logos (seeded to Logos/ on first run)
   ├─ profiles/             pre-converted sample profiles
   └─ icon.ico
```

> **Note on logos:** the logo files in the original archive were empty (0 bytes),
> so clean placeholder logos (BP, Burullus, DeepTech, PhPC, ROV) were generated
> as defaults. Replace them anytime via the Logo Manager with your real artwork.
