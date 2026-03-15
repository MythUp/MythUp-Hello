# MythUpHello

MythUpHello is a Windows face-recognition lock assistant built with Python, OpenCV, face_recognition, and PyQt6.

The app watches the camera feed, compares detected faces against known identities from the `faces/` folder, and locks the workstation when no authorized face is seen for a configurable delay.

## Features

- Face detection and recognition from webcam stream
- Configurable confidence threshold and lock delay in `config.py`
- Red/green bounding boxes in preview mode:
  - Green: authorized match
  - Red: weak match or unknown face
- Smoothed FPS display and frame-skipping optimization
- Camera auto-reconnect safety if the camera disappears
- Lock decision is deferred until camera access is restored and one verification pass completes
- Headless-by-default runtime for Windows startup use
- Optional camera preview with `--show-camera`
- PyInstaller one-file build script

## Project Structure

- `main.py`: application entry point and CLI arguments
- `gui.py`: camera loop, face rendering, lock logic, reconnection safety
- `face_engine.py`: encoding loading and face matching engine
- `config.py`: user configuration values
- `locker.py`: workstation lock helper
- `build_pyinstaller.bat`: Windows build script for PyInstaller
- `faces/`: known faces images and optional cached arrays

## Requirements

Install dependencies in your virtual environment:

```bash
pip install -r requirements.txt
```

## Configuration

Edit `config.py`:

- `LOCK_DELAY_SECONDS`: seconds before locking after no authorized face
- `MIN_CONFIDENCE_PERCENT`: minimum percent required for authorized match
- `WEAK_CONFIDENCE_PERCENT`: threshold for weak match labeling (`name?`)
- `ANALYZE_SCALE`: processing scale for recognition (`0.5` is faster)
- `RECOGNITION_EVERY_N_FRAMES`: recognition cadence
- `CAMERA_WIDTH`, `CAMERA_HEIGHT`: requested capture size

## Run

Default mode depends on build config (`show-camera` or `no-camera`).

Force preview mode:

```bash
python main.py --show-camera
```

Force hidden mode:

```bash
python main.py --no-camera
```

## Build Executable (PyInstaller)

Run:

```powershell
.\build_pyinstaller.bat
```

Build mode options:

```powershell
.\build_pyinstaller.bat external
.\build_pyinstaller.bat embedded
.\build_pyinstaller.bat both
```

Camera default options during build:

```powershell
.\build_pyinstaller.bat both show-camera
.\build_pyinstaller.bat both no-camera
```

Full syntax:

```powershell
.\build_pyinstaller.bat [external|embedded|both] [show-camera|no-camera]
```

If omitted:

- Build mode defaults to `both`
- Camera default mode defaults to `no-camera`

- `external`: faces are loaded from `faces/` and `encodings.npy` next to the executable.
- `embedded`: faces are loaded only from resources embedded in the executable.
- `both` (default): load external first, then fallback to embedded.

Output:

- `dist/MythUpHello-<mode>.exe`

Run built app:

```powershell
.\dist\MythUpHello-both.exe
```

Run built app with preview:

```powershell
.\dist\MythUpHello-both.exe --show-camera
```

Run built app without preview:

```powershell
.\dist\MythUpHello-both.exe --no-camera
```

Default (no argument) build command:

```powershell
.\build_pyinstaller.bat
```

This generates `dist/MythUpHello-both.exe`.

Default release recommendation for GitHub Actions: use `external` and publish `MythUpHello-external.exe` with a companion `faces/` folder and `encodings.npy`.

## Windows Startup

Use Task Scheduler or the Startup folder to launch:

- Headless startup:
  - `dist\MythUpHello-<mode>.exe`
- Startup with preview:
  - `dist\MythUpHello-<mode>.exe --show-camera`

Recommended Task Scheduler options:

- Run whether user is logged on or not (for headless mode)
- Run with highest privileges
- Delay task for 15 to 30 seconds after logon (camera drivers may need time)

## Notes

- Place one clear image per known person in `faces/`.
- Rebuild cache by deleting `encodings.npy` if known faces change significantly.
- Camera fallback probes indices 0 to 3 automatically.
- In terminal mode, `Ctrl+C` is handled for clean shutdown.
