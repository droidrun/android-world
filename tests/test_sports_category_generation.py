"""Same-sport noise must obey the exclusion used to construct the answer."""
import datetime as dt
from types import SimpleNamespace

import pytest
from android_world import registry, suite_utils
from android_world.task_evals import task_eval
from android_world.task_evals.information_retrieval import activity_app_utils as sports
from android_world.task_evals.information_retrieval.proto import state_pb2, task_pb2


@pytest.mark.parametrize('category', ['skate boarding', 'snow boarding'])
@pytest.mark.parametrize('date,allowed', [
    ('October 8 2023', True), ('October 9 2023', False),
    ('October 13 2023', False), ('October 15 2023', False),
    ('October 16 2023', True)])
def test_generated_sport_uses_template_spelling_and_weekly_exclusion(monkeypatch, category, date, allowed):
    choices = [category, sports._CATEGORY_TO_ACTIVITY_NAMES[category][0]]
    monkeypatch.setattr(sports.random, 'choice', lambda _: choices.pop(0))
    when = dt.datetime.strptime(date, '%B %d %Y').replace(tzinfo=dt.timezone.utc)
    monkeypatch.setattr(sports.datetime_utils, 'generate_random_datetime', lambda **_: when)
    row = sports._generate_random_activity()
    assert row.category == row.activity_type == category
    op = task_pb2.ExclusionCondition.Operation
    exclusions = [
        task_pb2.ExclusionCondition(field='category', value=category, operation=op.CONTAINS),
        task_pb2.ExclusionCondition(field='start_date', value='October 9 2023', operation=op.GREATER_THAN_OR_EQUAL_TO),
        task_pb2.ExclusionCondition(field='start_date', value='October 15 2023', operation=op.LESS_THAN_OR_EQUAL_TO)]
    assert sports._check_activity_conditions(row, exclusions) is allowed


def test_distinct_walking_distractor_remains_valid():
    row = sports._create_activity_from_proto(state_pb2.SportsActivity(
        name='Nature Walk', category='walking', start_date='October 13 2023',
        start_time='17:25', duration='94', total_distance='11201'))
    condition = task_pb2.ExclusionCondition(field='category', value='hiking',
        operation=task_pb2.ExclusionCondition.Operation.CONTAINS)
    assert sports._check_activity_conditions(row, [condition])


def test_normal_initialization_has_only_intended_weekly_sport_rows(monkeypatch):
    reg = registry.TaskRegistry()
    name = 'SportsTrackerTotalDurationForCategoryThisWeek'
    cls = reg.get_registry(reg.ANDROID_WORLD_FAMILY)[name]
    env = SimpleNamespace(interaction_cache='')
    monkeypatch.setattr(task_eval.TaskEval, 'initialize_device_time', lambda *_: None)
    monkeypatch.setattr(task_eval.TaskEval, '_initialize_apps', lambda *_: None)
    monkeypatch.setattr(sports, 'clear_db', lambda *_: None)
    captured = []
    monkeypatch.setattr(sports, '_add_activities', lambda rows, env: captured.extend(rows))
    task = suite_utils.create_suite({name: cls}, seed=42, tasks=[name], env=env)[name][0]
    task.initialize_task(env)
    relevant = task.task.relevant_state.state.sports_activity_app.sports_activities
    assert {row.category for row in relevant} == {'skate boarding'}
    expected = sum(int(row.duration) for row in relevant)
    assert expected == 205
    actual = [row for row in captured if row.category.replace(' ', '') == 'skateboarding'
              and dt.date(2023, 10, 9) <= dt.datetime.fromtimestamp(
                  row.starttime / 1000, dt.timezone.utc).date() <= dt.date(2023, 10, 15)]
    assert len(actual) == len(relevant) == 2
    assert sum(row.totaltime / 60000 for row in actual) == expected
    assert {row.name for row in actual} == {row.name for row in relevant}
    env.interaction_cache = str(expected)
    assert task.is_successful(env) == 1.0
    for incorrect in ('304', '509', '0'):
        env.interaction_cache = incorrect
        assert task.is_successful(env) == 0.0
