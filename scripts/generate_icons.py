#!/usr/bin/env python3
"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Renders the app icon (sitblinksip_desktop/icon.py) into the platform icon
files the installers need:

    packaging/icons/sitblinksip-desktop.png    512x512, general use
    packaging/icons/sitblinksip-desktop.ico    Windows (Inno Setup + the .exe)
    packaging/icons/sitblinksip-desktop.icns   macOS .app bundle

Both container formats are written here in pure Python rather than shelling
out to ImageMagick or macOS's `iconutil`, so `make icons` produces identical
files on any of the three platforms - which matters because the Windows .ico
has to be generated on whatever machine happens to be doing the release, and
that machine is usually not a Mac.

Usage: python scripts/generate_icons.py
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "packaging" / "icons"
BASENAME = "sitblinksip-desktop"

# Windows shows the icon everywhere from a 16px tray slot to a 256px "extra
# large icons" view and does not rescale gracefully, so ship every step.
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

# macOS icon element types, keyed by the pixel size each one must contain.
# The 4-char codes are the OSTypes from Apple's icns format; everything from
# 'ic07' on accepts a PNG payload (10.7+), which is all we target.
ICNS_ELEMENTS = (
    ("ic11", 32),    # 16pt @2x
    ("ic12", 64),    # 32pt @2x
    ("ic07", 128),   # 128pt @1x
    ("ic13", 256),   # 128pt @2x
    ("ic08", 256),   # 256pt @1x
    ("ic14", 512),   # 256pt @2x
    ("ic09", 512),   # 512pt @1x
    ("ic10", 1024),  # 512pt @2x
)


def _render_png(size: int) -> bytes:
    """PNG bytes of the app icon at `size`x`size`."""
    from PySide6.QtCore import QBuffer, QByteArray
    from sitblinksip_desktop.icon import render_image

    image = render_image(size)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QBuffer.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError(f"Qt failed to encode a {size}px PNG")
    buffer.close()
    return bytes(data)


def write_ico(path: Path, pngs: dict[int, bytes]) -> None:
    """Write a PNG-compressed .ico (the Vista+ form, universally supported)."""
    sizes = sorted(pngs)
    header = struct.pack("<HHH", 0, 1, len(sizes))  # reserved, type=icon, count

    entries = bytearray()
    payload = bytearray()
    offset = len(header) + 16 * len(sizes)
    for size in sizes:
        data = pngs[size]
        entries += struct.pack(
            "<BBBBHHII",
            size if size < 256 else 0,  # 0 is the format's escape for 256
            size if size < 256 else 0,
            0,   # palette entries: 0 for a true-colour image
            0,   # reserved
            1,   # colour planes
            32,  # bits per pixel
            len(data),
            offset,
        )
        payload += data
        offset += len(data)

    path.write_bytes(header + bytes(entries) + bytes(payload))


def write_icns(path: Path, pngs: dict[int, bytes]) -> None:
    """Write an .icns whose elements are PNG-encoded."""
    body = bytearray()
    for ostype, size in ICNS_ELEMENTS:
        data = pngs[size]
        body += ostype.encode("ascii")
        body += struct.pack(">I", len(data) + 8)  # length includes this header
        body += data

    path.write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + bytes(body))


def main() -> int:
    sys.path.insert(0, str(PROJECT_ROOT))

    # Icon rendering is pure QImage/QPainter work, but Qt still wants a
    # QGuiApplication to exist. "offscreen" keeps this runnable on a headless
    # CI box with no display.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication([])

    needed = sorted({*ICO_SIZES, *(size for _, size in ICNS_ELEMENTS), 512})
    pngs = {size: _render_png(size) for size in needed}

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    png_path = OUTPUT_DIR / f"{BASENAME}.png"
    png_path.write_bytes(pngs[512])

    ico_path = OUTPUT_DIR / f"{BASENAME}.ico"
    write_ico(ico_path, {size: pngs[size] for size in ICO_SIZES})

    icns_path = OUTPUT_DIR / f"{BASENAME}.icns"
    write_icns(icns_path, pngs)

    for out in (png_path, ico_path, icns_path):
        print(f"wrote {out.relative_to(PROJECT_ROOT)} ({out.stat().st_size:,} bytes)")

    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
