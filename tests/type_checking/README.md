# Type-checking examples

Reflex code whose *inferred types* are part of the public contract. Every file
here must type-check cleanly under every checker CI runs.

These are not runtime tests. Nothing here is executed; the assertions are
`typing.assert_type` calls, which each checker verifies statically. That makes
them checker-agnostic: the same file proves the contract to pyright, ty, and
anything added later.

Both checkers gate this directory through pre-commit. The `ty` hook and two
`pyright-type-checking-*` hooks always run over this directory regardless of
what changed, since what these examples catch is a source edit elsewhere
altering an inferred type. `ty` pins Python 3.14; pyright runs once under the
3.11 floor and once under 3.14, because a name in a class body resolves
differently before 3.14's deferred annotations. The plain `pyright` hook also
sees these files, under the running interpreter, when they are committed.

Write examples that hold across the whole supported range: the 3.11 pyright
hook rejects a 3.12+ construct.

Write an example here when the thing worth protecting is what a user's editor
shows, rather than what the code does:

- an overload set that must resolve to a specific return type
- a decorator that must preserve a signature
- a generic whose parameter must be solved from context

Files are named for the module they cover (`vars.py` for `reflex/vars/`).
They must not be named `test_*.py`, or pytest will try to collect them.

## Adding a checker

Add a hook to `.pre-commit-config.yaml` that runs it over this directory, next
to the `ty` one. Nothing else needs to change.
