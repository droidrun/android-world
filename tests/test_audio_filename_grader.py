"""Named audio grading regressions with no live device access."""

import random
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from android_world.env import device_constants
from android_world.task_evals import task_eval
from android_world.task_evals.single import audio_recorder


TASK = audio_recorder.AudioRecorderRecordAudioWithFileName
REQUESTED = "meeting_final.m4a"


@pytest.mark.parametrize("existing_names,score", [
    ({REQUESTED}, 1.0),
    (set(), 0.0),
    ({"other.m4a"}, 0.0),
    ({REQUESTED + ".m4a"}, 0.0),
    ({"meeting_final"}, 0.0),
    ({REQUESTED.upper()}, 0.0),
])
def test_grader_requires_exact_requested_filename(monkeypatch, existing_names, score):
    task = TASK({"file_name": REQUESTED, "text": ""})
    task.initialized = True
    env = SimpleNamespace(controller=Mock())
    exists = Mock(side_effect=lambda name, directory, controller: name in existing_names)
    monkeypatch.setattr(audio_recorder.file_utils, "check_file_or_folder_exists", exists)

    assert task.is_successful(env) == score
    exists.assert_called_once_with(REQUESTED, device_constants.AUDIORECORDER_DATA, env.controller)
    assert task.params == {"file_name": REQUESTED, "text": ""}


def test_seeded_parameters_goal_and_budget_are_unchanged():
    previous_state = random.getstate()
    try:
        random.seed(42)
        params = TASK.generate_random_params()
    finally:
        random.setstate(previous_state)
    assert params == {"file_name": "2023_05_21_debate.m4a", "text": ""}
    task = TASK(params)
    assert task.goal == (
        'Record an audio clip and save it with name "2023_05_21_debate.m4a" '
        'using Audio Recorder app.'
    )
    assert task.params == params
    assert task.complexity == 2


def test_grader_still_requires_initialization(monkeypatch):
    task = TASK({"file_name": REQUESTED, "text": ""})
    exists = Mock()
    monkeypatch.setattr(audio_recorder.file_utils, "check_file_or_folder_exists", exists)
    with pytest.raises(RuntimeError, match="must be called before"):
        task.is_successful(SimpleNamespace(controller=Mock()))
    exists.assert_not_called()


def test_file_inspection_error_propagates(monkeypatch):
    task = TASK({"file_name": REQUESTED, "text": ""})
    task.initialized = True
    monkeypatch.setattr(audio_recorder.file_utils, "check_file_or_folder_exists",
                        Mock(side_effect=RuntimeError("Device unavailable")))
    with pytest.raises(RuntimeError, match="Device unavailable"):
        task.is_successful(SimpleNamespace(controller=Mock()))


def test_setup_and_cleanup_keep_original_sequence(monkeypatch):
    task = TASK({"file_name": REQUESTED, "text": ""})
    env = SimpleNamespace(controller=Mock())
    calls = Mock()
    monkeypatch.setattr(task_eval.TaskEval, "initialize_task", calls.base_initialize)
    monkeypatch.setattr(task_eval.TaskEval, "tear_down", calls.base_teardown)
    monkeypatch.setattr(task.create_file_task, "initialize_task", calls.file_initialize)
    monkeypatch.setattr(task.create_file_task, "tear_down", calls.file_teardown)
    monkeypatch.setattr(audio_recorder.file_utils, "clear_directory", calls.clear)

    task.initialize_task(env)
    task.tear_down(env)

    assert calls.mock_calls == [
        call.base_initialize(env),
        call.file_initialize(env),
        call.clear(device_constants.AUDIORECORDER_DATA, env.controller),
        call.base_teardown(env),
        call.file_teardown(env),
        call.clear(device_constants.AUDIORECORDER_DATA, env.controller),
    ]
