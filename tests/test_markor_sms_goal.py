"""Expose the existing terminal-state requirement without changing grading."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from android_world.task_evals.composite import markor_sms
from android_world.task_evals.common_validators import sms_validators

PARAMS={'file_name':'example.txt','text':'Better late than never.','number':'+13660435839'}


def test_goal_discloses_existing_foreground_requirement_without_changing_params():
    task=markor_sms.MarkorCreateNoteAndSms(dict(PARAMS))
    assert task.goal.endswith('Leave Simple SMS Messenger as the foreground app when finished.')
    assert 'example.txt' in task.goal and PARAMS['text'] in task.goal and PARAMS['number'] in task.goal
    assert task.params == PARAMS
    assert task.complexity == 1.8


@pytest.mark.parametrize('package,messages,expected',[
    ('com.simplemobiletools.smsmessenger',['valid'],1.0),
    ('net.gsantner.markor',['valid'],0.5),
    ('com.simplemobiletools.smsmessenger',[],0.5),
    ('net.gsantner.markor',[],0.5),
])
def test_composite_retains_sms_sent_and_foreground_checks(monkeypatch,package,messages,expected):
    env=SimpleNamespace(controller=Mock())
    task=markor_sms.MarkorCreateNoteAndSms(dict(PARAMS));task.initialized=True
    task.markor_task=Mock();task.markor_task.is_successful.return_value=1.0
    sms=sms_validators.SimpleSMSSendSms({'number':PARAMS['number'],'message':PARAMS['text']})
    sms.initialized=True
    task.sms_task=sms
    monkeypatch.setattr(sms,'get_sent_messages',lambda controller:messages)
    monkeypatch.setattr(sms,'get_android_time',lambda controller:1000000)
    monkeypatch.setattr(sms_validators.time,'sleep',lambda seconds:None)
    monkeypatch.setattr(sms_validators.adb_utils,'get_current_activity',lambda controller:(package+'/MainActivity',))
    monkeypatch.setattr(sms_validators,'_check_if_stuck_at_sending',lambda env:False)
    monkeypatch.setattr(sms_validators,'was_sent',lambda rows,**kwargs:rows==['valid'])
    assert task.is_successful(env)==expected


@pytest.mark.parametrize('body,address,age,expected',[
    ('Better late than never.','+13660435839',0,True),
    ('Better late than never..','+13660435839',0,True),
    ('Unrelated message','+13660435839',0,False),
    ('Better late than never.','+19999999999',0,False),
    ('Better late than never.','+13660435839',301000,False),
])
def test_sms_content_recipient_and_time_constraints_are_unchanged(body,address,age,expected):
    now=1000000
    records=[f'Row: 0 _id=1, address={address}, date={now-age}, body={body}']
    assert sms_validators.was_sent(records,PARAMS['number'],PARAMS['text'],now) is expected
