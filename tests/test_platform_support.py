"""
project @ SitBlinkSip Desktop
author  @ github/ishworrsubedii

Covers the parts of cross-platform support that can be checked from any OS:
where settings land, and how each autostart backend quotes a command. The
platform branches are picked at call time from module-level flags, so a test
can exercise all three from one machine.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from sitblinksip_desktop import autostart, platform_support


@pytest.fixture
def as_platform(monkeypatch):
    """Pretend to be running on a given OS."""

    def _apply(name: str) -> None:
        flags = {
            "windows": ("IS_WINDOWS", "IS_MACOS", "IS_LINUX", (True, False, False)),
            "macos": ("IS_WINDOWS", "IS_MACOS", "IS_LINUX", (False, True, False)),
            "linux": ("IS_WINDOWS", "IS_MACOS", "IS_LINUX", (False, False, True)),
        }[name]
        *names, values = flags
        for module in (platform_support, autostart):
            for attr, value in zip(names, values):
                if hasattr(module, attr):
                    monkeypatch.setattr(module, attr, value, raising=False)

    return _apply


class TestConfigDir:
    def test_linux_uses_xdg_config_home(self, as_platform, monkeypatch, tmp_path):
        as_platform("linux")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert platform_support.config_dir() == tmp_path / "sitblinksip-desktop"

    def test_windows_uses_appdata(self, as_platform, monkeypatch, tmp_path):
        as_platform("windows")
        monkeypatch.setenv("APPDATA", str(tmp_path))
        assert platform_support.config_dir() == tmp_path / "sitblinksip-desktop"

    def test_macos_uses_application_support(self, as_platform, monkeypatch, tmp_path):
        as_platform("macos")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        expected = tmp_path / "Library" / "Application Support" / "sitblinksip-desktop"
        assert platform_support.config_dir() == expected

    def test_directory_is_created(self, as_platform, monkeypatch, tmp_path):
        as_platform("linux")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "nested" / "deeper"))
        assert platform_support.config_dir().is_dir()


class TestResourcesDir:
    def test_falls_back_to_source_tree(self, monkeypatch):
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        resources = platform_support.resources_dir()
        # The alert tones have to be findable, or the app runs silently.
        assert (resources / "sounds" / "blink.wav").is_file()

    def test_prefers_pyinstaller_bundle_layout(self, monkeypatch, tmp_path):
        bundled = tmp_path / "sitblinksip_desktop" / "resources"
        bundled.mkdir(parents=True)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        assert platform_support.resources_dir() == bundled


class TestLaunchCommand:
    def test_frozen_build_points_at_its_own_executable(self, monkeypatch, tmp_path):
        exe = tmp_path / "SitBlinkSipDesktop"
        exe.touch()
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(exe))
        assert platform_support.launch_command() == [str(exe.resolve())]

    def test_from_source_falls_back_to_module_invocation(self, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        monkeypatch.setattr(platform_support.shutil, "which", lambda _name: None)
        assert platform_support.launch_command() == [sys.executable, "-m", "sitblinksip_desktop"]


class TestDesktopExecQuoting:
    def test_plain_path_is_left_alone(self):
        assert autostart._desktop_exec_quote("/usr/bin/sitblinksip-desktop") == (
            "/usr/bin/sitblinksip-desktop"
        )

    def test_path_with_spaces_is_quoted(self):
        assert autostart._desktop_exec_quote("/opt/My Apps/run") == '"/opt/My Apps/run"'

    @pytest.mark.parametrize("char", ['"', "\\", "$", "`"])
    def test_reserved_characters_are_escaped(self, char):
        quoted = autostart._desktop_exec_quote(f"/opt/a{char}b")
        assert quoted.startswith('"') and quoted.endswith('"')
        if char in ('"', "\\"):
            assert f"\\{char}" in quoted


class TestLinuxAutostart:
    def test_write_and_remove_entry(self, as_platform, monkeypatch, tmp_path):
        as_platform("linux")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.setattr(autostart, "launch_command", lambda: ["/opt/My Apps/run"])

        assert autostart.set_enabled(True)
        entry = tmp_path / "autostart" / "sitblinksip-desktop.desktop"
        assert entry.is_file()
        assert autostart.is_enabled()

        text = entry.read_text()
        assert 'Exec="/opt/My Apps/run"' in text
        assert "Type=Application" in text

        assert autostart.set_enabled(False)
        assert not entry.exists()
        assert not autostart.is_enabled()

    def test_disabling_when_absent_is_not_an_error(self, as_platform, monkeypatch, tmp_path):
        as_platform("linux")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert autostart.set_enabled(False)


class TestWindowsAutostartQuoting:
    def test_registry_value_quotes_a_program_files_path(self):
        # The Run key is parsed by CreateProcess, so an install under
        # "C:\Program Files\..." must come back quoted or Windows will try to
        # launch "C:\Program".
        command = subprocess.list2cmdline([r"C:\Program Files\SitBlinkSip Desktop\app.exe"])
        assert command.startswith('"') and command.endswith('"')


class TestMacosLaunchAgent:
    def test_plist_is_written_and_removed(self, as_platform, monkeypatch, tmp_path):
        as_platform("macos")
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
        monkeypatch.setattr(autostart, "launch_command", lambda: ["/Applications/X.app/Contents/MacOS/X"])
        # launchctl doesn't exist off-macOS, and shouldn't be required anyway.
        monkeypatch.setattr(autostart, "_launchctl", lambda *args: None)
        monkeypatch.setattr(autostart.os, "getuid", lambda: 501, raising=False)

        assert autostart.set_enabled(True)
        plist_path = tmp_path / "Library" / "LaunchAgents" / f"{platform_support.BUNDLE_ID}.plist"
        assert plist_path.is_file()
        assert autostart.is_enabled()

        import plistlib

        with plist_path.open("rb") as handle:
            plist = plistlib.load(handle)
        assert plist["Label"] == platform_support.BUNDLE_ID
        assert plist["RunAtLoad"] is True
        assert plist["ProgramArguments"] == ["/Applications/X.app/Contents/MacOS/X"]

        assert autostart.set_enabled(False)
        assert not plist_path.exists()


class TestCameraErrorHint:
    @pytest.mark.parametrize(
        ("platform", "expected"),
        [("macos", "Privacy & Security"), ("windows", "Privacy & security"), ("linux", "/dev/video")],
    )
    def test_hint_is_platform_specific(self, as_platform, platform, expected):
        as_platform(platform)
        message = platform_support.camera_error_hint(0)
        assert "camera device 0" in message
        assert expected in message
