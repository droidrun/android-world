"""Retained SMS role and VLC storage grant handling without live device access."""

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from android_world.env.setup_device import apps


SMS_PACKAGE = "com.simplemobiletools.smsmessenger"
STORAGE_ALLOW = "Uid mode: MANAGE_EXTERNAL_STORAGE: allow\nMANAGE_EXTERNAL_STORAGE: default; time=+1m ago\n"


def role_dump(holder=SMS_PACKAGE, user=0, role="SMS"):
    return ("ROLE STATE (dumpsys role):\n{\n  user_states={\n"
            f"    user_id={user}\n    version=-1\n    roles=[\n      {{\n"
            f"        name=android.app.role.{role}\n        holders={holder}\n"
            "      }\n    ]\n  }\n}\n")


@pytest.fixture
def setup_fixture(monkeypatch):
    env = SimpleNamespace(controller=Mock())
    ui, clear, launch, close, defaults, grants = (Mock() for _ in range(6))
    request = Mock(return_value=SimpleNamespace(status=1, generic=SimpleNamespace(output=b"")))
    monkeypatch.setattr(apps.adb_utils, "clear_app_data", clear)
    monkeypatch.setattr(apps.adb_utils, "launch_app", launch)
    monkeypatch.setattr(apps.adb_utils, "close_app", close)
    monkeypatch.setattr(apps.adb_utils, "set_default_app", defaults)
    monkeypatch.setattr(apps.adb_utils, "grant_permissions", grants)
    monkeypatch.setattr(apps.adb_utils, "issue_generic_request", request)
    monkeypatch.setattr(apps.tools, "AndroidToolController", Mock(return_value=ui))
    monkeypatch.setattr(apps.file_utils, "check_directory_exists", Mock(return_value=True))
    monkeypatch.setattr(apps.time, "sleep", Mock())
    return SimpleNamespace(env=env, ui=ui, clear=clear, launch=launch, close=close,
                           defaults=defaults, grants=grants, request=request)


def test_sms_visible_chooser_preserves_official_setup(setup_fixture):
    fixture = setup_fixture
    apps.SimpleSMSMessengerApp.setup(fixture.env)
    fixture.clear.assert_called_once_with(SMS_PACKAGE, fixture.env.controller)
    fixture.defaults.assert_called_once_with("sms_default_application", SMS_PACKAGE, fixture.env.controller)
    assert fixture.ui.click_element.call_args_list == [call("SMS Messenger"), call("Set as default")]
    fixture.request.assert_not_called()
    fixture.close.assert_called_once_with(apps.SimpleSMSMessengerApp.app_name, fixture.env.controller)


@pytest.mark.parametrize("missing", ["SMS Messenger", "Set as default"])
@pytest.mark.parametrize("dump,accepted", [
    (role_dump(), True),
    (role_dump(holder="com.google.android.apps.messaging"), False),
    (role_dump(user=10), False),
    (role_dump(role="BROWSER"), False),
    (role_dump(holder="") + role_dump(user=10), False),
    (role_dump() + role_dump(), False),
    (role_dump(holder="other.package") + role_dump(role="BROWSER"), False),
    ("", False),
])
def test_sms_missing_chooser_requires_exact_owner_role(setup_fixture, missing, dump, accepted):
    fixture = setup_fixture
    def click(label):
        if label == missing:
            raise ValueError("SMS chooser absent")
    fixture.ui.click_element.side_effect = click
    fixture.request.return_value.generic.output = dump.encode()
    if accepted:
        apps.SimpleSMSMessengerApp.setup(fixture.env)
    else:
        with pytest.raises(ValueError, match="SMS chooser absent"):
            apps.SimpleSMSMessengerApp.setup(fixture.env)
    fixture.request.assert_called_once_with(["shell", "dumpsys", "role"], fixture.env.controller)
    fixture.close.assert_called_once_with(apps.SimpleSMSMessengerApp.app_name, fixture.env.controller)


def test_sms_failed_role_query_rejects_even_apparently_matching_holder(setup_fixture):
    fixture = setup_fixture
    fixture.ui.click_element.side_effect = ValueError("SMS chooser absent")
    fixture.request.return_value = SimpleNamespace(status=2, generic=SimpleNamespace(output=role_dump().encode()))
    with pytest.raises(RuntimeError, match="Cannot verify default SMS role"):
        apps.SimpleSMSMessengerApp.setup(fixture.env)
    fixture.close.assert_called_once_with(apps.SimpleSMSMessengerApp.app_name, fixture.env.controller)


