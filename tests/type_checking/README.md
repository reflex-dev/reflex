# Type-checking examples

Reflex code whose *inferred types* are part of the public contract. Every file
here must type-check cleanly under every checker CI runs.

These are not runtime tests. Nothing here is executed; the assertions are
`typing.assert_type` calls, which each checker verifies statically. That makes
them checker-agnostic: the same file proves the contract to pyright, ty, and
anything added later.

ty gates this directory through pre-commit, under two Python versions, because
a name in a class body resolves differently before 3.14's deferred annotations.
The `ty` hook checks the whole project, this directory included, under the 3.11
floor from `requires-python` whenever a Python file changes. The
`ty-type-checking` hook re-checks this directory under 3.14 and always runs,
regardless of what changed, since what these examples catch is a source edit
elsewhere altering an inferred type.

Write examples that hold across the whole supported range: the `ty` hook, at
the 3.11 floor, rejects a 3.12+ construct.

Write an example here when the thing worth protecting is what a user's editor
shows, rather than what the code does:

- an overload set that must resolve to a specific return type
- a decorator that must preserve a signature
- a generic whose parameter must be solved from context

Files are named for the module they cover (`vars.py` for `reflex/vars/`).
They must not be named `test_*.py`, or pytest will try to collect them.

## Adding a checker

Add a hook to `.pre-commit-config.yaml` that runs it over this directory, next
to the `ty-type-checking` one. Nothing else needs to change.
