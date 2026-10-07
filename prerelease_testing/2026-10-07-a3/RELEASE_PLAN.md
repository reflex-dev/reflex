# Release plan after the 0.10.0a3 re-verification (reflex / reflex-base 0.10.0a3 + reflex-enterprise 0.9.7a5)

**Status: DRAFT** — written at 2026-10-07 ~22:25 UTC after every exploration item finished; the independent verifications of
A3-06..A3-10 are in; A3-11/A3-12's is still running and may change the triage below. Rubric (testing skill): fix before release =
confirmed regression vs the previous stable (0.9.12), security-relevant, significant user impact, or trivially small. Evidence:
[FINDINGS.md](./FINDINGS.md). Supersedes [../2026-10-07/RELEASE_PLAN.md](../2026-10-07/RELEASE_PLAN.md) for everything it re-checked.

## The a2-pass must-fix list: all resolved

| finding | a3 result |
|---|---|
| N-001 `reflex[db]` without greenlet | fixed (#7466) — fresh installs on 3.11–3.14, uv and pip |
| N-025 prod AG Grid Var `column_defs` empty | fixed with **reflex-enterprise 0.9.7a5** (enterprise#273); still broken with enterprise 0.9.7a4 on any 0.10 reflex — the 0.10.0 release notes / enterprise notes should tell users to upgrade both |
| N-032 OIDC cross-tab logout | fixed by reflex #7493 (a5 alone does not fix it) |
| N-004 0.10 state unreadable by 0.9 | behaves exactly as the #7494 breaking-change note says |
| N-005 plain default drops storage | fixed for `str` values (#7495); gap A3-02 |
| N-039 patch/restore of a var default | fixed (#7495); edge cases A3-01 |
| N-008 dev guard accepts `_x__y` | fixed (#7495) |
| N-006, N-002, N-007, N-009, N-024, N-040 docs | fixed / documented (#7496); gaps A3-06 |
| F-014 `reflex component` message | fixed (#7497) |

No upgrade regression 0.9.12 → a3 or a2 → a3; F-002/F-003/F-004 stay fixed; events suite and the third-party sweep equal a2.

## Fix before release

- **A3-11** (MEDIUM, regression vs a2, NOT vs 0.9.12; verification running) — `sync=True` LocalStorage: #7493's boot echo writes back the
  value a tab read at connect time, so changing the value in one tab while other tabs boot starts an endless cross-tab ping-pong (tens of
  thousands of frames per 5 s, backend 50–70 % CPU, the user's last value lost). It does not meet the strict "regression vs the previous
  stable" arm (0.9.12 storms 9/10), but #7493 reintroduced it in a release that had removed it, it burns server CPU indefinitely, and the
  fix is local to the boot echo (do not re-send a client-storage value the browser itself just sent, or have the frontend skip an echo of
  the value it sent at boot). **Maintainer decision:** fix in 0.10.0, or ship with 0.9.12 parity and file it with A3-12.
- **A3-01** (LOW, regression vs a2; CONFIRMED) — trivially small arm: in `BaseStateMeta.__setattr__`, push the "kept default" undo entry
  before `_keep_client_storage` / `_accepts_default` can raise (so a rejected `mock.patch.object` / pytest-mock patch round-trips), and
  make `__delattr__` and the identity restore pop only an entry that the same patch pushed. The docs already promise the round trip.
- **A3-06** (LOW, docs; CONFIRMED by a verifier and found independently by two clusters) — add to the upgrade guide's background-task
  section and the #7312 changelog entry: "Writing a var inherited from a parent state outside `async with self` — directly or through any
  handler — now raises `ImmutableStateError`. On 0.9 it raised nothing: with the in-memory state manager the write landed without the lock,
  with Redis it was silently lost."
- **A3-03** (LOW, docs; NARROWED) — one sentence in base_vars.md / the #7495 changelog example: a named storage var's key is shared by every
  ComponentState instance; use a per-instance `name=` or an unnamed storage var for per-instance persistence.

## File as issues, fix after release

### reflex
- A3-12 (MEDIUM, pre-existing on 0.9.12/a2/a3) concurrent `sync=True` writes from several tabs loop forever (file together with A3-11 if
  A3-11 is deferred).
- A3-02 (LOW) `None` / non-str values assigned to a storage var drop storage (extend the N-005 fix; related to #7498).
- A3-13 (LOW, perf, same as 0.9.12) storage-dependent computed vars evaluated twice per page load (second boot delta).
- A3-07 (LOW, pre-existing; CONFIRMED) `reflex run --json` ignores a pid-only SIGINT; under supervisord `stopsignal=INT` the stop SIGKILLs only
  the supervisor and leaves the app serving as orphans that block the restart. Small fix: forward SIGINT like SIGTERM in `log.py:519`.
- A3-08 (LOW; CONFIRMED, second trigger: a second Ctrl-C during the drain) #7428's drain cap ends the JSON stream mid-record (one
  blocking write of the whole batch on a daemon thread); a consumer that stops reading blocks shutdown forever on every version.
- A3-04 (LOW, pre-existing) class-default assign/restore is not thread-safe.
- A3-05 — not new: add the render-crash symptom and the import-first workaround to reflex#7479.
- N-006 remainder (silent `str()` / `%s` / `!s` paths, cryptic `id=` error) — part of the filed N-006 follow-up if not already.

### reflex-enterprise
- A3-10 (MEDIUM, pre-existing; CONFIRMED and broadened: with `sync=True` two open tabs suffice) — filed [reflex-enterprise#274](https://github.com/reflex-dev/reflex-enterprise/issues/274).
- N-033 (HIGH, pre-existing) — still open as [reflex-enterprise#262](https://github.com/reflex-dev/reflex-enterprise/issues/262) (a3 re-check commented).
- A3-09 (LOW, cosmetic; NARROWED: 0.9.12 only redirects when a race goes its way, and a live cross-tab logout blanks without redirect on
  every version) — redirect to the login page after `reconcile_tokens_after_sync` resets a protected page. File with #261 closure or separately.
- reflex-enterprise#261 (N-032's enterprise side) can be closed: fixed by reflex #7493 on 0.10.0a3.

## Stable line
- Stock `pip install 'reflex[db]'` still resolves 0.9.12 + SQLAlchemy 2.1.4 without greenlet (N-001 for every 0.9.x user today). A 0.9.13
  carrying #7466 fixes it.
