"""Synthetic task-row serialization; no device access or saved-run replay."""
import dataclasses
from unittest.mock import patch

import pytest
from android_world.task_evals.information_retrieval import calendar_utils, task_app_utils
from android_world.task_evals.information_retrieval.proto import state_pb2


@pytest.mark.parametrize('due_time', ['', '14:20'])
def test_creation_is_one_week_before_due_and_other_fields_are_preserved(due_time):
    proto = state_pb2.TasksAppTask(
        title='Invented workshop preparation', notes='Bring sample materials',
        importance='1', due_date='November 21 2023', due_time=due_time,
        hide_until_date='November 13 2023', hide_until_time='08:15',
        completed_date='November 12 2023', completed_time='16:30')
    before = proto.SerializeToString()
    with patch.object(task_app_utils.uuid, 'uuid4') as uuid4:
        uuid4.return_value.int = 12345
        row = task_app_utils.create_task_from_proto(proto)
    due = calendar_utils.convert_datetime_to_unix_ts(proto.due_date, due_time or '12pm') * 1000
    due += 1000 if due_time else 0
    created = due - 604800000
    assert row.dueDate - row.created == 604800000
    assert row.modified == row.created == created
    # Assert the complete row, not just dates, so unrelated serialization cannot
    # drift along with the units fix. The input proto used by grading is intact.
    expected = task_app_utils.sqlite_schema_utils.Task(
        title=proto.title, notes=proto.notes, importance=1, dueDate=due,
        hideUntil=calendar_utils.convert_datetime_to_unix_ts(
            proto.hide_until_date, proto.hide_until_time) * 1000 + 1000,
        completed=calendar_utils.convert_datetime_to_unix_ts(
            proto.completed_date, proto.completed_time) * 1000,
        created=created, modified=created, remoteId='12345', recurrence=None)
    assert dataclasses.asdict(row) == dataclasses.asdict(expected)
    assert proto.SerializeToString() == before
    # This narrow units repair does not impose new chronological constraints.
    assert row.completed < row.created
    assert row.hideUntil < row.created


def test_incomplete_task_keeps_unset_completion():
    proto = state_pb2.TasksAppTask(title='Invented pending task', due_date='November 21 2023')
    row = task_app_utils.create_task_from_proto(proto)
    assert row.completed == 0
    assert row.dueDate - row.created == 7 * 24 * 3600 * 1000
