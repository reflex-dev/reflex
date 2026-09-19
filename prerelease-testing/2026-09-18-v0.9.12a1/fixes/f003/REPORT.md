# f003 — FINDING-003 / issue #7212: withheld `@rx.var(cache=False)` is never re-sent

- Worktree: `/home/user/wt/f003` · Branch: `fix/finding-003-delta-memo` · Commit: `91020caec`
  (amended from the reviewed `600671cee`; see `## FOLLOW-UP` at the end for what changed)
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

## REVIEW

Independent adversarial review of `600671cee` on `fix/finding-003-delta-memo`, run from
`/home/user/wt/f003` (worktree untouched: `git status` clean, HEAD unchanged) with servers on
ports 3930-3932 / 8930-8932 and redis on 8939. Scratch:
`/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad/fixes/f003-review/`.

**Verdict: the fix is correct and I would merge it after two small changes. Not approved as-is.**

### What I verified myself

| check | result |
| --- | --- |
| `uv run ruff check .` / `ruff format --check .` | clean; 1627 files already formatted |
| `uv run pytest tests/units/test_state.py` | 222 passed |
| `uv run pytest tests/units` (full) | 207 failed, 9488 passed — **every** failure in `tests/units/reflex_cli/**`, none in or near the changed code |
| `uv run pytest tests/units/{test_app.py,test_state_tree.py,istate,reflex_base,vars,test_var.py,middleware}` | 1187 passed, 10 skipped |
| **`uv run pyright reflex tests`** | **2 errors, both introduced by this change** (see blocking issue 1) |
| regression test fails without the fix | yes — sources restored from `origin/main` with `git show origin/main:<path> >`, test file kept: `[False-dropped]`, `[False-replaced]` and `test_uncached_computed_var_recorded_only_once_delivered` fail (`assert {} == {...'secret-1'}`); restored afterwards, `git status` clean |
| e2e, in-process, on the real delivery path | my own `probe_delta_memo.py` (uses `_get_resolved_delta`, not a bare `get_delta`, and also asserts the dedupe still works): **fixed worktree PASS 8/8**, published 0.9.12a1 FAIL (withheld sync value never re-sent), 0.9.11.post1 FAIL (delivers, but no dedupe at all) |
| e2e, browser, `elapp` `/filtered` + `s_filtered.py`, dev/memory | published 0.9.12a1: stale `secret-0` after `show`, stale `secret-2` after round 2. Fixed worktree: `secret-1` and `secret-3`. Zero console/page/network errors both runs |
| same, dev + redis (8939) | fixed worktree: `secret-1` / `secret-3` |
| #6946 savings intact | `/uncached` via `s_uncached.py`: 33 inbound frames, 24 delta frames, **identical delta key sets** on published 0.9.12a1 and the fixed tree (15778 B vs 15331 B, token-length noise) |
| `test_state_manager_lock_warning_threshold_contend` | flaked 5x under load, then passed 4x in a row on the fixed tree; unrelated timing test, not a regression |

I also read `reflex_enterprise` 0.9.5 out of the offline wheel and can close open question 1: rxe does
**not** override `_get_resolved_delta`. It wraps `state_cls.get_delta` and `state_cls.dict`
(`auth/enforcement.py:install_delta_filter`), wraps `reflex.state._resolve_delta` only on an older core
(`install_delta_prune` is a no-op here because core owns `_DROP_FROM_DELTA`), and `filter_protected_delta`
rebuilds the subdelta dict while passing surviving values through **by reference** — so the identity test
holds for allowed values and fails for dropped/placeholder ones, exactly as the fix needs. `_guarded_value`
returns `original_value` itself on allow, so deferred async checks record correctly too.

### Blocking issues

1. **`uv run pyright reflex tests` now fails — 2 errors, both from the new test.**
   `tests/units/test_state.py:1780` (`delta = original_get_delta(self)`):
   `Argument of type "BaseState" cannot be assigned to parameter "self" of type "WithheldState"` /
   `"AsyncWithheldState"`. The report's claim that pyright shows an "identical 149-error set before and
   after" and is "broken environment-wide (2800 errors)" does not hold in this checkout: with
   `reflex/state.py`, `vars/base.py` and `tests/units/test_state.py` restored from `origin/main`, the same
   command reports **0 errors, 0 warnings**, and the full `uv run pyright reflex tests` on HEAD reports
   exactly these 2. CLAUDE.md's checklist gates on this. Fix: bind the original through the base class
   (`original_get_delta = BaseState.get_delta`) or annotate `self: Any`.

