"""Tasks 13.6.3 native date encoding, using invented offline fixtures only."""
import datetime
from zoneinfo import ZoneInfo

import pytest
from android_world.env import device_constants
from android_world.task_evals.information_retrieval import calendar_utils, proto_utils, task_app_utils
from android_world.task_evals.information_retrieval.proto import state_pb2, task_pb2


def local(timestamp):
    return datetime.datetime.fromtimestamp(timestamp / 1000, ZoneInfo(device_constants.TIMEZONE))


def native_normalize(timestamp, date_only_hour):
    # Task.hasDueTime and TaskEditViewModel.setStartDate / Task.createDueDate
    # at tasks/tasks commit ee21cc660eb5ccea11ed011d23aab33d7e06bb40.
    if timestamp == 0:
        return 0
    value = local(timestamp)
    if timestamp % 60000 > 0:
        value = value.replace(second=1, microsecond=0)
    else:
        value = value.replace(hour=date_only_hour, minute=0, second=0, microsecond=0)
    return int(value.timestamp() * 1000)


@pytest.mark.parametrize('time,hour,minute,timed', [
    ('', 0, 0, False), ('12am', 0, 0, True), ('00:00', 0, 0, True),
    ('08:15', 8, 15, True), ('11:59pm', 23, 59, True)])
def test_native_encoding_retains_dates_times_and_survives_editor_normalization(time, hour, minute, timed):
    proto = state_pb2.TasksAppTask(title='Invented lab preparation',
        due_date='November 21 2023', due_time=time,
        hide_until_date='November 13 2023', hide_until_time=time,
        completed_date='November 12 2023', completed_time=time)
    original = proto.SerializeToString()
    row = task_app_utils.create_task_from_proto(proto)
    for value, date, date_only_hour in (
        (row.dueDate, datetime.date(2023, 11, 21), 12),
        (row.hideUntil, datetime.date(2023, 11, 13), 0)):
        decoded = local(value)
        assert decoded.date() == date
        assert (decoded.hour, decoded.minute, decoded.second) == (
            hour if timed else date_only_hour, minute, 1 if timed else 0)
        assert (value % 60000 > 0) is timed
        assert native_normalize(value, date_only_hour) == value
    assert row.completed == calendar_utils.convert_datetime_to_unix_ts(
        proto.completed_date, time) * 1000
    assert row.completed % 60000 == 0
    assert proto.SerializeToString() == original


def test_absent_dates_stay_zero():
    row = task_app_utils.create_task_from_proto(state_pb2.TasksAppTask(title='Invented undated task'))
    assert (row.dueDate, row.hideUntil, row.completed) == (0, 0, 0)


@pytest.mark.parametrize('time', ['', '12am', '23:59'])
def test_exclusion_dates_and_official_answers_are_unchanged(time):
    proto = state_pb2.TasksAppTask(title='Invented completed task',
        due_date='November 21 2023', due_time=time,
        completed_date='November 12 2023', completed_time='08:30')
    row = task_app_utils.create_task_from_proto(proto)
    op = task_pb2.ExclusionCondition.EQUAL_TO
    for date, eligible in [('November 20 2023', True), ('November 21 2023', False),
                           ('November 22 2023', True)]:
        conditions = [task_pb2.ExclusionCondition(field='due_date', operation=op, value=date)]
        assert task_app_utils.check_task_conditions(row, conditions) is eligible
    assert not task_app_utils.check_task_conditions(row, [task_pb2.ExclusionCondition(
        field='completed_date', operation=op, value='November 12 2023')])
    task = task_pb2.Task()
    task.relevant_state.state.tasks_app.tasks_app_tasks.add().CopyFrom(proto)
    expectation = task.success_criteria.expectations.add(match_type=task_pb2.Expectation.STRING_MATCH)
    expectation.field_transformation.operation = task_pb2.FieldTransformation.IDENTITY
    expectation.field_transformation.field_name = 'title'
    before = task.SerializeToString()
    assert proto_utils.get_expected_answer(task) == [proto.title]
    assert proto_utils.check_agent_answer(proto.title, task)
    assert not proto_utils.check_agent_answer('Invented unrelated title', task)
    assert task.SerializeToString() == before
