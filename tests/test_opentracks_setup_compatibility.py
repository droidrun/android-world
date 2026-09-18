"""OpenTracks clean onboarding and permission verification without a device."""

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from android_world.env.setup_device import apps


PACKAGE = "de.dennisguse.opentracks"
BOTH_GRANTED = (
    "    android.permission.BLUETOOTH_SCAN: granted=true, flags=[ USER_SET ]\n"
    "    android.permission.BLUETOOTH_CONNECT: granted=true, flags=[ USER_SET ]\n"
)


@pytest.fixture
def opentracks_setup(monkeypatch):
    env = SimpleNamespace(controller=Mock())
    events = []
    ui = Mock()
    clear = Mock(side_effect=lambda *args: events.append("clear"))
    launch = Mock(side_effect=lambda name, controller: events.append("launch:" + name))
    close = Mock(side_effect=lambda name, controller: events.append("close:" + name))
    request = Mock(return_value=SimpleNamespace(
        status=1, generic=SimpleNamespace(output=BOTH_GRANTED.encode())))
    grants = Mock()
    monkeypatch.setattr(apps.adb_utils, "clear_app_data", clear)
    monkeypatch.setattr(apps.adb_utils, "launch_app", launch)
    monkeypatch.setattr(apps.adb_utils, "close_app", close)
    monkeypatch.setattr(apps.adb_utils, "grant_permissions", grants)
    monkeypatch.setattr(apps.adb_utils, "issue_generic_request", request)
    monkeypatch.setattr(apps.tools, "AndroidToolController", Mock(return_value=ui))
    monkeypatch.setattr(apps.time, "sleep", Mock())
    return SimpleNamespace(env=env, events=events, ui=ui, clear=clear, launch=launch,
                           close=close, request=request, grants=grants)


def test_visible_allow_keeps_official_grants_and_cleans_before_launch(opentracks_setup):
    fixture = opentracks_setup
    apps.OpenTracksApp.setup(fixture.env)
    fixture.clear.assert_called_once_with(PACKAGE, fixture.env.controller)
    assert fixture.events[0] == "clear"
    fixture.grants.assert_has_calls([
        call(PACKAGE, "android.permission.ACCESS_COARSE_LOCATION", fixture.env.controller),
        call(PACKAGE, "android.permission.ACCESS_FINE_LOCATION", fixture.env.controller),
        call(PACKAGE, "android.permission.POST_NOTIFICATIONS", fixture.env.controller),
    ])
    assert fixture.grants.call_count == 3
    fixture.ui.click_element.assert_called_once_with("Allow")
    fixture.request.assert_not_called()
    assert fixture.events[-1] == "close:" + apps.OpenTracksApp.app_name


@pytest.mark.parametrize("permissions,accepted", [
    (BOTH_GRANTED, True),
    (BOTH_GRANTED.replace("SCAN: granted=true", "SCAN: granted=false"), False),
    (BOTH_GRANTED.replace("CONNECT: granted=true", "CONNECT: granted=false"), False),
    ("android.permission.BLUETOOTH_SCAN: granted=true\n", False),
    ("android.permission.BLUETOOTH_CONNECT: granted=true\n", False),
    ("", False),
    (BOTH_GRANTED.replace("granted=true", "granted=trueish"), False),
    (BOTH_GRANTED.replace("android.permission.", "other.permission."), False),
    (BOTH_GRANTED + "android.permission.BLUETOOTH_SCAN: granted=false\n", False),
])
def test_absent_allow_requires_both_exact_granted_states(opentracks_setup, permissions, accepted):
    fixture = opentracks_setup
    fixture.ui.click_element.side_effect = ValueError("Allow absent")
    fixture.request.return_value.generic.output = permissions.encode()
    if accepted:
        apps.OpenTracksApp.setup(fixture.env)
        assert fixture.launch.call_args_list[-1] == call("activity tracker", fixture.env.controller)
    else:
        with pytest.raises(ValueError, match="Allow absent"):
            apps.OpenTracksApp.setup(fixture.env)
        assert fixture.launch.call_count == 1
    fixture.request.assert_called_once_with(
        ["shell", "dumpsys", "package", PACKAGE], fixture.env.controller)
    assert fixture.events[-1] == "close:" + apps.OpenTracksApp.app_name


def test_failed_dumpsys_cannot_authorize_missing_prompt(opentracks_setup):
    fixture = opentracks_setup
    fixture.ui.click_element.side_effect = ValueError("Allow absent")
    fixture.request.return_value.status = 2
    with pytest.raises(RuntimeError, match="Cannot verify OpenTracks Bluetooth permissions"):
        apps.OpenTracksApp.setup(fixture.env)
    assert fixture.events[-1] == "close:" + apps.OpenTracksApp.app_name


def test_unrelated_controller_failure_is_not_treated_as_existing_permission(opentracks_setup):
    fixture = opentracks_setup
    fixture.ui.click_element.side_effect = RuntimeError("Controller disconnected")
    with pytest.raises(RuntimeError, match="Controller disconnected"):
        apps.OpenTracksApp.setup(fixture.env)
    fixture.request.assert_not_called()
    assert fixture.events[-1] == "close:" + apps.OpenTracksApp.app_name


def test_failed_data_clear_cannot_launch_or_snapshot_old_state(opentracks_setup):
    fixture = opentracks_setup
    fixture.clear.side_effect = RuntimeError("Data clear failed")
    with pytest.raises(RuntimeError, match="Data clear failed"):
        apps.OpenTracksApp.setup(fixture.env)
    fixture.launch.assert_not_called()
    fixture.request.assert_not_called()
    fixture.close.assert_called_once_with(apps.OpenTracksApp.app_name, fixture.env.controller)


def test_permission_grant_failure_closes_app(opentracks_setup):
    fixture = opentracks_setup
    fixture.grants.side_effect = RuntimeError("Permission grant failed")
    with pytest.raises(RuntimeError, match="Permission grant failed"):
        apps.OpenTracksApp.setup(fixture.env)
    fixture.request.assert_not_called()
    assert fixture.events[-1] == "close:" + apps.OpenTracksApp.app_name
