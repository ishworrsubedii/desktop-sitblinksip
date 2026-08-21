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

Linux, Windows and macOS are all supported, from the same source tree and the
same [PyInstaller spec](packaging/pyinstaller/sitblinksip-desktop.spec).

| OS | Package | Notes |
| --- | --- | --- |
| Linux | `.deb` | Any desktop environment with a system tray. X11 recommended - see the [Wayland note](#about-the-f6-hotkey). |
| Windows | `setup.exe` (Inno Setup) | Windows 10/11, 64-bit. Everything works out of the box, including the global F6 hotkey. |
| macOS | `.dmg` (`.app` bundle) | macOS 11 Big Sur or newer, Apple Silicon and Intel. Runs as a menu-bar app with no Dock icon. Needs two [permission grants](#macos-permissions) on first run. |

## Requirements

Common to all three: a webcam, and - if running from source - Python
3.9-3.12. Python is not needed to run any of the packaged builds; they bundle
a frozen interpreter.

Posture checking uses a small (~3MB) MediaPipe Pose model that is downloaded
on first use if it isn't already cached, so running from source needs network
access once. All three build scripts pre-fetch it at build time, so users of
the packaged builds never hit this - including fully offline ones.

> [!NOTE]
> **Python version.** MediaPipe is pinned exactly, because 0.10.18+ dropped
> the `mediapipe.solutions` API this app is built on. That ceiling means
> CPython 3.9-3.12 only; 3.13 has no compatible wheel. Windows additionally
> pins one release lower (0.10.14 rather than 0.10.15), because upstream
> shipped no Windows wheel for 0.10.15 at all. `requirements.txt` encodes this
> with environment markers, so `pip install -r requirements.txt` does the
> right thing per platform without you having to think about it.

### macOS permissions

macOS gates both of the things this app does, so expect two prompts:

| Permission | Needed for | Where |
| --- | --- | --- |
| **Camera** | Blink and posture tracking (required) | System Settings → Privacy & Security → Camera |
| **Accessibility** | The global F6 hotkey (optional) | System Settings → Privacy & Security → Accessibility |

The camera prompt appears by itself on first launch. Accessibility does not -
without it, the app detects the missing grant at startup and tells you once
via a notification rather than leaving F6 silently dead. F6 still works while
a SitBlinkSip window is focused, and the menu bar always has a manual toggle.

Running **from source** on macOS, these permissions attach to your *terminal*
app, not to SitBlinkSip - so grant them to Terminal/iTerm instead.

## Run from source

Works the same on all three platforms:

```bash
cd desktop-sitblinksip
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m sitblinksip_desktop
```

## Build a native package

Each package has to be built **on the OS it targets** - PyInstaller freezes
the interpreter and native wheels of the machine it runs on, so there is no
cross-compiling. All three scripts follow the same shape: create an isolated
build venv, generate the platform icons, warm the MediaPipe Pose cache, freeze
via the shared spec, then wrap the result.

### Linux → `.deb`

```bash
./packaging/linux/build-deb.sh
sudo apt install ./dist/sitblinksip-desktop_0.1.0_amd64.deb
```

Produces a standard Debian package with an app-menu entry and icon. Launch
**SitBlinkSip Desktop** from your applications menu, or run
`sitblinksip-desktop` from a terminal. Uninstall with
`sudo apt remove sitblinksip-desktop`.

### Windows → `setup.exe`

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build-windows.ps1
```

Produces `dist\SitBlinkSipDesktop\` (the frozen app, directly runnable) and,
if [Inno Setup 6.3+](https://jrsoftware.org/isdl.php) is installed,
`dist\SitBlinkSipDesktop-0.1.0-setup.exe`. Inno Setup is optional - without it
you still get the app directory, just no installer. Pass `-SkipInstaller` to
skip that step deliberately.

The installer defaults to a **per-user** install (no UAC prompt), since the
app only ever writes to `%APPDATA%` and `HKCU`; you can switch it to a
machine-wide install in the wizard.

The build is unsigned, so SmartScreen will show a "Windows protected your PC"
warning on first run - click **More info → Run anyway**.

### macOS → `.dmg`

```bash
./packaging/macos/build-macos.sh
```

Produces `dist/SitBlinkSip Desktop.app` and
`dist/SitBlinkSip-Desktop-0.1.0-<arch>.dmg`. Open the DMG and drag the app to
Applications.

Two things to know:

- **Architecture.** The build is native-only, not universal2, because
  `opencv-contrib-python` (pulled in by MediaPipe) publishes separate arm64
  and x86_64 macOS wheels rather than a fat one. Build on Apple Silicon to
  ship for Apple Silicon, on Intel for Intel.
- **Gatekeeper.** The bundle is ad-hoc signed but not notarised, so the first
  launch needs **right-click → Open → Open**. A plain double-click is blocked.
  (The ad-hoc signature is not optional decoration: PyInstaller rewrites
  library load paths after linking, which invalidates the toolchain's
  signatures, and on Apple Silicon an invalid signature is fatal. It also
  gives the camera permission grant a stable identity to attach to, so macOS
  doesn't re-prompt after every rebuild.)

### Icons

`make icons` regenerates `packaging/icons/*.{png,ico,icns}` from the QPainter
drawing in [icon.py](sitblinksip_desktop/icon.py), so the installer artwork
can't drift from what the app actually renders in the tray. The `.ico` and
`.icns` writers are pure Python, so this runs on any of the three platforms -
no ImageMagick, no macOS `iconutil`.

## Using it

Everything is driven from the tray icon - the system tray on Linux, the
notification area on Windows, the menu bar on macOS. "Tray icon" below means
whichever of those your OS calls it.

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

### About the F6 hotkey

Global hotkeys are the one feature with genuinely different behaviour per
platform, because each OS decides for itself whether an ordinary app may
watch the keyboard:

| Platform | Global F6 | Why |
| --- | --- | --- |
| Windows | ✅ Works | `pynput` installs a Win32 low-level keyboard hook; no permission needed. |
| Linux (X11) | ✅ Works | `pynput` hooks X11 directly. |
| macOS | ⚠️ After granting Accessibility | See [macOS permissions](#macos-permissions). Detected at startup and reported once. |
| Linux (Wayland) | ❌ Blocked | Wayland's security model forbids system-wide key listeners for regular apps. A platform limitation, not something the app can work around. |

Wherever it's unavailable the app says so once, and nothing is lost: F6 still
works while a SitBlinkSip window has focus, and the tray/menu-bar (or the
HUD's right-click menu) always has a manual toggle.

## Configuration

Settings are available from the tray's "Settings..." dialog (Blink / Posture /
Water / General tabs) and persisted as `config.json` in the usual place for
each OS:

| Platform | Location |
| --- | --- |
| Linux | `~/.config/sitblinksip-desktop/` (or `$XDG_CONFIG_HOME`) |
| Windows | `%APPDATA%\sitblinksip-desktop\` |
| macOS | `~/Library/Application Support/sitblinksip-desktop/` |

The settings themselves:

- **Blink**: camera device index, EAR threshold, minimum blinks/minute, break
  screen duration, cooldown between breaks.
- **Posture**: enable/disable, head-tilt angle threshold, forward-lean
  threshold, posture score alert threshold, cooldown between alerts.
- **Water**: enable/disable, reminder interval.
- **General**: sound on/off, launch on login.

"Launch on login" writes whatever the platform expects: an XDG autostart entry
on Linux, an `HKCU\...\Run` registry value on Windows, or a launchd user agent
in `~/Library/LaunchAgents` on macOS.

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
│   ├── hotkeys.py           # global F6 toggle, per-platform, graceful fallback
│   ├── settings_dialog.py   # tabbed settings: blink/posture/water/general
│   ├── autostart.py         # launch-on-login: XDG / registry / launchd
│   ├── platform_support.py  # all the Linux/Windows/macOS differences, in one file
│   ├── config.py            # persisted settings
│   ├── icon.py              # in-app icon, drawn in code (no asset deps)
│   └── resources/sounds/    # pre-rendered WAV alert tones
├── scripts/
│   ├── generate_alert_sounds.py  # regenerates resources/sounds/*.wav
│   └── generate_icons.py    # renders icon.py to .png/.ico/.icns
├── packaging/
│   ├── pyinstaller/
│   │   └── sitblinksip-desktop.spec   # shared freeze config, all platforms
│   ├── linux/
│   │   ├── sitblinksip-desktop.desktop
│   │   ├── build-deb.sh
│   │   └── debian/          # control, copyright, postinst, postrm
│   ├── windows/
│   │   ├── build-windows.ps1
│   │   └── sitblinksip-desktop.iss    # Inno Setup installer
│   ├── macos/
│   │   └── build-macos.sh   # .app bundle + .dmg
│   └── icons/               # SVG source + generated .png/.ico/.icns
└── tests/
```

Platform differences are deliberately concentrated in `platform_support.py`
(paths, camera backend, process identity) and `autostart.py` (login items),
rather than scattered as `sys.platform` checks through the feature modules.

## Development

```bash
pip install -r requirements.txt pytest
python -m pytest tests/
```

The tests are headless and run on any of the three platforms. Alongside the
blink/posture engines they cover the cross-platform layer by faking the OS -
config paths, resource lookup (including the PyInstaller bundle layout), and
each autostart backend's quoting - so a change that breaks the Windows
registry value or the macOS launch agent fails on a Linux CI box too.

`make` targets: `venv`, `run`, `test`, `icons`, `deb`, `app`/`dmg`, `clean`.

## Scope

This desktop app covers blink, posture and water-break reminders - the same
three checks as the main SitBlinkSip web app - but as a standalone background
process with no server, database or network involved: just the webcam and a
timer, entirely local.

## How the platforms differ

The core stack (PySide6, MediaPipe, OpenCV, NumPy, pynput) is cross-platform,
so most of the app is genuinely shared code. These are the places where the
platforms actually diverge, and how each is handled:

| Piece | Linux | Windows | macOS |
| --- | --- | --- | --- |
| Packaging | `.deb` (PyInstaller `--onefile`) | Inno Setup installer around a `--onedir` build | `.app` bundle in a `.dmg` |
| Settings path | `~/.config` (XDG) | `%APPDATA%` | `~/Library/Application Support` |
| Launch on login | XDG autostart `.desktop` entry | `HKCU\...\CurrentVersion\Run` | launchd agent in `~/Library/LaunchAgents` |
| Global **F6** | X11 only, [not Wayland](#about-the-f6-hotkey) | Works as-is | Needs Accessibility permission |
| Camera | V4L2 (OpenCV default) | DirectShow, explicitly - OpenCV's default MSMF backend is slow to open and unreliable at mapping a device index | AVFoundation + a `NSCameraUsageDescription` in the bundle's `Info.plist`, without which macOS kills the process on first camera access |
| Tray / menu bar | `QSystemTrayIcon`, with the HUD's right-click menu as a fallback where no tray exists | `QSystemTrayIcon` + an explicit AppUserModelID, so notifications aren't attributed to "Python" | `QSystemTrayIcon` in the menu bar; `LSUIElement` keeps it out of the Dock |
| Break overlay | Frameless `Qt.Tool` window per screen | Same | Plain window, not `Qt.Tool` - a tool window can't become key on macOS, which would leave the overlay under the menu bar and unable to receive Escape |
| App icon | SVG + `.desktop` entry | `.ico` embedded in the `.exe` and used by the installer | `.icns` in the bundle |

Contributions welcome - see [CONTRIBUTING.md](../CONTRIBUTING.md) in the main
repo.

## License

Apache-2.0, same as the rest of the [SitBlinkSip](../README.md) project - see
[LICENSE](../LICENSE).
