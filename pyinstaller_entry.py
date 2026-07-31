"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

PyInstaller entry point, kept separate from sitblinksip_desktop/__main__.py.

A frozen --onefile build executes its target script as a standalone
top-level `__main__` module with no parent package - `__main__.py`'s
`from .app import main` fails there with "attempted relative import with no
known parent package" even though it works fine for `python -m
sitblinksip_desktop` (which sets up the package context `-m` provides). This
script uses an absolute import instead, so it works regardless of how it's
invoked.
"""
from sitblinksip_desktop.app import main

if __name__ == "__main__":
    main()