2. **`test_uncached_computed_var_scalar_key_distinguishes_types` is now vacuous.**
   Eight #6946 tests were moved to `await state._get_resolved_delta()`, but this one (line 1545) and
   `test_uncached_computed_var_unkeyable_value_always_sent` (line 1697) still drive bare `get_delta()`,
   which by design no longer records anything — so nothing can ever be deduped on that path and the
   assertions cannot fail. Proven by mutation: replacing `_delta_value_key`'s
   `return (value_type, value)` with `return value` (i.e. dropping the `1` / `True` / `1.0`
   discrimination the test exists to guard) is **caught on `origin/main`**
   (`KeyError: 'reflex___istate___dynamic____scalar_state'`) and **passes silently on HEAD**. The fix
   therefore disarms a guard test for the exact keying machinery it touches. Fix: convert both to
   `await ..._get_resolved_delta()` like the other eight (they are already `async` neighbours).

### Nits (non-blocking)

- `_get_resolved_delta`'s suppressed early-return path leaves `_pending_delta_records` pointing at an
  outer collector, so a `_suppress_delta_recording()` traversal nested inside a recording one (possible
  via `istate/shared.py:_patch_state` reached from an async computed var) appends into the outer list.
  Harmless today — a record only commits when the delivered delta holds that identical object under that
  key, in which case the outer traversal appended an identical record anyway — but it breaks the stated
  "a suppressed traversal records nothing" invariant. One line: set `_pending_delta_records` to `None` in
  that branch.
- Unkeyable values: `_commit_delta_records` sets `instance._was_touched = True` unconditionally in the
  `stored is None` branch, including when the `delattr` found nothing to remove. `_record_delta_value`
  never did. An app with a non-serializable `cache=False` var now forces a redis write on every delivered
  delta. Guard it on the `delattr` actually succeeding.
- The structured claim lists the regression test as "4 params"; the two `is_async=True` params pass on
  `origin/main` as well (the filter closes the coroutine before it can reach the memo). Real regression
  coverage is the 2 sync params plus `test_uncached_computed_var_recorded_only_once_delivered` — which the
  report itself says, but the summary does not.
- Two ContextVars now encode one idea (`_record_delta_values` is read in exactly one place, and
  `_pending_delta_records is None` already means "not recording"). A maintainer may ask to collapse them.
- `packages/reflex-base/news/+uncached-var-withheld-from-delta.bugfix.md` reads as an internal
  implementation note (`ComputedVar` no longer records..., it reports to `BaseState`) rather than a
  downstream-user statement.
- The new async test cases emit `RuntimeWarning: coroutine '...._awaitable_result' was never awaited` into
  the suite output (the pre-existing wrapper-close nit the report flags as item 5), now visible on every
  `tests/units/test_state.py` run.
- Commit trailer says `Co-Authored-By: Claude Opus 5 (1M context)`; the shared brief asked for
  `Claude Fable 5.1`. Harness rule vs brief — the release owner should pick one before cherry-picking.

### Things I tried and could not break

- Override that mutates the subdelta in place (what `elapp` does) vs. one that rebuilds it (what the unit
  test and rxe do): both work, because surviving values keep their identity.
- An override calling `super().get_delta()` twice and returning the second delta: correct under the fix
  (it was broken under the eager memo, which deduped the second call to empty).
- Placeholder substitution where the placeholder is the same interned object as the computed value
  (`None`, `True`, small ints, `""`): records, but correctly — `is` implies the client received exactly
  that object.
- Concurrency: `_drop_unchanged_delta_value` takes `pending` as an argument, so `asyncio.create_task`
  context copying inside `_resolve_delta` cannot cross-contaminate collectors;
  `_do_update_other_tokens` spawns its tasks from `_clean()`, after the collector is reset.
- `_get_resolved_delta` really is the only delivery chokepoint: `reflex/app.py:1864`,
  `reflex/istate/proxy.py:223`, `reflex-base .../base_state_processor.py:226`,
  `reflex/istate/shared.py:123`. Everything else (`hydrate_middleware`, `compiler/utils`,
  `state.py:2900`) resolves `dict()`, not a delta. `test_delta_methods_take_no_arguments` still holds for
  both methods.

## FOLLOW-UP

Follow-up pass on the reviewer's verdict, in the same worktree `/home/user/wt/f003` on branch
`fix/finding-003-delta-memo`. The branch is still **one commit** on top of `origin/main`
(`4cba00435`), amended in place: `91020caec` (was `600671cee`). Nothing pushed, no PR.
Ports used: 3920-3922 / 8920-8922, redis on 8929; all released afterwards.
Scratch: `/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad/fixes/f003-followup/`.

**Both blocking issues are accepted and fixed; four of the seven nits are fixed; three are answered
below.** The reviewer was right on both counts, including that the previous pyright claim in this
report was wrong: `uv run pyright reflex tests` works fine in this checkout.

### Blocking 1 — pyright regression from the new test (fixed)

Confirmed exactly as reported: on `600671cee`, `uv run pyright reflex tests` gave

