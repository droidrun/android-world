"""Contacts notification-label compatibility with no live device access."""

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from android_world.env import adb_utils
from android_world.env.setup_device import apps


@pytest.fixture
def contacts_setup(monkeypatch):
    controller = Mock()
    close = Mock()
    monkeypatch.setattr(apps.AppSetup, "setup", Mock())
    monkeypatch.setattr(adb_utils, "launch_app", Mock())
    monkeypatch.setattr(adb_utils, "close_app", close)
    monkeypatch.setattr(adb_utils, "issue_generic_request", Mock(return_value=SimpleNamespace(
        status=1, generic=SimpleNamespace(output=b""))))
    monkeypatch.setattr(apps.time, "sleep", Mock())
    monkeypatch.setattr(apps.tools, "AndroidToolController", Mock(return_value=controller))
    return SimpleNamespace(controller=Mock()), controller, close


@pytest.mark.parametrize("visible_label,expected", [
    ("Don't allow", ["Skip", "Don't allow"]),
    ("Don’t allow", ["Skip", "Don't allow", "Don’t allow"]),
])
def test_contacts_setup_accepts_ascii_and_curly_apostrophe(contacts_setup, visible_label, expected):
    env, controller, close = contacts_setup
    def click(label):
        if label not in ("Skip", visible_label):
            raise ValueError(f"Element not found: {label}")
    controller.click_element.side_effect = click
    apps.ContactsApp.setup(env)
    assert controller.click_element.call_args_list == [call(label) for label in expected]
    close.assert_called_once_with("contacts", env.controller)


def test_contacts_setup_propagates_failure_when_both_labels_are_missing(contacts_setup):
    env, controller, close = contacts_setup
    def click(label):
        if label != "Skip":
            raise ValueError(f"Element not found: {label}")
    controller.click_element.side_effect = click
    with pytest.raises(ValueError, match="Don’t allow"):
        apps.ContactsApp.setup(env)
    assert controller.click_element.call_args_list == [call("Skip"), call("Don't allow"), call("Don’t allow")]
    close.assert_called_once_with("contacts", env.controller)


def test_contacts_setup_does_not_retry_unrelated_controller_failure(contacts_setup):
    env, controller, close = contacts_setup
    controller.click_element.side_effect = [None, RuntimeError("Controller disconnected")]
    with pytest.raises(RuntimeError, match="Controller disconnected"):
        apps.ContactsApp.setup(env)
    assert controller.click_element.call_args_list == [call("Skip"), call("Don't allow")]
    close.assert_called_once_with("contacts", env.controller)


@pytest.mark.parametrize("permission,accepted", [("granted=false", True), ("granted=true", False), ("", False)])
def test_missing_prompt_requires_explicit_denied_permission(contacts_setup, permission, accepted):
    env, controller, close = contacts_setup
    controller.click_element.side_effect = [None, ValueError("ASCII absent"), ValueError("Curly absent")]
    adb_utils.issue_generic_request.return_value.generic.output = (
        f"android.permission.POST_NOTIFICATIONS: {permission}".encode())
    if accepted:
        apps.ContactsApp.setup(env)
    else:
        with pytest.raises(ValueError, match="Curly absent"):
            apps.ContactsApp.setup(env)
    close.assert_called_once_with("contacts", env.controller)
