#!/usr/bin/env bash
# Builds SitBlinkSip Desktop for macOS: a .app bundle plus a .dmg to ship it in.
#
# Mirrors packaging/linux/build-deb.sh. Freezes the app with PyInstaller (so
# end users need no Python, MediaPipe, OpenCV or Qt of their own) into an .app
# bundle - which is also the only way to get the Info.plist keys macOS demands
# before it will let a process touch the webcam.
#
# Usage: packaging/macos/build-macos.sh
# Output: dist/SitBlinkSip Desktop.app
#         dist/SitBlinkSip-Desktop-<version>-<arch>.dmg
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/build"
DIST_DIR="${PROJECT_ROOT}/dist"
VENV_DIR="${BUILD_DIR}/venv"
APP_NAME="SitBlinkSip Desktop"

[ "$(uname -s)" = "Darwin" ] || { echo "error: this script must run on macOS." >&2; exit 1; }

# mediapipe is pinned to ==0.10.15 (see requirements.txt for why: newer
# releases dropped the mp.solutions API this app relies on), and that release
# only ships wheels for Python 3.9-3.12. Whatever `python3` means in the
# invoking shell is not trustworthy here - conda, pyenv and Homebrew routinely
# shadow it with an incompatible version, which fails with a confusing "no
# matching distribution" error deep inside pip. Search for a known-good
# interpreter by explicit version instead.
PYTHON_BIN=""
for candidate in python3.11 python3.10 python3.12 python3.9; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v "$candidate")"
        break
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    echo "error: need python3.9-3.12 on PATH (mediapipe==0.10.15 has no wheel for other versions)." >&2
    echo "Install one, e.g.: brew install python@3.11" >&2
    exit 1
fi
echo "==> Using ${PYTHON_BIN} ($(${PYTHON_BIN} --version 2>&1))"

VERSION="$("${PYTHON_BIN}" -c "
import re, sys
text = open(sys.argv[1]).read()
print(re.search(r'__version__\s*=\s*\"([^\"]+)\"', text).group(1))
" "${PROJECT_ROOT}/sitblinksip_desktop/__init__.py")"

# Native-architecture build only. A universal2 bundle would need every wheel
# in the tree to be universal, and opencv-contrib-python (pulled in by
# mediapipe) publishes separate arm64 and x86_64 macOS wheels rather than a
# fat one - so an Apple Silicon build serves Apple Silicon, and an Intel
# build serves Intel. Build on both if you need to ship both.
ARCH="$(uname -m)"

echo "==> Building ${APP_NAME} ${VERSION} (${ARCH})"

rm -rf "${BUILD_DIR}" "${DIST_DIR}"
mkdir -p "${DIST_DIR}"

echo "==> Creating isolated build venv"
"${PYTHON_BIN}" -m venv "${VENV_DIR}"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip >/dev/null
pip install -r "${PROJECT_ROOT}/requirements.txt" pyinstaller >/dev/null

echo "==> Generating platform icons"
python "${PROJECT_ROOT}/scripts/generate_icons.py"

# mediapipe's legacy Pose Solutions API downloads its .tflite model into its
# own site-packages/ directory on first use instead of shipping it in the
# wheel (unlike FaceMesh, which is bundled). Triggering that download here
# means the spec's collect_all("mediapipe") picks the file up like any other
# bundled package data - otherwise every installed copy would re-download it,
# and users offline (or behind a proxy) would silently get no posture checks.
echo "==> Warming MediaPipe Pose model cache (one-time download)"
python -c "
import mediapipe as mp
mp.solutions.pose.Pose(model_complexity=0).close()
"

echo "==> Freezing with PyInstaller"
pyinstaller --noconfirm \
    --distpath "${DIST_DIR}" \
    --workpath "${BUILD_DIR}/pyinstaller-work" \
    "${PROJECT_ROOT}/packaging/pyinstaller/sitblinksip-desktop.spec"

deactivate

APP_BUNDLE="${DIST_DIR}/${APP_NAME}.app"
[ -d "${APP_BUNDLE}" ] || { echo "PyInstaller did not produce ${APP_BUNDLE}" >&2; exit 1; }

# PyInstaller rewrites library load paths after the linker has run, which
# invalidates the ad-hoc signatures the toolchain applied - and on Apple
# Silicon an invalid signature is fatal, not a warning. Re-sign the finished
# bundle so it launches at all, and so macOS keeps the camera (TCC) grant tied
# to a stable identity instead of re-prompting after every rebuild.
#
# This is still an *ad-hoc* signature, not a Developer ID one: the .dmg is not
# notarised, so first launch needs right-click -> Open (see the README).
echo "==> Ad-hoc signing the bundle"
codesign --force --deep --sign - --timestamp=none "${APP_BUNDLE}"
codesign --verify --deep --strict "${APP_BUNDLE}" && echo "    signature OK"

DMG_NAME="SitBlinkSip-Desktop-${VERSION}-${ARCH}"
DMG_PATH="${DIST_DIR}/${DMG_NAME}.dmg"
STAGING="${BUILD_DIR}/dmg-staging"

echo "==> Building .dmg"
rm -rf "${STAGING}"
mkdir -p "${STAGING}"
cp -R "${APP_BUNDLE}" "${STAGING}/"
# The customary drag-to-install target, so the DMG window explains itself
# without needing a background image.
ln -s /Applications "${STAGING}/Applications"

hdiutil create \
    -volname "${APP_NAME}" \
    -srcfolder "${STAGING}" \
    -ov -format UDZO \
    "${DMG_PATH}" >/dev/null

echo "==> Done:"
echo "    ${APP_BUNDLE}"
echo "    ${DMG_PATH}"
echo
echo "Install: open the .dmg and drag the app to Applications."
echo "First launch: right-click the app -> Open -> Open (the build is not"
echo "notarised, so a plain double-click is blocked by Gatekeeper)."
