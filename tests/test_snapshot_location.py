"""Snapshot save and restore use one root without live device access."""

from unittest.mock import Mock, call

import pytest

from android_world.env import adb_utils, device_constants
from android_world.env.setup_device import setup
from android_world.utils import app_snapshot, file_utils


SNAPSHOT_ROOT = "/data/local/tmp/android_world/snapshots"
CONTACTS = "com.google.android.contacts"


def test_snapshot_root_is_outside_package_manager_app_data():
    assert device_constants.SNAPSHOT_DATA == SNAPSHOT_ROOT
    for app in setup._APPS:
        assert app_snapshot._snapshot_path(app.app_name) == f"{SNAPSHOT_ROOT}/{app.package_name()}"
        assert app_snapshot._app_data_path(app.app_name) == f"/data/data/{app.package_name()}"


def test_official_save_and_restore_use_the_same_relocated_snapshot(monkeypatch):
    operations = Mock()
    monkeypatch.setattr(file_utils, "clear_directory", operations.clear)
    monkeypatch.setattr(file_utils, "copy_dir", operations.copy)
    monkeypatch.setattr(file_utils, "check_directory_exists", operations.exists)
    operations.exists.return_value = True
    monkeypatch.setattr(adb_utils, "close_app", operations.close)
    monkeypatch.setattr(adb_utils, "issue_generic_request", operations.request)
    monkeypatch.setattr(adb_utils, "check_ok", operations.check_ok)
    controller = Mock()
    snapshot = f"{SNAPSHOT_ROOT}/{CONTACTS}"
    app_data = f"/data/data/{CONTACTS}"

    app_snapshot.save_snapshot("contacts", controller)
    app_snapshot.restore_snapshot("contacts", controller)

    assert operations.mock_calls[:6] == [
        call.clear(snapshot, controller),
        call.copy(app_data, snapshot, controller),
        call.close("contacts", controller),
        call.exists(snapshot, controller),
        call.clear(app_data, controller),
        call.copy(snapshot, app_data, controller),
    ]
    assert operations.request.call_args_list == [
        call(["shell", "restorecon", "-RD", app_data], controller),
        call(["shell", "chmod", "777", "-R", app_data], controller),
    ]


def test_restore_does_not_fall_back_to_old_snapshot_location(monkeypatch):
    old_snapshot = f"/data/data/android_world/snapshots/{CONTACTS}"
    exists = Mock(side_effect=lambda path, controller: path == old_snapshot)
    monkeypatch.setattr(file_utils, "check_directory_exists", exists)
    copy = Mock()
    monkeypatch.setattr(file_utils, "copy_dir", copy)
    monkeypatch.setattr(adb_utils, "close_app", Mock())
    controller = Mock()

    with pytest.raises(RuntimeError, match=f"Snapshot not found in {SNAPSHOT_ROOT}/{CONTACTS}"):
        app_snapshot.restore_snapshot("contacts", controller)

    exists.assert_called_once_with(f"{SNAPSHOT_ROOT}/{CONTACTS}", controller)
    copy.assert_not_called()
