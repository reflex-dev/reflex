# f003 — FINDING-003 / issue #7212: withheld `@rx.var(cache=False)` is never re-sent

- Worktree: `/home/user/wt/f003` · Branch: `fix/finding-003-delta-memo` · Commit: `600671cee`
- Status: **fixed**, verified end to end (campaign repro fails on published 0.9.12a1, passes on the branch)
- Files changed: `reflex/state.py`, `packages/reflex-base/src/reflex_base/vars/base.py`,
  `tests/units/test_state.py`, `news/+uncached-var-withheld-from-delta.bugfix.md`,
  `packages/reflex-base/news/+uncached-var-withheld-from-delta.bugfix.md`

## Root cause

On `origin/main` (== the published 0.9.12a1 behaviour):

- `reflex/state.py:2385` — `BaseState.get_delta` calls `cvar._record_delta_value(self, value, token)`
  **while building** the subdelta, and `reflex/state.py:382` does the same from
  `_drop_unchanged_delta_value` for async uncached vars.
- `packages/reflex-base/src/reflex_base/vars/base.py:2689` — `ComputedVar._record_delta_value`
  writes `instance.__last_delta_<js_expr> = (token, key)` **immediately** and returns "include it".

Nothing reconciles that write with what actually leaves the override chain. `get_delta` is, by its own
docstring, the method downstream packages monkeypatch (reflex-enterprise 0.9.5 does exactly that in
`reflex_enterprise/auth/enforcement.py:install_delta_filter`, and again in
`reflex_enterprise/auth/oidc/state.py:2501`). A wrapper that **drops** the key, or **replaces** it with
an anonymous placeholder — both of which rxe's `filter_protected_delta` does — leaves the memo claiming
"the client has value V" for a value the client never received. The next event recomputes the same V,
`_record_delta_value` returns `False`, the #6946 dedupe omits it, and the client stays stale until the
value changes again. rxe's `redeliver_protected()` (`auth/enforcement.py:960-995`) re-marks the withheld
names dirty on the assumption that the end-of-event delta re-delivers them; that assumption is exactly
what #6946 broke for `cache=False` vars.

`_suppress_delta_recording()` (`reflex/state.py:317`) was the existing primitive for "this delta is not
delivered", but it is private and only reachable from `reflex/istate/shared.py:122`; a downstream filter
has no way in.

## The fix and why this shape

One rule: **an uncached var value counts as sent only when the delta that carries it is delivered.**

- `ComputedVar._record_delta_value` → `ComputedVar._pending_delta_record` (`vars/base.py:2689`). It still
  owns the memo format and still *reads* the memo to decide whether the value has to be sent, but it no
  longer writes. It returns `None` (unchanged → omit) or `(attr, stored)` — the instance attribute and
  what to put in it once the value has been delivered (`stored is None` for an unkeyable value, whose
  record must be dropped instead).
- `reflex/state.py:317` — new `_DeltaRecord` NamedTuple `(state_name, key, value, instance, attr, stored)`.
- `reflex/state.py:333` — new `_pending_delta_records` ContextVar holding the list of records for the
  delta currently being built (`None` when nobody is collecting).
- `reflex/state.py:2435` — `get_delta` appends to that list instead of recording; `full_name` and the
  delta key are hoisted so the record knows where the value sits. `_drop_unchanged_delta_value`
  (`reflex/state.py:414`) takes the same three extra arguments and appends the *resolved* value after
  awaiting, so async uncached vars are recorded at the object `_resolve_delta` actually puts in the delta.
- `reflex/state.py:2472` — `_get_resolved_delta` installs the collector, awaits
  `_resolve_delta(self.get_delta())`, and then calls `_commit_delta_records` (`reflex/state.py:355`),
  which stores a record **only where `delta[state_name][key] is value`** — the very object that was
  computed. A dropped key, or a key whose value a filter swapped for a placeholder, fails that test and
  is simply owed to the client again.

