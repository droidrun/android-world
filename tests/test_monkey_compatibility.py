"""Regression coverage for launch-only Monkey on the API 33 emulator."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from android_world.env import adb_utils
from android_world.env.setup_device import apps


def _emulator_without_physical_system_keys(commands):
    def issue(command, controller, **kwargs):
        del controller, kwargs
        commands.append(command)
        if command[:2] == ["shell", "monkey"]:
            if "--pct-syskeys" not in command or command[command.index("--pct-syskeys") + 1] != "0":
                raise RuntimeError("** SYS_KEYS has no physical keys but with factor 2.0%.")
        return SimpleNamespace(output=b"Events injected: 1\n")
    return issue


@pytest.mark.parametrize("app,package", [
    (apps.AudioRecorder, "com.dimowner.audiorecorder"),
    (apps.VlcApp, "org.videolan.vlc"),
    (apps.JoplinApp, "net.cozic.joplin"),
])
def test_official_setup_launches_on_emulator_without_syskeys(monkeypatch, app, package):
    commands = []
    monkeypatch.setattr(apps.AppSetup, "setup", Mock())
    monkeypatch.setattr(adb_utils, "grant_permissions", Mock())
    monkeypatch.setattr(adb_utils, "close_app", Mock())
    monkeypatch.setattr(adb_utils, "issue_generic_request", _emulator_without_physical_system_keys(commands))
    monkeypatch.setattr(apps.time, "sleep", Mock())
    monkeypatch.setattr(apps.file_utils, "check_directory_exists", Mock(return_value=True))
    monkeypatch.setattr(apps.tools, "AndroidToolController", Mock())
    monkeypatch.setattr(apps.joplin_app_utils, "create_note", Mock())
    monkeypatch.setattr(apps.joplin_app_utils, "clear_dbs", Mock())
    app.setup(SimpleNamespace(controller=Mock()))
    assert len(commands) == 1
    command = commands[0]
    assert command[command.index("-p") + 1] == package
    assert "-candroid.intent.category.LAUNCHER" in command
    assert command[-1] == "1"


def test_unknown_package_launch_works_without_physical_syskeys(monkeypatch):
    commands = []
    monkeypatch.setattr(adb_utils, "get_adb_activity", Mock(return_value=None))
    monkeypatch.setattr(adb_utils, "issue_generic_request", _emulator_without_physical_system_keys(commands))
    package = "com.example.launchable"
    assert adb_utils.launch_app(package, Mock()) == package
    assert len(commands) == 1
    assert commands[0][commands[0].index("-p") + 1] == package
    assert commands[0][-1] == "1"
