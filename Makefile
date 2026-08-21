.PHONY: venv run test icons deb dmg app windows clean

VENV := .venv
PYTHON := $(VENV)/bin/python

venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

run:
	$(PYTHON) -m sitblinksip_desktop

test:
	$(VENV)/bin/pip install pytest >/dev/null
	$(PYTHON) -m pytest tests/

# Regenerates packaging/icons/*.{png,ico,icns} from sitblinksip_desktop/icon.py.
# Runs anywhere - the .ico and .icns writers are pure Python - so a release
# doesn't need a Windows box or a Mac just to refresh the icons.
icons:
	$(PYTHON) scripts/generate_icons.py

# Native packages. Each must run on its own OS: PyInstaller freezes the
# interpreter and native wheels of the machine it runs on, so there is no
# cross-compiling here.
deb:
	./packaging/linux/build-deb.sh

dmg app:
	./packaging/macos/build-macos.sh

windows:
	@echo "Run this on Windows, in PowerShell:"
	@echo "  powershell -ExecutionPolicy Bypass -File packaging\\windows\\build-windows.ps1"
	@exit 1

clean:
	rm -rf build dist *.egg-info