`_get_resolved_delta` is the chokepoint: every delivery path goes through it and nothing else delivers a
`get_delta` result (`reflex/app.py:1864`, `reflex/istate/proxy.py:223`,
`packages/reflex-base/.../base_state_processor.py:226` — `chain_updates`; hydrate emits `dict()`, not a
delta). Critically, `_get_resolved_delta` calls `self.get_delta()`, so the delta it inspects is the one
that came **back out of the downstream override**, with coroutines resolved — which is precisely the
information the old code lacked. `_suppress_delta_recording` is honoured there now
(`reflex/istate/shared.py:122` keeps working unchanged): no collector is installed, so nothing is recorded.

Identity (`is`), not equality, is the survival test. A filter that passes a value through — including one
that rebuilds the dicts, as both the campaign repro and rxe do — preserves object identity; one that
substitutes a placeholder does not. `a is b` implies the client received exactly what was keyed, so the
check can never record a value that was not delivered. A filter that hands back a *copy* of a value would
lose the dedupe for that var (it would be re-sent every event) but stays correct; that is the safe
direction to fail.

### Alternatives considered and rejected

1. **Roll back the memo in `_get_resolved_delta` instead of deferring it.** Keeps every existing test
   green and fixes the app path — but a bare `get_delta()` (which the campaign's `pure_delta_memo.py`
   repro and any ad-hoc caller use) still commits eagerly with nothing to roll it back, so the verbatim
   repro would still print `False`. Rejected.
2. **Commit eagerly unless `type(self).get_delta is not BaseState.get_delta`** ("nobody can filter me").
   Keeps all existing tests green and fixes the repro, but makes the dedupe two-moded and subtle: whether
   a value counts as sent would depend on whether *some other package* patched a method. Rejected as
   unexplainable, for a rule that cannot be proved anyway (a wrapper on `_get_resolved_delta` defeats it).
3. **A public "forget that I sent this" hook for downstream filters.** Correct long term, but it does not
   fix the already-published reflex-enterprise 0.9.5, which is the reported failure. Worth doing on top,
   not instead.
4. **Finalize at each emit site rather than in `_get_resolved_delta`.** Equivalent today (every site is
   `delta = await _get_resolved_delta(); if delta: emit`), but it would put the same four lines in three
   packages. See "risks" for the one case this would additionally cover.

## Behaviour change: `get_delta()` on its own no longer records

A delta built and not delivered records nothing. Concretely: two consecutive bare `state.get_delta()`
calls now return the uncached var twice, where before the second was deduped away. Nothing in reflex
delivers a delta that way, so this is not user-visible in an app — but it did require updating the #6946
unit tests to drive `await state._get_resolved_delta()` (the real delivery path) instead of
`state.get_delta()`. Their substance is unchanged and all of them still assert the same dedupe:

`test_computed_var_cached_depends_on_non_cached`, `test_uncached_computed_var_unchanged_omitted_from_delta`,
`test_uncached_computed_var_nan_value_not_resent`, `test_uncached_computed_var_records_last_value_for_redis`,
`test_uncached_computed_var_mutable_value_mutated_in_place`,
`test_uncached_computed_var_recorded_per_client_token`,
`test_discarded_delta_does_not_record_values_of_substates`, and the two delta assertions in `test_get_state`.

Two further small changes fall out:

- The `delattr` for an unkeyable value also moves to delivery time. If such a value is withheld, the
  previous (keyable) record now survives — correct, since the client still holds that value — and a
  successful `delattr` now marks the state touched so the removal reaches redis (it did not before).
- Under `_suppress_delta_recording()` the discarded delta is now deduped on read as well (it used to
  include every uncached var). The getters still run and async vars are still awaited, so `shared.py`'s
  "resolve to refresh computed vars" side effect is unchanged; only the discarded dict is smaller.

## Regression test

`tests/units/test_state.py`:

