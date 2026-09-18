# App setup, task generation, and grading fixes

These corrections support the existing Android 13/API 33 environment and align
generated tasks with their displayed requests and native app data formats. Task
action budgets and required outcomes are preserved.

## App initialization and snapshots

- Disable Monkey's physical system-key event category for launch-only commands.
  This avoids launch failures on emulators without physical system keys while
  retaining the single requested app-launch event.
- Accept Contacts' straight or curly apostrophe in the notification denial
  button. If the dialog is absent, require an explicit denied notification
  permission from the package manager.
- Handle absent Markor, Gallery, and VLC storage-permission screens only when
  the requested all-files access is already granted. Gallery and VLC distinguish
  UID-level and package-level app-op modes.
- Handle an absent SMS role chooser only when Simple SMS Messenger already owns
  the SMS role for Android user 0.
- Clear OpenTracks app data before onboarding, verify both Bluetooth grants when
  its permission dialog is absent, and close the app even when setup raises.
- Wait for Calendar's default event type to be visible in persisted preferences
  before saving its initial state. Fail setup if initialization does not finish.
- Store app snapshots under `/data/local/tmp/android_world/snapshots`, outside
  package-manager-controlled app data. Save and restore use the same root.
  Regenerate snapshots using normal app setup after adopting this location;
  restoration does not silently fall back to the old directory.

## Task requests and grading

- Check the exact requested audio filename rather than appending a second
  `.m4a`. Missing, differently named, and double-extension-only files fail.
- Treat the exact terminal `. Reimbursable.` annotation in generated Markor
  expense notes as selection metadata. Accept copied notes with or without that
  annotation while retaining the original note body, all other expense fields,
  the exact requested additions, and preservation of existing rows.
- Use `next <weekday>` and `last <weekday>` for dates exactly one week away,
  avoiding wording that can also refer to the current day.
- Retain the full requested date in completed-task questions. Keep the
  original request template, normal random-number consumption, and generated
  answer criteria unchanged.
- Match the `skate boarding` and `snow boarding` category names used by task
  templates, so category/date exclusions apply to generated distractors.

## Native Tasks timestamps

Tasks 13.6.3 (versionCode 130605) uses a seconds marker to distinguish an explicit
time from a date-only value. Encode due/start times with second 1, date-only due
dates at local noon, and date-only start dates at local midnight. Completion
timestamps retain their ordinary encoding. This prevents an unchanged editor
from normalizing injected start dates and presenting a spurious discard dialog.

Calculate the creation timestamp one week before the due timestamp in
milliseconds: `7 * 24 * 3600 * 1000`. The generated semantic dates, titles,
completion status, and answer predicates remain unchanged.

## Validation

The regression tests use synthetic data and mocked device access. They cover
visible and absent permission dialogs, denied or unknown grants, setup cleanup,
snapshot location, exact filenames, expense integrity, date wording, category
exclusions, and native timestamp normalization.

After installing the repository dependencies and generating protobuf bindings:

```sh
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. \
  android_world/task_evals/information_retrieval/proto/state.proto \
  android_world/task_evals/information_retrieval/proto/task.proto

python -m pytest -q tests \
  android_world/env/adb_utils_test.py \
  android_world/env/setup_device/setup_test.py \
  android_world/task_evals/information_retrieval \
  android_world/task_evals/single/audio_recorder_test.py \
  android_world/task_evals/single/expense_test.py \
  android_world/task_evals/composite/markor_sms_test.py \
  android_world/utils/datetime_utils_test.py
```

The tests do not require an emulator or a model session. Generated protobuf
bindings are build artifacts and are not part of the source changes.
