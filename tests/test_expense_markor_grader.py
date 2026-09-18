"""Offline regressions for Markor's generated reimbursement annotation."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from android_world.task_evals.common_validators import sqlite_validators
from android_world.task_evals.single import expense
from android_world.task_evals.utils.sqlite_schema_utils import Expense


TASK = expense.ExpenseAddMultipleFromMarkor
SUFFIX = ". Reimbursable."


@pytest.fixture
def rows():
    existing = [Expense("Existing lunch", 1300, 3, "Unrelated note", expense_id=1)]
    targets = [
        Expense("Airport taxi", 4750, 7, "Conference travel", expense_id=-1),
        Expense("Office notebook", 1825, 1, "Meeting supplies", expense_id=-1),
    ]
    added = [replace(row, expense_id=100 + index) for index, row in enumerate(targets)]
    return existing, targets, added


def validate(rows, added=None, existing=None, task_class=TASK):
    before, references, defaults = rows
    task = task_class({sqlite_validators.ROW_OBJECTS: references})
    return task.validate_addition_integrity(
        before, (before if existing is None else existing) + (defaults if added is None else added), references
    )


@pytest.mark.parametrize("annotated", [(False, False), (True, True), (True, False), (False, True)])
def test_base_or_visible_annotation_is_accepted_without_mutating_inputs(rows, annotated):
    before, references, added = rows
    copied = [replace(row, note=row.note + SUFFIX) if enabled else row
              for row, enabled in zip(added, annotated)]
    saved = (list(before), list(references), list(copied))
    assert validate(rows, copied)
    assert (before, references, copied) == saved


@pytest.mark.parametrize("note", [
    "", None, "Completely unrelated purchase", "Reimbursable.",
    "Conference travel. Reimbursable",  # Missing final punctuation.
    "Conference travel. reimbursable.",
    "Conference travel.Reimbursable.",
    "Conference travel. Reimbursable. ",
    "Conference travel. Reimbursable. More content",
    "Conference. Reimbursable. travel",
    "Conference travel" + SUFFIX + SUFFIX,
    "Incorrect body" + SUFFIX,
])
def test_wrong_missing_or_nonterminal_note_content_is_not_removed(rows, note):
    added = list(rows[2])
    added[0] = replace(added[0], note=note)
    assert not validate(rows, added)


@pytest.mark.parametrize("changes", [
    {"name": "Unrequested groceries"}, {"amount": 999999}, {"category": 11},
])
def test_annotation_does_not_relax_other_expense_fields(rows, changes):
    added = [replace(row, note=row.note + SUFFIX) for row in rows[2]]
    added[0] = replace(added[0], **changes)
    assert not validate(rows, added)


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate", "replace_with_noise"])
def test_exact_requested_additions_still_required(rows, change):
    added = [replace(row, note=row.note + SUFFIX) for row in rows[2]]
    if change == "missing":
        added.pop()
    elif change == "extra":
        added.append(Expense("Extra purchase", 3000, 1, "Unexpected", expense_id=200))
    elif change == "duplicate":
        added[1] = replace(added[0], expense_id=101)
    else:
        added[1] = Expense("Noise transaction", 3000, 1, "Unexpected", expense_id=101)
    assert not validate(rows, added)


@pytest.mark.parametrize("change", ["append_annotation", "remove_annotation", "other_note", "amount", "deleted"])
def test_original_unrelated_rows_are_checked_before_normalization(rows, change):
    before, references, added = rows
    existing = list(before)
    if change == "append_annotation":
        existing[0] = replace(existing[0], note=existing[0].note + SUFFIX)
    elif change == "remove_annotation":
        before = [replace(before[0], note=before[0].note + SUFFIX)]
        rows = before, references, added
    elif change == "other_note":
        existing[0] = replace(existing[0], note="Unrelated edit")
    elif change == "amount":
        existing[0] = replace(existing[0], amount=1)
    else:
        existing = []
    assert not validate(rows, [replace(row, note=row.note + SUFFIX) for row in added], existing)


def test_preserved_existing_annotation_is_not_normalized(rows):
    before, references, added = rows
    before = [replace(before[0], note=before[0].note + SUFFIX)]
    assert validate((before, references, added))


@pytest.mark.parametrize("annotated", [False, True])
def test_existing_fuzzy_name_and_note_rules_are_preserved(rows, annotated):
    added = [replace(row, name=row.name.upper(), note=row.note.lower() + (SUFFIX if annotated else ""))
             for row in rows[2]]
    assert validate(rows, added)
    if not annotated:
        assert validate(rows, added, task_class=expense.ExpenseAddMultiple)


@pytest.mark.parametrize("task_class", [expense.ExpenseAddSingle, expense.ExpenseAddMultiple,
                                       expense.ExpenseAddMultipleFromGallery])
def test_other_expense_classes_keep_the_original_validator(rows, task_class):
    assert task_class.validate_addition_integrity is expense._ExpenseAddMultiple.validate_addition_integrity
    assert validate(rows, task_class=task_class)
    assert not validate(rows, [replace(row, note=row.note + SUFFIX) for row in rows[2]], task_class=task_class)


def test_initialization_keeps_reference_rows_goal_and_displayed_selection_unchanged(monkeypatch, rows):
    before, references, _ = rows
    params = {sqlite_validators.ROW_OBJECTS: references, sqlite_validators.NOISE_ROW_OBJECTS: before}
    task = TASK(params)
    env = SimpleNamespace(controller=Mock())
    initialize = Mock()
    clear = Mock()
    write = Mock()
    monkeypatch.setattr(expense._ExpenseAddMultiple, "initialize_task", initialize)
    monkeypatch.setattr(expense.file_utils, "clear_directory", clear)
    monkeypatch.setattr(expense.user_data_generation, "write_to_markor", write)
    monkeypatch.setattr(expense.random, "shuffle", lambda items: None)

    task.initialize_task(env)

    initialize.assert_called_once_with(env)
    clear.assert_called_once_with(expense.device_constants.MARKOR_DATA, env.controller)
    expected_rows = [replace(row, note=row.note + SUFFIX) for row in references] + before
    write.assert_called_once_with(expense._get_expense_rows_as_text(expected_rows, "csv"), "my_expenses.txt", env)
    assert task.params == params
    assert references == rows[1] and all(not row.note.endswith(SUFFIX) for row in references)
    assert task.goal == ('Go through the transactions in my_expenses.txt in Markor. Log the '
                         'reimbursable transactions in the pro expense.')
    assert task.complexity == 6 and task.n_rows == 2 and task.n_rows_noise == 100
    assert TASK._REIMBURSABLE_SUFFIX == SUFFIX


def test_official_score_path_uses_class_specific_validator_without_device_access(monkeypatch, rows):
    before, references, added = rows
    task = TASK({sqlite_validators.ROW_OBJECTS: references})
    task.before = before
    list_rows = Mock(return_value=before + [replace(row, note=row.note + SUFFIX) for row in added])
    monkeypatch.setattr(task, "list_rows", list_rows)
    env = SimpleNamespace()
    assert task.is_successful(env) == 1.0
    list_rows.assert_called_once_with(env)
