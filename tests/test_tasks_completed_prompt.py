"""Completed-task questions retain an explicit due date without changing grading.

All fixtures are synthetic and device setup is mocked.
"""
import random
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from android_world import registry
from android_world.task_evals import task_eval
from android_world.task_evals.information_retrieval import (
    information_retrieval as ir, proto_utils, task_app_utils,
)
from android_world.task_evals.information_retrieval.proto import task_pb2, state_pb2


def task_type(name='TasksCompletedTasksForDate'):
    reg = registry.TaskRegistry()
    return reg.get_registry(reg.ANDROID_WORLD_FAMILY)[name]


def params(date):
    return {'date': date, 'completed_date': 'October 09 2023',
            'title': 'Invented planning task', 'notes': 'Invented note',
            'time': '10am', 'seed': 781}


@pytest.fixture
def offline(monkeypatch):
    def initialize(task, env):
        task.initialized = True
        random.seed(task.params['seed'])
    monkeypatch.setattr(task_eval.TaskEval, 'initialize_task', initialize)
    setup = Mock()
    monkeypatch.setattr(ir.task_app_utils, 'setup_task_state', setup)
    return SimpleNamespace(interaction_cache=''), setup


def test_two_tuesdays_remain_distinct_even_when_rewording_collides(monkeypatch, offline):
    env, _ = offline
    monkeypatch.setattr(ir.datetime_utils_ir, 'generate_reworded_date', lambda _: 'Tuesday')
    goals = []
    for date in ('October 10 2023', 'October 17 2023'):
        task = task_type()(params(date))
        task.initialize_task(env)
        goals.append(task.goal)
        assert f'completed tasks have a due date of {date}' in task.goal
        assert 'Tuesday' not in task.goal
        assert {row.due_date for row in task.task.relevant_state.state.tasks_app.tasks_app_tasks} == {date}
        assert {row.completed_date for row in task.task.relevant_state.state.tasks_app.tasks_app_tasks} == {'October 09 2023'}
    assert goals[0] != goals[1]


def test_rewording_preserves_state_grading_and_rng_consumption(offline):
    env, setup = offline
    original_params = params('October 17 2023')
    baseline = task_pb2.Task()
    baseline.CopyFrom(task_type()(original_params.copy()).task)
    random.seed(original_params['seed'])
    proto_utils.initialize_proto(baseline, original_params)
    ir._maybe_replace_date(original_params)
    expected_rng = random.getstate()

    task = task_type()(params('October 17 2023'))
    task.initialize_task(env)
    assert random.getstate() == expected_rng
    assert task.task == baseline
    assert task.params == {**original_params, 'date': 'October 17 2023'}
    setup.assert_called_once_with(task.task.relevant_state.state.tasks_app,
                                 list(task.task.relevant_state.exclusion_conditions), env)
    expected = proto_utils.get_expected_answer(task.task)
    env.interaction_cache = ', '.join(expected)
    assert task.is_successful(env) == 1.0
    for extra in ('Invented wrong-date completed task', 'Invented incomplete task'):
        env.interaction_cache = ', '.join([*expected, extra])
        assert task.is_successful(env) == 0.0
        env.interaction_cache = ', '.join([*expected[:-1], extra])
        assert task.is_successful(env) == 0.0

    # Existing exclusion keeps any task due on the answer date out of noise,
    # including incomplete tasks; other-date completed noise remains possible.
    conditions = list(task.task.relevant_state.exclusion_conditions)
    incomplete = task_app_utils.create_task_from_proto(state_pb2.TasksAppTask(
        title='Invented incomplete task', due_date='October 17 2023'))
    wrong_date = task_app_utils.create_task_from_proto(state_pb2.TasksAppTask(
        title='Invented wrong-date completed task', due_date='October 10 2023',
        completed_date='October 09 2023'))
    assert not task_app_utils.check_task_conditions(incomplete, conditions)
    assert task_app_utils.check_task_conditions(wrong_date, conditions)


def test_unrelated_task_keeps_normal_rewording(monkeypatch, offline):
    env, _ = offline
    task = task_type('TasksDueOnDate')(params('October 17 2023'))
    monkeypatch.setattr(ir.datetime_utils_ir, 'generate_reworded_date', lambda _: 'Tuesday')
    task.initialize_task(env)
    assert task.params['date'] == 'Tuesday'
    assert 'Tuesday' in task.goal
    assert 'October 17 2023' not in task.goal
