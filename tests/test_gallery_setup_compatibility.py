"""Gallery all-files onboarding compatibility without a device."""

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from android_world.env.setup_device import apps


PACKAGE = "com.simplemobiletools.gallery.pro"
UID_ALLOW_PACKAGE_DEFAULT = (
    "Uid mode: MANAGE_EXTERNAL_STORAGE: allow\n"
    "MANAGE_EXTERNAL_STORAGE: default; rejectTime=+5m ago\n"
)


@pytest.fixture
def gallery_setup(monkeypatch):
    env = SimpleNamespace(controller=Mock())
    ui = Mock()
    clear, launch, close, grants = Mock(), Mock(), Mock(), Mock()
    request = Mock(return_value=SimpleNamespace(
        status=1, generic=SimpleNamespace(output=UID_ALLOW_PACKAGE_DEFAULT.encode())))
    monkeypatch.setattr(apps.adb_utils, "clear_app_data", clear)
    monkeypatch.setattr(apps.adb_utils, "launch_app", launch)
    monkeypatch.setattr(apps.adb_utils, "close_app", close)
    monkeypatch.setattr(apps.adb_utils, "grant_permissions", grants)
    monkeypatch.setattr(apps.adb_utils, "issue_generic_request", request)
    monkeypatch.setattr(apps.tools, "AndroidToolController", Mock(return_value=ui))
    monkeypatch.setattr(apps.time, "sleep", Mock())
    return SimpleNamespace(env=env, ui=ui, clear=clear, launch=launch, close=close,
                           grants=grants, request=request)


def test_gallery_visible_permission_screens_keep_official_onboarding(gallery_setup):
    fixture = gallery_setup
    apps.SimpleGalleryProApp.setup(fixture.env)
    fixture.clear.assert_called_once_with(PACKAGE, fixture.env.controller)
    assert fixture.grants.call_args_list == [
        call(PACKAGE, permission, fixture.env.controller)
        for permission in apps.SimpleGalleryProApp.PERMISSIONS]
    assert fixture.ui.click_element.call_args_list == [
        call("All files"), call("Allow access to manage all files")]
    fixture.request.assert_not_called()
    fixture.close.assert_called_once_with(apps.SimpleGalleryProApp.app_name, fixture.env.controller)


@pytest.mark.parametrize("missing_screen", ["All files", "Allow access to manage all files"])
@pytest.mark.parametrize("mode,accepted", [
    (UID_ALLOW_PACKAGE_DEFAULT, True),
    ("Uid mode: MANAGE_EXTERNAL_STORAGE: allow", True),
    ("MANAGE_EXTERNAL_STORAGE: allow; time=+1m ago", True),
    ("MANAGE_EXTERNAL_STORAGE: default", False),
    ("MANAGE_EXTERNAL_STORAGE: ignore", False),
    ("Uid mode: MANAGE_EXTERNAL_STORAGE: ignore\nMANAGE_EXTERNAL_STORAGE: allow", False),
    ("Uid mode: MANAGE_EXTERNAL_STORAGE: default\nMANAGE_EXTERNAL_STORAGE: allow", False),
    ("Uid mode: MANAGE_EXTERNAL_STORAGE: allow\nMANAGE_EXTERNAL_STORAGE: ignore", False),
    ("Uid mode: MANAGE_EXTERNAL_STORAGE: allow\nUid mode: MANAGE_EXTERNAL_STORAGE: ignore", False),
    ("Uid mode: MANAGE_EXTERNAL_STORAGE: allowed", False),
    ("", False),
])
def test_gallery_missing_screen_requires_verified_existing_allow(gallery_setup, missing_screen, mode, accepted):
    fixture = gallery_setup
    def click(label):
        if label == missing_screen:
            raise ValueError("Permission screen absent: " + label)
    fixture.ui.click_element.side_effect = click
    fixture.request.return_value.generic.output = mode.encode()
    if accepted:
        apps.SimpleGalleryProApp.setup(fixture.env)
    else:
        with pytest.raises(ValueError, match="Permission screen absent"):
            apps.SimpleGalleryProApp.setup(fixture.env)
    fixture.request.assert_called_once_with(
        ["shell", "appops", "get", PACKAGE, "MANAGE_EXTERNAL_STORAGE"], fixture.env.controller)
    fixture.close.assert_called_once_with(apps.SimpleGalleryProApp.app_name, fixture.env.controller)


def test_gallery_failed_permission_query_cannot_authorize_missing_screen(gallery_setup):
    fixture = gallery_setup
    fixture.ui.click_element.side_effect = ValueError("All files absent")
    fixture.request.return_value.status = 2
    with pytest.raises(RuntimeError, match="Cannot verify Gallery all-files permission"):
        apps.SimpleGalleryProApp.setup(fixture.env)
    fixture.close.assert_called_once_with(apps.SimpleGalleryProApp.app_name, fixture.env.controller)


def test_gallery_unrelated_ui_failure_does_not_query_permission(gallery_setup):
    fixture = gallery_setup
    fixture.ui.click_element.side_effect = RuntimeError("Controller disconnected")
    with pytest.raises(RuntimeError, match="Controller disconnected"):
        apps.SimpleGalleryProApp.setup(fixture.env)
    fixture.request.assert_not_called()
    fixture.close.assert_called_once_with(apps.SimpleGalleryProApp.app_name, fixture.env.controller)