- `test_uncached_var_withheld_by_delta_override_is_resent[dropped|replaced][sync|async]` — a
  `cache=False` var plus a `get_delta` wrapper that, while a flag is set, either deletes the key or
  replaces its value with `"anon"` (the two shapes rxe's `filter_protected_delta` produces). The value
  changes while withheld; when the flag clears, the next delivered delta must carry `secret-1`, and the
  one after that must not (the dedupe still works).
- `test_uncached_computed_var_recorded_only_once_delivered` — the pure `pure_delta_memo.py` invariant:
  building a delta is not delivering it, so a bare `get_delta()` does not consume the value, while
  `_get_resolved_delta()` does.

Before the fix (`evidence/unit_regression_before_fix.txt`, sources reverted to `origin/main`, new tests
kept):

```
FAILED tests/units/test_state.py::test_uncached_var_withheld_by_delta_override_is_resent[False-dropped]
FAILED tests/units/test_state.py::test_uncached_var_withheld_by_delta_override_is_resent[False-replaced]
FAILED tests/units/test_state.py::test_uncached_computed_var_recorded_only_once_delivered
3 failed, 2 passed, 217 deselected
```

with, for the `dropped` case:

```
        withholding = False
>       assert await state._get_resolved_delta() == {full_name: {key: "secret-1"}}
E       AssertionError: assert {} == {'reflex___is...: 'secret-1'}}
```

After the fix (`evidence/unit_regression_after_fix.txt`): `13 passed` for
`-k "withheld_by_delta_override or recorded_only_once_delivered or uncached"`.

The two `is_async=True` cases pass **before and after**: a wrapper that filters the coroutine out of the
delta closes it before `_resolve_delta` can await it, so the async path never reached the memo. They are
kept as a guard on the new `_drop_unchanged_delta_value` signature.

## End-to-end verification

### 1. Pure-python repro, verbatim (only the `/envs/` assert removed)

`evidence/pure_delta_memo.py`, run from `/tmp/.../scratchpad/fixes/f003`:

| | published 0.9.12a1 (`envs/shared/bin/python`) | fixed worktree (`/home/user/wt/f003/.venv/bin/python`) |
| --- | --- | --- |
| 3 after login | `False` | **`True`** (`shared_label_rx_state_: 'shared=SERVER-ONLY-SECRET'`) |
| 4 after another event | `False` | **`True`** |

`evidence/pure_delta_memo.published-0.9.12a1.txt`, `evidence/pure_delta_memo.fixed-worktree.txt`.

### 2. Browser repro (`event_loop/elapp` page `/filtered`, `scripts/s_filtered.py`)

Apps copied to scratch, dev mode, ports 3920/8920 (fixed worktree venv), 3921/8921 (published
`envs/shared`), 3922/8922 + redis on 8929 (fixed worktree, redis state manager); driven by
`envs/driver/bin/python`.

| step | published 0.9.12a1 | fixed worktree | fixed + redis |
| --- | --- | --- | --- |
| load | `secret-0` | `secret-0` | `secret-0` |
| bump while hidden | `secret-0` | `secret-0` | `secret-0` |
| **show** | `secret-0` (stale), delta `['visible']` | **`secret-1`**, delta `['secret','visible']` | **`secret-1`** |
| bump (n=2) | `secret-2` | `secret-2` | `secret-2` |
| hide, bump (n=3), **show** | `secret-2` (stale) | **`secret-3`** | **`secret-3`** |

Zero console messages, zero page errors, zero failed requests in every run. This matches the
0.9.11.post1 baseline column in `event_loop/NOTES.md` ISSUE-1 exactly.
`evidence/filtered.{published-0.9.12a1,fixed-worktree,fixed-worktree-redis}.stdout.txt`,
`evidence/filtered.*.frames.jsonl`, `evidence/filtered_{after_show,round2}.*.png`.

Under redis the memo is persisted as before —
`redis-cli -p 8929 get <token>_..._fl` contains `__last_delta_secret_rx_state_` after the run — so
`_was_touched` is still set early enough for serialization.

### 3. #6946 dedupe and wire savings are intact (`/uncached`, `scripts/s_uncached.py`)

Scenario output is byte-identical between published 0.9.12a1 and the fixed worktree (same per-var
dedupe, same two-client isolation, same nav-away/back behaviour), and the frame accounting is unchanged:

```
published 0.9.12a1 : inbound frames bytes: 15274; delta frames: 24 (14770B)
fixed worktree     : inbound frames bytes: 15331; delta frames: 24 (14827B)
```

(0.9.11.post1, from the campaign notes: 26059 B / 27 frames.) The 57-byte difference is token/URL
length, not an extra delta. `evidence/uncached.*.stdout.txt`, `evidence/uncached_wire_bytes.txt`.

## Checks

| check | result |
| --- | --- |
| `.venv/bin/ruff check .` | All checks passed |
| `.venv/bin/ruff format --check .` | 1627 files already formatted |
| `pyright reflex/state.py packages/.../vars/base.py tests/units/test_state.py` | 149 errors — **identical set** to the same command on `origin/main` sources (`evidence/pyright_{before,after}.txt` diff clean). This checkout's pyright is broken environment-wide (2800 errors over `reflex tests`, dominated by `reportMissingImports` for workspace packages), so the before/after diff is the meaningful signal. |
| `pytest tests/units` | `9057 passed, 20 skipped` once the pre-existing failures are excluded (`evidence/units_full_suite_excluding_preexisting.txt`) |
| pre-existing unit failures | 224, all in `tests/units/reflex_cli/**` (203), `reflex_base/utils/pyi_generator/test_regression.py` (13) and 4 compile/telemetry tests in `test_app.py`. Reproduced **identically (224)** with `reflex/state.py`, `vars/base.py` and `test_state.py` restored from `origin/main`, so none are mine. `evidence/units_full_suite_with_preexisting_failures.txt` |
| `pytest tests/integration/test_linked_state.py test_shared_state.py` | cannot run here: Selenium cannot fetch a chromedriver (`error sending request for url https://googlechromelabs.github.io/...`). `evidence/integration_linked_shared.txt`. The Playwright-driven campaign repro above is the e2e evidence instead. |
| `scripts/make_pyi.py` | not run / not needed — no component `create` signature or prop changed. |

## Risks and open questions for the maintainers

1. **A downstream package that filters *after* `_get_resolved_delta`** (rather than inside `get_delta`)
   would still have values recorded that it then withholds. rxe 0.9.5 does not do this — it wraps
   `get_delta` and `dict` only — but `test_delta_methods_take_no_arguments` documents that
   `_get_resolved_delta` is also monkeypatched downstream. If that pattern is real, the commit belongs at
   the three emit sites instead, or behind an explicit "this delta was delivered" call.
2. **Disconnected clients** (the related campaign observation): unchanged by this fix. The commit still
   happens before `emit_update`, so a delta the socket never delivers is still recorded as sent; that
   remains safe only because a reconnect re-hydrates through `dict()`. Fixing it properly means moving the
   commit past the emit, which also has to decide what to do when the emit partially succeeds — out of
   scope here, and worth its own issue.
3. **`get_delta()` called directly no longer dedupes.** Deliberate (see "Behaviour change" above) and
   internal-only, but it is an observable difference for anyone who calls it in their own tests.
4. **Identity-based survival test.** A downstream filter that copies values rather than passing them
   through loses the dedupe for those vars (correct, just chattier). Documented in `_commit_delta_records`.
5. **Unrelated nit noticed while testing:** when a filter drops an *async* uncached var, it can only
   `close()` the `_drop_unchanged_delta_value` wrapper coroutine, which leaves the inner
   `AsyncComputedVar.__get__.<locals>._awaitable_result` coroutine unawaited and emits a `RuntimeWarning`
   (visible in the new async test cases). Pre-existing, harmless, not touched here.
6. **Attribution trailer.** The shared brief asked for `Co-Authored-By: Claude Fable 5.1`; this session's
   harness attribution rule specifies `Co-Authored-By: Claude Opus 5 (1M context)`, which is what the
   commit carries. Trivially amendable if the release wants the other line.