```
tests/units/test_state.py:1780:36 - error: Argument of type "BaseState" cannot be assigned to
  parameter "self" of type "AsyncWithheldState" in function "get_delta"
tests/units/test_state.py:1780:36 - error: ... of type "WithheldState" ...
2 errors, 0 warnings, 0 informations
```

The earlier "identical 149-error set before and after" / "environment-wide broken pyright (2800
errors)" claim in the Checks table above does not hold: that was a *module-scoped* invocation
(`pyright reflex/state.py packages/... tests/units/test_state.py`), which type-checks those files
without the project's import graph and manufactures `reportMissingImports` noise. The gate CLAUDE.md
actually specifies, `uv run pyright reflex tests`, is clean on `origin/main` and was not run.
**Treat the pyright row of the original Checks table as retracted.**

Fix (`tests/units/test_state.py:1787`): bind the original through the base class, which is what the
wrapper's `self: BaseState` annotation describes, and which is also more robust — `monkeypatch`
installs the wrapper on the subclass, so the base method is guaranteed to be the unpatched one.

```python
    # Bound through the base class: neither state overrides `get_delta`, and the
    # wrapper below replaces it on both, so its `self` is only a `BaseState`.
    original_get_delta = BaseState.get_delta
```

`uv run pyright reflex tests` → **0 errors, 0 warnings, 0 informations**
(`evidence/followup_checks_after_fix.txt`).

### Blocking 2 — two #6946 tests left on the now-non-recording `get_delta()` path (fixed)

Accepted: a test that drives bare `get_delta()` can no longer observe the dedupe at all, so it
asserts nothing about `_delta_value_key`. Both are now `async def` driving
`await ..._get_resolved_delta()`, like the other eight:

- `test_uncached_computed_var_scalar_key_distinguishes_types` (`tests/units/test_state.py:1545`)
- `test_uncached_computed_var_unkeyable_value_always_sent` (`tests/units/test_state.py:1698`)

Re-proved with the reviewer's mutation, plus a second one for the other test
(`evidence/followup_mutation_tests.txt`), both run on the follow-up HEAD:

| mutation in `reflex-base` `vars/base.py` | test | result on follow-up HEAD |
| --- | --- | --- |
| `_delta_value_key` returns bare `value` (drops the 1/`True`/1.0 discrimination) | `..._scalar_key_distinguishes_types` | **FAILED** — `KeyError: 'reflex___istate___dynamic____scalar_state'` (was: passed silently) |
| `_delta_value_key` returns a constant key instead of `_UNKEYABLE_VALUE` | `..._unkeyable_value_always_sent` | **FAILED** — `KeyError: 'reflex___istate___dynamic____circular_state'` (was: passed silently) |

