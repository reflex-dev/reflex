# Type-checking examples

Reflex code whose *inferred types* are part of the public contract. Every file
here must type-check cleanly under every checker CI runs.

These are not runtime tests. Nothing here is executed; the assertions are
`typing.assert_type` calls, which each checker verifies statically. That makes
them checker-agnostic: the same file proves the contract to pyright, ty, and
anything added later.

Both checkers gate this directory through pre-commit. The `pyright` hook is
passed the files being committed, so locally it sees these examples only when
they change; CI runs `pre-commit run --all-files`, where it sees all of them.
The `ty` hook always runs over this directory regardless of what changed, since
what these examples catch is a source edit elsewhere altering an inferred type.

Write examples that hold across the whole supported range, so `assert_type`
comes from `typing_extensions` rather than `typing`, which only grew it in
3.11. Note that neither hook currently enforces that: `ty` pins 3.14 and
pyright uses the running interpreter, so a 3.11+ construct would pass both
while breaking a user on the 3.10 floor. Pointing `--python-version` at the
floor instead would close that, at the cost of not checking the version most
contributors develop on.

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
