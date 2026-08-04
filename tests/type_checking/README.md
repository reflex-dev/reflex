# Type-checking examples

Reflex code whose *inferred types* are part of the public contract. Every file
here must type-check cleanly under every checker in `tests/units/test_type_checking.py`.

These are not runtime tests. Nothing here is executed; the assertions are
`typing.assert_type` calls, which each checker verifies statically. That makes
them checker-agnostic: the same file proves the contract to pyright, ty, and
anything added later.

Write an example here when the thing worth protecting is what a user's editor
shows, rather than what the code does:

- an overload set that must resolve to a specific return type
- a decorator that must preserve a signature
- a generic whose parameter must be solved from context

Files are named for the module they cover (`vars.py` for `reflex/vars/`).
They must not be named `test_*.py`, or pytest will try to collect them.

## Adding a checker

Add an entry to `CHECKERS` in `tests/units/test_type_checking.py`. Each entry
needs a way to invoke the checker and a way to read a pass/fail out of it. A
checker that is not installed is skipped, so a missing optional tool does not
fail the suite.
