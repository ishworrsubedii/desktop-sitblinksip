# SitBlinkSip Desktop

A native desktop companion to [SitBlinkSip](../README.md), the health app for
people who spend long hours at a computer. Unlike the web dashboard (browser +
FastAPI backend + Docker), this is a standalone app you install once and it
quietly runs in the background - no server, no database, no browser tab to
keep open, just the webcam and a timer, entirely local to your machine.

What it does, at a glance:

- Counts your blinks using the webcam - **no camera feed is shown by default**,
  only a small always-on-top counter (blink count + blinks/min).
- Press **F6** (or use the tray menu) to reveal the live camera preview on
  demand, and again to hide it.
- If your blink rate over the last minute drops below a healthy minimum, every
  screen blanks for a couple of seconds as a "blink now" nudge, then resumes,
  with a short alert tone.
- **Posture corrector**: the same webcam feed is checked periodically for head
  tilt and forward lean (slouching); when your posture score drops too low you
  get a sound + notification (no screen blank - posture drift is gradual, not
  urgent like a missed blink).
- **Water break reminders**: an independent timer nudges you with a sound +
  notification on a configurable interval, whether or not tracking is paused.
- Lives in the system tray: pause/resume tracking, toggle the preview, open
  settings, or quit.

It reuses the same detection approach as the main project (eye-aspect-ratio
for blinks, head-tilt-angle/forward-displacement for posture), but via
MediaPipe FaceMesh/Pose instead of dlib, so there's no large landmark model
file to ship and no compiled dependency to build from source. The three alert
tones (blink/posture/water) mirror `frontend/lib/alertSounds.ts` so the
desktop app sounds like the same product as the web dashboard.

## OS support

