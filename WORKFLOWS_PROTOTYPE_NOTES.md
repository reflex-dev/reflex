# Workflows prototype: reflex side

Branch `claude/project-thread-nm3bkx`, for the P-ENG-582 demo. The full notes
(status, deviations, PR split, runbook) are in flexgen's
`WORKFLOWS_PROTOTYPE_NOTES.md` on the same branch name. This file records what
is specific to this repo.

## What is here

- **ENG-13935** (`packages/reflex-workflow`):
  - `Workflow.start(first, *, key=None)` inserts with
    `ON CONFLICT (key) DO NOTHING`, so `False` means only "a run with this key
    exists".
  - A clash on any other unique constraint raises `RunConflict`, with its
    `.constraint`.
  - `handles.key_column` refuses a `key=` that is not one column unique on its
    own.
  - Tests are in `tests/units/reflex_workflow/engine/test_handles.py`. They need
    `REFLEX_TEST_POSTGRES`.
- **ENG-13936** (`packages/reflex-build-sdk/src/reflex_build_sdk/triggers.py`), stdlib only:
  - `sign` and `verify` in the Standard Webhooks format: multiple signatures
    per message, a `whsec_` key prefix, 300 s of tolerance;
  - `parse_delivery`;
  - `EntryPoints` and `EntryPoint`, with `build`, `describe` and `manifest`;
  - `reply` and `Result`.
  - Tests are in `tests/units/reflex_build_sdk/test_triggers.py`. They pin a
    wire fixture that flexgen's `tests/unit/services/triggers/test_wire.py`
    reproduces byte for byte.

## Deviations and corners

- The `key=` tests run on Postgres only. The ticket asked for SQLite too, but the
  engine's insert is `pg_insert`.
- The wire format is versioned (`{"version": 1, "events": [...]}`, and the
  manifest has `version: 1`). The reply is a plain `{event_id: RESULT}` map.
- `EntryPoint.describe` names the workflow from the step function's
  `__qualname__`, which is the class that owns the step.
- Neither package is released. flexgen pins both by git revision until
  ENG-13484.
- The README examples are not executed in tests.
