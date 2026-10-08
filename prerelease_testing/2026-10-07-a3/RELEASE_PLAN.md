# Release plan after the 0.10.0a3 re-verification (reflex / reflex-base 0.10.0a3 + reflex-enterprise 0.9.7a5)

**Status: FINAL (#7505 merged as 03a2e95e7, #7513 as 9b81d8c3f; class-default assignment backed out by #7516, in review)** — every exploration item and all four independent verifications (A3-01..A3-12) are in. Rubric (testing skill): fix before release =
confirmed regression vs the previous stable (0.9.12), security-relevant, significant user impact, or trivially small. Evidence:
[FINDINGS.md](./FINDINGS.md). Supersedes [../2026-10-07/RELEASE_PLAN.md](../2026-10-07/RELEASE_PLAN.md) for everything it re-checked.

## The a2-pass must-fix list: all resolved

| finding | a3 result |
|---|---|
| N-001 `reflex[db]` without greenlet | fixed (#7466) — fresh installs on 3.11–3.14, uv and pip |
| N-025 prod AG Grid Var `column_defs` empty | fixed with **reflex-enterprise 0.9.7a5** (enterprise#273); still broken with enterprise 0.9.7a4 on any 0.10 reflex — the 0.10.0 release notes / enterprise notes should tell users to upgrade both |
| N-032 OIDC cross-tab logout | fixed by reflex #7493 (a5 alone does not fix it) |
| N-004 0.10 state unreadable by 0.9 | behaves exactly as the #7494 breaking-change note says |
| N-005 plain default drops storage | fixed for `str` values (#7495); gap A3-02. **Superseded 10-08:** #7516 backs class-level default assignment out, so the case no longer exists (assignment raises; storage defaults are set as storage values on the field) |
| N-039 patch/restore of a var default | fixed (#7495); edge cases A3-01. **Superseded 10-08:** #7516 backs the feature out; patching a var on the class raises, tests patch the field |
| N-008 dev guard accepts `_x__y` | fixed (#7495) |
| N-006, N-002, N-007, N-009, N-024, N-040 docs | fixed / documented (#7496); gaps A3-06 |
| F-014 `reflex component` message | fixed (#7497) |

No upgrade regression 0.9.12 → a3 or a2 → a3; F-002/F-003/F-004 stay fixed; events suite and the third-party sweep equal a2.

## Fix before release

- **A3-11 + A3-12** (MEDIUM; A3-11 regression vs a2, not vs 0.9.12; A3-12 pre-existing; both CONFIRMED by an independent verifier, A3-11
  wider than first reported: one change with 3 tabs over a real network, e.g. a session restore, loops forever at ~72 % backend CPU and
  can leave localStorage on the old value; A3-12 is set off by any dev save/deploy/restart with ≥4 tabs whose on_load stamps a synced
  var). **Decided 10-07: fix in 0.10.0** — [reflex-dev/reflex#7505](https://github.com/reflex-dev/reflex/pull/7505) (frontend only: a
  synced var's echo is written back only over a value the tab itself stored after sending it, storage events send the value stored
  when the sync is sent; 4cfafa359: 0 storms and full convergence in 37/37 matrix runs dev/prod incl. 100 ms RTT and dev reload;
  2063422c8 limits echo skipping to `sync=True` vars after review found a lost handler write for a `sync=False` var, re-run 8/8
  converge; Playwright regression tests fail on main). Two intermediate designs were rejected during review (one reintroduced the
  storm, one lost a value when the socket reply beat the `storage` event) — [a3_hydration/pr7505/NOTES.md](./a3_hydration/pr7505/NOTES.md).
- **A3-01** (LOW, regression vs a2; CONFIRMED) — PR #7512 closed 10-08: the maintainer decided to back class-level default assignment out of 0.10 instead ([review](https://github.com/reflex-dev/reflex/pull/7512)). **[reflex-dev/reflex#7516](https://github.com/reflex-dev/reflex/pull/7516)** removes the #7461/#7495 assignment layer; `BaseStateMeta.__setattr__` now raises `TypeError` on an assignment over a state var (a ClassVar or new name is fine), defaults are set with `State.__fields__[name].default`, tests patch the field. Breaking vs 0.9.12 (which silently accepted the assignment), documented in the upgrade guide. Original plan, trivially small arm: in `BaseStateMeta.__setattr__`, push the "kept default" undo entry
  before `_keep_client_storage` / `_accepts_default` can raise (so a rejected `mock.patch.object` / pytest-mock patch round-trips), and
  make `__delattr__` and the identity restore pop only an entry that the same patch pushed. The docs already promise the round trip.
- **A3-06** (LOW, docs; CONFIRMED by a verifier and found independently by two clusters) — **merged 10-08 as [reflex-dev/reflex#7513](https://github.com/reflex-dev/reflex/pull/7513)**: add to the upgrade guide's background-task
  section and the #7312 changelog entry: "Writing a var inherited from a parent state outside `async with self` — directly or through any
  handler — now raises `ImmutableStateError`. On 0.9 it raised nothing: with the in-memory state manager the write landed without the lock,
  with Redis it was silently lost."
- **A3-03** (LOW, docs; NARROWED) — PR #7514 closed 10-08, the caveat folded into #7516's ComponentState docs (`cls.__fields__["theme"].default = rx.LocalStorage(initial, name=f"theme_{key}")`). Original plan: one sentence in base_vars.md / the #7495 changelog example: a named storage var's key is shared by every
  ComponentState instance; use a per-instance `name=` or an unnamed storage var for per-instance persistence.

## File as issues, fix after release

### reflex
- A3-12 — fixed together with A3-11 by #7505; no issue needed.
- Several `sync=True` vars sharing one storage `name` only sync the last one (pre-existing, found reviewing #7505) — filed
  [reflex-dev/reflex#7506](https://github.com/reflex-dev/reflex/issues/7506).
- A3-02 — filed [#7507](https://github.com/reflex-dev/reflex/issues/7507) (moot if #7516 lands: class assignment raises). (LOW) `None` / non-str values assigned to a storage var drop storage (extend the N-005 fix; related to #7498).
- A3-13 — filed [#7508](https://github.com/reflex-dev/reflex/issues/7508). (LOW, perf, same as 0.9.12) storage-dependent computed vars evaluated twice per page load (second boot delta).
- A3-07 — filed [#7509](https://github.com/reflex-dev/reflex/issues/7509). (LOW, pre-existing; CONFIRMED) `reflex run --json` ignores a pid-only SIGINT; under supervisord `stopsignal=INT` the stop SIGKILLs only
  the supervisor and leaves the app serving as orphans that block the restart. Small fix: forward SIGINT like SIGTERM in `log.py:519`.
- A3-08 — filed [#7510](https://github.com/reflex-dev/reflex/issues/7510). (LOW; CONFIRMED, second trigger: a second Ctrl-C during the drain) #7428's drain cap ends the JSON stream mid-record (one
  blocking write of the whole batch on a daemon thread); a consumer that stops reading blocks shutdown forever on every version.
- A3-04 — filed [#7511](https://github.com/reflex-dev/reflex/issues/7511) (moot if #7516 lands). (LOW) class-default assign/restore is not thread-safe.
- A3-05 — not new: symptom and import-first workaround added to [reflex#7479](https://github.com/reflex-dev/reflex/issues/7479#issuecomment-6052150382).
- N-006 remainder (silent `str()` / `%s` / `!s` paths, cryptic `id=` error) — added to [reflex#7459](https://github.com/reflex-dev/reflex/issues/7459#issuecomment-6052149625).

### reflex-enterprise
- A3-10 (MEDIUM, pre-existing; CONFIRMED and broadened: with `sync=True` two open tabs suffice) — filed [reflex-enterprise#274](https://github.com/reflex-dev/reflex-enterprise/issues/274).
- N-033 (HIGH, pre-existing) — still open as [reflex-enterprise#262](https://github.com/reflex-dev/reflex-enterprise/issues/262) (a3 re-check commented).
- A3-09 — filed [reflex-enterprise#275](https://github.com/reflex-dev/reflex-enterprise/issues/275). (LOW, cosmetic; NARROWED: 0.9.12 only redirects when a race goes its way, and a live cross-tab logout blanks without redirect on
  every version) — redirect to the login page after `reconcile_tokens_after_sync` resets a protected page. File with #261 closure or separately.
- reflex-enterprise#261 (N-032's enterprise side) can be closed: fixed by reflex #7493 on 0.10.0a3.

## Stable line
- Stock `pip install 'reflex[db]'` still resolves 0.9.12 + SQLAlchemy 2.1.4 without greenlet (N-001 for every 0.9.x user today). A 0.9.13
  carrying #7466 fixes it — tracked as Linear [ENG-13207](https://linear.app/reflex-dev/issue/ENG-13207/cut-reflex-0913-with-the-reflexdb-greenlet-fix-7466) (current cycle, masenf).