| OS | Status | Notes |
| --- | --- | --- |
| Linux | ✅ Available now | Any desktop environment with a system tray; X11 recommended (see the [Wayland note](#about-the-f6-hotkey-and-wayland) below). Installable as a native `.deb`, or run from source. |
| Windows | 🕒 Coming soon | Not yet packaged or tested. See [Windows & macOS roadmap](#windows--macos-roadmap) below for what's planned and why it isn't ready yet. |
| macOS | Not currently planned | No macOS build exists yet; may follow after Windows. |

## Requirements

### Linux (available now)

- A desktop environment with a system tray, and a webcam.
- X11 recommended. Wayland mostly works too, with one caveat - see the
  [Wayland note](#about-the-f6-hotkey-and-wayland) below.
- Python 3.10+ if running from source. Not needed if you install the `.deb`
  (it bundles its own frozen Python via PyInstaller).
- Posture checking downloads a small (~3MB) MediaPipe Pose model on first use
  if it isn't already cached - needs network access once. The `.deb` build
  pre-fetches it at build time (see `build-deb.sh`) so installed users never
  hit this.

### Windows (coming soon)

Not available yet - see the [roadmap](#windows--macos-roadmap) below.

### macOS (not currently planned)

No build or timeline yet.

## Run from source

```bash
cd desktop-sitblinksip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m sitblinksip_desktop
```

## Build a native .deb package

```bash
cd desktop-sitblinksip
./packaging/linux/build-deb.sh
sudo apt install ./dist/sitblinksip-desktop_0.1.0_amd64.deb
```

The script freezes the app with PyInstaller (so end users don't need a
matching system Python, mediapipe, OpenCV, or PySide6 install) and wraps the
result into a standard Debian package with a proper app-menu entry and icon.
After installing, launch **SitBlinkSip Desktop** from your applications menu,
or run `sitblinksip-desktop` from a terminal.

Uninstall with `sudo apt remove sitblinksip-desktop`.

## Using it

| Action | How |
| --- | --- |
| Show/hide the blink counter | Tray icon -> "Show/Hide counter" (or click the tray icon) |
| Minimize the counter to just the blink count | **–** button on the counter widget |
| Close the counter (app keeps running in the tray) | **×** button on the counter widget |
| Show/hide the camera preview | Press **F6**, or tray icon -> "Show camera preview" |
| Pause/resume tracking | Tray icon -> "Pause tracking" |
| Enable/disable posture checks | Tray icon -> "Posture checks" (checkbox) |
| Enable/disable water reminders | Tray icon -> "Water break reminders" (checkbox) |
| Enable/disable alert sounds | Tray icon -> "Alert sounds" (checkbox) |
| Adjust sensitivity / thresholds | Tray icon -> "Settings..." |
| Quit | Tray icon -> "Quit" |

The three checkboxes are quick on/off switches for the whole feature (persisted
immediately); the Settings dialog has the same enable/disable checkboxes plus
their fine-tuning options (thresholds, intervals, etc.) alongside them.

If your desktop has no system tray (some minimal setups don't), right-click
the floating counter widget for the same menu.

### About the F6 hotkey and Wayland

Global hotkeys are handled via `pynput`, which relies on X11 and cannot
register system-wide under Wayland's security model - this is a platform
limitation, not something the app can work around. On a Wayland session, F6
still works while a SitBlinkSip window has focus, and the tray/right-click
menu always has a manual toggle regardless of session type.

## Configuration

Settings are available from the tray's "Settings..." dialog (Blink / Posture /
Water / General tabs) and persisted to
`~/.config/sitblinksip-desktop/config.json`:

- **Blink**: camera device index, EAR threshold, minimum blinks/minute, break
  screen duration, cooldown between breaks.
- **Posture**: enable/disable, head-tilt angle threshold, forward-lean
  threshold, posture score alert threshold, cooldown between alerts.
- **Water**: enable/disable, reminder interval.
- **General**: sound on/off, launch on login.

## Project layout

```
desktop-sitblinksip/
├── sitblinksip_desktop/     # application source
│   ├── app.py               # wires everything together (entry point)
│   ├── blink_engine.py      # headless MediaPipe EAR blink counter
│   ├── posture_engine.py    # headless MediaPipe Pose head-tilt/lean checker
│   ├── camera_worker.py     # background capture thread (blink + posture)
│   ├── water_reminder.py    # independent periodic water-break timer
│   ├── sound.py             # plays the blink/posture/water alert tones
│   ├── hud_widget.py        # floating counter + posture line + camera preview
│   ├── break_overlay.py     # full-screen "blink now" break
│   ├── tray_icon.py         # system tray menu
│   ├── hotkeys.py           # global F6 toggle (X11) with graceful fallback
│   ├── settings_dialog.py   # tabbed settings: blink/posture/water/general
│   ├── autostart.py         # XDG autostart entry management
│   ├── config.py            # persisted settings
│   ├── icon.py              # in-app icon, drawn in code (no asset deps)
│   └── resources/sounds/    # pre-rendered WAV alert tones
├── scripts/
│   └── generate_alert_sounds.py  # regenerates resources/sounds/*.wav
├── packaging/
│   ├── linux/
│   │   ├── sitblinksip-desktop.desktop
│   │   ├── build-deb.sh
│   │   └── debian/          # control, copyright, postinst, postrm
│   └── icons/                # app-menu icon (SVG)
└── tests/
```

## Development

```bash
pip install -r requirements.txt
python -m pytest tests/
```

## Scope

This desktop app covers blink, posture and water-break reminders - the same
three checks as the main SitBlinkSip web app - but as a standalone background
process with no server, database or network involved: just the webcam and a
timer, entirely local.

## Windows & macOS roadmap

The app is Linux-only today. The core stack (PySide6, MediaPipe, OpenCV,
NumPy, pynput) is cross-platform, but a few Linux-specific pieces still need
platform equivalents before a Windows (or macOS) build is usable:

| Piece | Linux implementation today | What Windows needs |
| --- | --- | --- |
| Packaging | `.deb` via PyInstaller (`packaging/linux/build-deb.sh`) | PyInstaller `--onefile`/`--onedir` build + a Windows installer (e.g. Inno Setup or an MSI) |
| Global **F6** hotkey | `pynput` over X11 (see the [Wayland note](#about-the-f6-hotkey-and-wayland)) | `pynput`'s Win32 backend - should work with little to no change, but needs testing |
| Launch on login | `autostart.py` writes an XDG autostart `.desktop` entry | Windows Registry `Run` key or a Startup-folder shortcut |
| System tray | `tray_icon.py` via PySide6 `QSystemTrayIcon` | Already cross-platform - should work as-is on Windows |
| App icon / menu entry | SVG icon + `.desktop` file (`packaging/icons`, `packaging/linux`) | `.ico` icon + Start Menu shortcut via the installer |

macOS isn't scheduled yet, but the same stack applies (with `.app`/`.dmg`
packaging and a `launchd` agent for autostart instead).

Want to help get Windows support out sooner? Contributions on any of the rows
above are welcome - see [CONTRIBUTING.md](../CONTRIBUTING.md) in the main
repo.

## License

Apache-2.0, same as the rest of the [SitBlinkSip](../README.md) project - see
[LICENSE](../LICENSE).
