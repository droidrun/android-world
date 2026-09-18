"""Calendar snapshots must include the persisted default event visibility."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from android_world.env.setup_device import apps


READY = b'<map><set name="display_event_types"><string>1</string></set></map>'


def response(body=READY, status=1):
    return SimpleNamespace(status=status, generic=SimpleNamespace(output=body))


@pytest.fixture
def setup(monkeypatch):
    env = SimpleNamespace(controller=Mock())
    base, launch, close, grant, query, sleep = (Mock() for _ in range(6))
    monkeypatch.setattr(apps.AppSetup, 'setup', base)
    monkeypatch.setattr(apps.adb_utils, 'launch_app', launch)
    monkeypatch.setattr(apps.adb_utils, 'close_app', close)
    monkeypatch.setattr(apps.adb_utils, 'grant_permissions', grant)
    monkeypatch.setattr(apps.adb_utils, 'issue_generic_request', query)
    monkeypatch.setattr(apps.time, 'sleep', sleep)
    return env, base, launch, close, grant, query, sleep


def test_waits_for_first_launch_preferences_before_closing_and_granting(setup):
    env, base, launch, close, grant, query, sleep = setup
    def read():
        assert not close.called
        return [response(b'No such file', 2), response(b'<map>'), response(READY)]
    query.side_effect = read()
    apps.SimpleCalendarProApp.setup(env)
    base.assert_called_once_with(env)
    launch.assert_called_once_with('simple calendar pro', env.controller)
    close.assert_called_once_with('simple calendar pro', env.controller)
    assert query.call_count == 3 and sleep.call_count == 2
    query.assert_called_with(['shell', 'cat', '/data/data/com.simplemobiletools.calendar.pro/shared_prefs/Prefs.xml'], env.controller)
    assert [call.args[1] for call in grant.call_args_list] == [
        'android.permission.READ_CALENDAR', 'android.permission.WRITE_CALENDAR',
        'android.permission.POST_NOTIFICATIONS']


@pytest.mark.parametrize('body,status', [
    (b'', 1), (b'<map/>', 1), (b'<map><set name="display_event_types"/></map>', 1),
    (b'<map><set name="display_event_types"><string>2</string></set></map>', 1),
    (b'<map><set name="unrelated"><string>1</string></set></map>', 1),
    (READY, 2),
])
def test_uninitialized_or_failed_query_cannot_be_snapshotted(setup, body, status):
    env, _, _, close, grant, query, sleep = setup
    query.return_value = response(body, status)
    with pytest.raises(RuntimeError, match='event visibility'):
        apps.SimpleCalendarProApp.setup(env)
    assert query.call_count == 30 and sleep.call_count == 30
    close.assert_called_once_with('simple calendar pro', env.controller)
    grant.assert_not_called()


def test_ready_preferences_do_not_toggle_or_rewrite_visibility(setup):
    env, _, _, close, _, query, sleep = setup
    query.return_value = response()
    apps.SimpleCalendarProApp.setup(env)
    assert query.call_count == 1
    sleep.assert_not_called()
    close.assert_called_once()


def test_transport_error_closes_app_and_propagates(setup):
    env, _, _, close, grant, query, _ = setup
    query.side_effect = OSError('transport failed')
    with pytest.raises(OSError, match='transport failed'):
        apps.SimpleCalendarProApp.setup(env)
    close.assert_called_once()
    grant.assert_not_called()
