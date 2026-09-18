"""A same-weekday date one week away must not be described as today."""
import datetime as dt
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from android_world import registry
from android_world.env import device_constants
from android_world.task_evals import task_eval
from android_world.task_evals.information_retrieval import datetime_utils, information_retrieval


@pytest.mark.parametrize('weekday', range(7))
@pytest.mark.parametrize('delta,prefix', [(7,'next'),(-7,'last')])
def test_exact_week_alias_is_unambiguous(monkeypatch, weekday, delta, prefix):
    today = dt.datetime(2023,10,16,tzinfo=dt.timezone.utc) + dt.timedelta(days=weekday)
    monkeypatch.setattr(device_constants,'DT',today)
    date = today.date() + dt.timedelta(days=delta)
    name = date.strftime('%A')
    assert datetime_utils._generate_nl_date_options(date.strftime('%B %d %Y')) == [
        date.strftime('%B %d'), date.strftime('%B %d %Y'), f'{prefix} {name}']


@pytest.mark.parametrize('delta', [-15,-14,-8,-6,-1,0,1,2,6,8,14,15])
def test_nonboundary_options_are_preserved(monkeypatch,delta):
    today=dt.datetime(2023,10,15,tzinfo=dt.timezone.utc)
    monkeypatch.setattr(device_constants,'DT',today)
    date=today.date()+dt.timedelta(days=delta);name=date.strftime('%A')
    expected=[date.strftime('%B %d'),date.strftime('%B %d %Y')]
    if delta==0: expected.append('today')
    if delta==1: expected.append('tomorrow')
    if delta==-1: expected.append('yesterday')
    if 0<delta<7: expected += [name,'this '+name]
    elif 7<delta<=14: expected += ['the '+name+' after next']
    elif -7<delta<0: expected.append(name)
    assert datetime_utils._generate_nl_date_options(date.strftime('%B %d %Y'))==expected


def test_wording_change_preserves_underlying_date_and_expected_answer(monkeypatch):
    reg=registry.TaskRegistry()
    task_type=reg.get_registry(reg.ANDROID_WORLD_FAMILY)['SimpleCalendarEventsOnDate']
    task=task_type({'time':'10:30am','date':'October 22 2023','duration':'90 min',
                    'title':'Board meeting','seed':2949225442})
    monkeypatch.setattr(device_constants,'DT',dt.datetime(2023,10,15,tzinfo=dt.timezone.utc))
    monkeypatch.setattr(task_eval.TaskEval,'initialize_task',lambda task,env:setattr(task,'initialized',True))
    monkeypatch.setattr(datetime_utils.random,'choice',lambda options:options[-1])
    setup=Mock()
    monkeypatch.setattr(information_retrieval.calendar_utils_ir,'setup_task_state',setup)
    env=SimpleNamespace(interaction_cache='')
    task.initialize_task(env)
    event=task.task.relevant_state.state.calendar.events[0]
    assert event.start_date=='October 22 2023'
    assert event.title=='Board meeting'
    assert 'next Sunday' in task.goal
    assert 'this Sunday' not in task.goal
    assert task.complexity==1
    setup.assert_called_once()
    env.interaction_cache='Board meeting'
    assert task.is_successful(env)==1.0
    env.interaction_cache='Call with Dr. Smith'
    assert task.is_successful(env)==0.0
