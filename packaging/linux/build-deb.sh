#!/usr/bin/env bash
# Builds a .deb for sitblinksip-desktop by freezing the app with PyInstaller
# (so end users don't need a matching system Python + mediapipe/opencv/PySide6
# install) and wrapping the result in a standard Debian package tree.
#
# Usage: packaging/linux/build-deb.sh
# Output: dist/sitblinksip-desktop_<version>_<arch>.deb
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/build"
DIST_DIR="${PROJECT_ROOT}/dist"
VENV_DIR="${BUILD_DIR}/venv"
PKG_ROOT="${BUILD_DIR}/deb-root"

command -v dpkg-deb >/dev/null 2>&1 || { echo "dpkg-deb is required (Debian/Ubuntu provide it by default)" >&2; exit 1; }

# mediapipe is pinned to ==0.10.15 (see requirements.txt for why: newer
# releases dropped the mp.solutions API this app relies on), and that release
# only ships wheels for Python 3.9-3.11. Whatever `python3` means in the
# invoking shell is not trustworthy here - conda/pyenv routinely shadow it
# with an incompatible version (e.g. conda's base env defaulting to 3.12+),
# which fails with a confusing "no matching distribution" error deep inside
# pip. Search for a known-good interpreter by explicit version instead.
PYTHON_BIN=""
for candidate in python3.10 python3.11 python3.9; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v "$candidate")"
        break
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    echo "error: need python3.9, python3.10, or python3.11 on PATH (mediapipe==0.10.15 has no wheel for other versions)." >&2
    echo "Install one, e.g.: sudo apt install python3.10 python3.10-venv" >&2
    exit 1
fi
echo "==> Using ${PYTHON_BIN} ($(${PYTHON_BIN} --version 2>&1))"

VERSION="$("${PYTHON_BIN}" -c "
import re, sys
text = open(sys.argv[1]).read()
print(re.search(r'__version__\s*=\s*\"([^\"]+)\"', text).group(1))
" "${PROJECT_ROOT}/sitblinksip_desktop/__init__.py")"
ARCH="$(dpkg --print-architecture)"
PKG_NAME="sitblinksip-desktop"

echo "==> Building ${PKG_NAME} ${VERSION} (${ARCH})"

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
# wheel (unlike FaceMesh, which is bundled). A frozen --onefile build re-
# extracts to a fresh temp dir on every launch, so without this warm-up the
# app would silently redownload that model from the network on every single
# start. Triggering it once here means the spec's collect_all("mediapipe")
# picks up the file like any other bundled package data.
echo "==> Warming MediaPipe Pose model cache (one-time download)"
python -c "
import mediapipe as mp
mp.solutions.pose.Pose(model_complexity=0).close()
"

# The shared spec (used by the Windows and macOS builds too) is what decides
# --onefile vs --onedir per platform, and - unlike the old inline flags - it
# also bundles sitblinksip_desktop/resources, without which the installed app
# starts fine but plays no alert sounds.
echo "==> Freezing with PyInstaller"
pyinstaller --noconfirm \
    --distpath "${BUILD_DIR}/pyinstaller-dist" \
    --workpath "${BUILD_DIR}/pyinstaller-work" \
    "${PROJECT_ROOT}/packaging/pyinstaller/sitblinksip-desktop.spec"

deactivate

FROZEN_BIN="${BUILD_DIR}/pyinstaller-dist/${PKG_NAME}"
[ -f "${FROZEN_BIN}" ] || { echo "PyInstaller did not produce ${FROZEN_BIN}" >&2; exit 1; }

echo "==> Assembling package tree"
install -Dm755 "${FROZEN_BIN}" "${PKG_ROOT}/usr/bin/${PKG_NAME}"
install -Dm644 "${SCRIPT_DIR}/${PKG_NAME}.desktop" "${PKG_ROOT}/usr/share/applications/${PKG_NAME}.desktop"
install -Dm644 "${PROJECT_ROOT}/packaging/icons/${PKG_NAME}.svg" \
    "${PKG_ROOT}/usr/share/icons/hicolor/scalable/apps/${PKG_NAME}.svg"
install -Dm644 "${SCRIPT_DIR}/debian/copyright" \
    "${PKG_ROOT}/usr/share/doc/${PKG_NAME}/copyright"

mkdir -p "${PKG_ROOT}/DEBIAN"
install -m755 "${SCRIPT_DIR}/debian/postinst" "${PKG_ROOT}/DEBIAN/postinst"
install -m755 "${SCRIPT_DIR}/debian/postrm" "${PKG_ROOT}/DEBIAN/postrm"

INSTALLED_SIZE="$(du -sk "${PKG_ROOT}/usr" | cut -f1)"
sed \
    -e "s/__VERSION__/${VERSION}/" \
    -e "s/__ARCH__/${ARCH}/" \
    -e "s/__INSTALLED_SIZE__/${INSTALLED_SIZE}/" \
    "${SCRIPT_DIR}/debian/control" > "${PKG_ROOT}/DEBIAN/control"

echo "==> Building .deb"
OUTPUT="${DIST_DIR}/${PKG_NAME}_${VERSION}_${ARCH}.deb"
dpkg-deb --root-owner-group --build "${PKG_ROOT}" "${OUTPUT}"

echo "==> Done: ${OUTPUT}"
echo "Install with: sudo apt install ${OUTPUT}   (or: sudo dpkg -i ${OUTPUT})"