def test_sms_unrelated_controller_failure_is_not_treated_as_retained_role(setup_fixture):
    fixture = setup_fixture
    fixture.ui.click_element.side_effect = RuntimeError("Controller disconnected")
    with pytest.raises(RuntimeError, match="Controller disconnected"):
        apps.SimpleSMSMessengerApp.setup(fixture.env)
    fixture.request.assert_not_called()
    fixture.close.assert_called_once_with(apps.SimpleSMSMessengerApp.app_name, fixture.env.controller)


def test_vlc_visible_permission_flow_preserves_monkey_launch_and_grant(setup_fixture):
    fixture = setup_fixture
    apps.VlcApp.setup(fixture.env)
    fixture.clear.assert_called_once_with("org.videolan.vlc", fixture.env.controller)
    fixture.grants.assert_called_once_with("org.videolan.vlc", "android.permission.POST_NOTIFICATIONS", fixture.env.controller)
    assert fixture.ui.click_element.call_args_list == [
        call("Skip"), call("GRANT PERMISSION"), call("OK"), call("Allow access to manage all files")]
    assert fixture.request.call_count == 1
    assert fixture.request.call_args.args[0][:4] == ["shell", "monkey", "--pct-syskeys", "0"]
    fixture.close.assert_called_once_with("vlc", fixture.env.controller)


@pytest.mark.parametrize("missing", ["GRANT PERMISSION", "OK", "Allow access to manage all files"])
@pytest.mark.parametrize("mode,accepted", [
    (STORAGE_ALLOW, True),
    ("MANAGE_EXTERNAL_STORAGE: allow", True),
    ("MANAGE_EXTERNAL_STORAGE: default", False),
    ("MANAGE_EXTERNAL_STORAGE: ignore", False),
    ("Uid mode: MANAGE_EXTERNAL_STORAGE: ignore\nMANAGE_EXTERNAL_STORAGE: allow", False),
    ("Uid mode: MANAGE_EXTERNAL_STORAGE: allow\nMANAGE_EXTERNAL_STORAGE: ignore", False),
    ("MANAGE_EXTERNAL_STORAGE: allowed", False),
    ("", False),
])
def test_vlc_missing_permission_screen_requires_existing_allow(setup_fixture, missing, mode, accepted):
    fixture = setup_fixture
    def click(label):
        if label == missing:
            raise ValueError("VLC permission screen absent")
    fixture.ui.click_element.side_effect = click
    fixture.request.return_value.generic.output = mode.encode()
    if accepted:
        apps.VlcApp.setup(fixture.env)
    else:
        with pytest.raises(ValueError, match="VLC permission screen absent"):
            apps.VlcApp.setup(fixture.env)
    assert fixture.request.call_args_list[-1] == call(
        ["shell", "appops", "get", "org.videolan.vlc", "MANAGE_EXTERNAL_STORAGE"], fixture.env.controller)
    fixture.close.assert_called_once_with("vlc", fixture.env.controller)


def test_vlc_missing_unrelated_skip_does_not_accept_retained_storage(setup_fixture):
    fixture = setup_fixture
    fixture.ui.click_element.side_effect = ValueError("Skip absent")
    fixture.request.return_value.generic.output = STORAGE_ALLOW.encode()
    with pytest.raises(ValueError, match="Skip absent"):
        apps.VlcApp.setup(fixture.env)
    assert fixture.request.call_count == 1  # Only the original Monkey launch.
    fixture.close.assert_called_once_with("vlc", fixture.env.controller)


def test_vlc_failed_appops_query_cannot_authorize_missing_prompt(setup_fixture):
    fixture = setup_fixture
    fixture.ui.click_element.side_effect = [None, ValueError("VLC permission screen absent")]
    fixture.request.side_effect = [
        SimpleNamespace(status=1, generic=SimpleNamespace(output=b"")),
        SimpleNamespace(status=2, generic=SimpleNamespace(output=STORAGE_ALLOW.encode())),
    ]
    with pytest.raises(RuntimeError, match="Cannot verify VLC all-files permission"):
        apps.VlcApp.setup(fixture.env)
    fixture.close.assert_called_once_with("vlc", fixture.env.controller)


def test_vlc_unrelated_controller_error_propagates(setup_fixture):
    fixture = setup_fixture
    fixture.ui.click_element.side_effect = [None, RuntimeError("Controller disconnected")]
    with pytest.raises(RuntimeError, match="Controller disconnected"):
        apps.VlcApp.setup(fixture.env)
    assert fixture.request.call_count == 1
    fixture.close.assert_called_once_with("vlc", fixture.env.controller)
