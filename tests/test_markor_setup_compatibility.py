from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from android_world.env.setup_device import apps


@pytest.mark.parametrize("mode,allowed", [("Uid mode: MANAGE_EXTERNAL_STORAGE: allow", True),
                                         ("MANAGE_EXTERNAL_STORAGE: allow", True),
                                         ("MANAGE_EXTERNAL_STORAGE: default", False),
                                         ("", False)])
def test_markor_absent_permission_screen_requires_existing_grant(monkeypatch, mode, allowed):
    env = SimpleNamespace(controller=Mock())
    controller = Mock()
    def click(label):
        if label == "Allow access to manage all files":
            raise ValueError("Permission screen absent")
    controller.click_element.side_effect = click
    close = Mock()
    monkeypatch.setattr(apps.AppSetup, "setup", Mock())
    monkeypatch.setattr(apps.adb_utils, "launch_app", Mock())
    monkeypatch.setattr(apps.adb_utils, "close_app", close)
    monkeypatch.setattr(apps.adb_utils, "issue_generic_request", Mock(return_value=SimpleNamespace(
        status=1, generic=SimpleNamespace(output=mode.encode()))))
    monkeypatch.setattr(apps.tools, "AndroidToolController", Mock(return_value=controller))
    monkeypatch.setattr(apps.time, "sleep", Mock())
    if allowed:
        apps.MarkorApp.setup(env)
    else:
        with pytest.raises(ValueError, match="Permission screen absent"):
            apps.MarkorApp.setup(env)
    close.assert_called_once_with("markor", env.controller)
