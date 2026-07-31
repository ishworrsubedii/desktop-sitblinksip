.PHONY: venv run test deb clean

VENV := .venv

venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

run:
	$(VENV)/bin/python -m sitblinksip_desktop

test:
	$(VENV)/bin/pip install pytest >/dev/null
	$(VENV)/bin/python -m pytest tests/

deb:
	./packaging/linux/build-deb.sh

clean:
	rm -rf build dist *.egg-info