Both mutations were reverted; `packages/reflex-base/src/reflex_base/vars/base.py` is byte-identical
to the reviewed commit (the follow-up changes nothing in that package's source).

### Nits fixed

1. **`_get_resolved_delta` no longer leaks an outer collector into a suppressed traversal**
   (`reflex/state.py:2487`). The early return is gone; the method now always installs the
   ContextVar, with `None` when `_record_delta_values` is false, so "a suppressed traversal records
   nothing, at any depth" holds literally:

   ```python
   pending: list[_DeltaRecord] | None = [] if _record_delta_values.get() else None
   records_token = _pending_delta_records.set(pending)
   try:
       delta = await _resolve_delta(self.get_delta())
   finally:
       _pending_delta_records.reset(records_token)
   if pending:
       _commit_delta_records(pending, delta)
   ```

2. **Unkeyable values no longer force a redis write when nothing was removed**
   (`reflex/state.py:374`): `delattr` is now a `try/except AttributeError: continue`, so
   `_was_touched` is set only when a record actually went away. This restores the pre-fix behaviour
   (`_record_delta_value` never touched `_was_touched` on that path) for an app with a
   non-serializable `cache=False` var.

3. **`packages/reflex-base/news/+uncached-var-withheld-from-delta.bugfix.md`** rewritten for
   downstream users (it no longer narrates `ComputedVar`'s internal division of labour).

4. **The `RuntimeWarning` no longer pollutes the suite output.** The async cases of the regression
   test carry a targeted
   `@pytest.mark.filterwarnings("ignore:coroutine '.*_awaitable_result' was never awaited:RuntimeWarning")`
   with a comment saying why. The leak itself is *pre-existing*, and I verified that rather than
   assuming it: running the reviewed test file against `origin/main` sources (fix reverted, test kept)
   emits the same warning from the same line. A filter that withholds an async uncached var can only
   `close()` the `_drop_unchanged_delta_value` wrapper — the inner `AsyncComputedVar` coroutine is
   unreachable from outside, and closing a never-started wrapper runs none of its code, so there is
   no hook to close it from inside either. Fixing it means not building the inner coroutine before
   the wrapper runs, which is a separate change to `get_delta`; it stays an issue for the maintainers
   (open question 5 above).

### Nits answered rather than changed

- **"Two ContextVars encode one idea" — kept, deliberately.** They answer different questions:
  `_record_delta_values` is set by the `_suppress_delta_recording()` *context manager* around a whole
  block and read once, at the entry point, to decide whether to collect; `_pending_delta_records`
  carries *where* to put the records of the one delta currently in flight. Collapsing them needs a
  third state ("suppressed" vs "no collector installed yet"), i.e. a sentinel list that `get_delta`
  must then test for by identity before appending — more code and less obvious than the flag. Happy
  to collapse if a maintainer prefers it; it is a two-line change either way.
- **"4 params" overclaim — corrected.** Real regression coverage for #7212 is
  `test_uncached_var_withheld_by_delta_override_is_resent[False-dropped]`, `[False-replaced]` and
  `test_uncached_computed_var_recorded_only_once_delivered`. The two `is_async=True` params pass on
  `origin/main` too and are a guard on the new `_drop_unchanged_delta_value` signature, not a
  regression test. The structured result of this follow-up says so.
- **Commit trailer.** Still `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`:
  this session's harness attribution rule is explicit that it replaces other attribution guidance,
  and the brief's `Claude Fable 5.1` line came from the workflow script, not from the user. One
  `git commit --amend` for the release owner if they want the other line.

### Re-run evidence (all on the amended commit `91020caec`)

| check | result | evidence |
| --- | --- | --- |
| `uv run ruff check .` | All checks passed | — |
| `uv run ruff format --check .` | 1627 files already formatted | — |
| **`uv run pyright reflex tests`** | **0 errors, 0 warnings, 0 informations** | `evidence/followup_checks_after_fix.txt` |
| `uv run pytest tests/units/test_state.py` | 222 passed, no `RuntimeWarning` in the output | `evidence/followup_checks_after_fix.txt` |
| `uv run pytest tests/units` (full) | 207 failed, 9488 passed, 20 skipped — **all 207 in `tests/units/reflex_cli/**`**, same set the reviewer saw | `evidence/followup_units_full.txt`, `evidence/followup_units_full_failure_modules.txt` |
| `pytest test_state.py test_state_tree.py test_app.py istate reflex_base vars test_var.py middleware` | 17 failed, 1392 passed, 10 skipped — the identical 17 `test_app.py` failures appear with `state.py`/`vars/base.py`/`test_state.py` restored from `origin/main` (17 failed, 1387 passed), so they are pre-existing order-dependent pollution, not mine (each passes in isolation) | `evidence/followup_units_subset.txt`, `evidence/followup_units_subset_origin_main.txt` |
| new + converted tests on **unfixed** sources | `[False-dropped]`, `[False-replaced]`, `test_uncached_computed_var_recorded_only_once_delivered` FAIL; the two converted #6946 tests pass (they guard existing behaviour) | `evidence/followup_unit_regression_before_fix.txt` |
| mutation tests | both converted tests now catch a `_delta_value_key` mutation that HEAD previously let through | `evidence/followup_mutation_tests.txt` |

End-to-end, re-run from scratch on the amended commit (`evidence/followup_*`):

| repro | published 0.9.12a1 | follow-up HEAD |
| --- | --- | --- |
| `pure_delta_memo.py` (campaign repro, verbatim) | steps 3/4 `False` | steps 3/4 **`True`** |
| `probe_delta_memo.py` (reviewer probe: real `_get_resolved_delta` path, also asserts the dedupe still works) | **FAIL** (2/8: withheld sync value never re-sent) | **PASS 8/8** |
| browser `elapp /filtered` + `s_filtered.py`, dev/memory | `secret-0` after `show` (stale), `secret-2` after round 2 (stale) | **`secret-1`**, **`secret-3`** |
| same, dev + redis on 8929 | — | **`secret-1`**, **`secret-3`**; `__last_delta_secret_rx_state_` present in the redis payload, so the memo still serializes |
| `/uncached` probe (#6946 savings) | 24 delta frames, 15274 B inbound | 24 delta frames, 15331 B inbound; **delta key sequences identical** once the hydrate delta's state-name ordering (set iteration) is normalized — the 57 B is port/token length |

Zero console messages, zero page errors, zero failed requests in every browser run.

Files: `reflex/state.py`, `packages/reflex-base/src/reflex_base/vars/base.py`,
`tests/units/test_state.py`, `news/+uncached-var-withheld-from-delta.bugfix.md`,
`packages/reflex-base/news/+uncached-var-withheld-from-delta.bugfix.md` — unchanged from the reviewed
commit except as described above.
