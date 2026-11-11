# Campaign state (compact context) — re-verification of the 0.10.0a4 train (2026-10-08)

## What is under test
- **reflex 0.10.0a4 + reflex-base 0.10.0a4**, released from `origin/r/pre-2026.10.06-37579583012` at `f6e070ef4`
  (tag `v0.10.0a4`; "Materialize changelogs for reflex@0.10.0a4, reflex-base@0.10.0a4"). Only these two packages were
  re-released; every other train package stays on its a2-train version. All 20 packages are on PyPI with wheel + sdist;
  the published reflex 0.10.0a4 pins `reflex-base==0.10.0a4`; `.pyi` audit PASS (122 stubs). Every source file a4
  changed is byte-identical in the installed wheels (`preflight/`).
- **reflex-enterprise 0.9.7a5** (unchanged since the a3 pass; still the newest on PyPI). Offline wheel at
  `$SB/downloads/enterprise_wheel_a5/` (not in the repo).

## What a4 changed (a3 → a4: exactly three PRs; `git diff v0.10.0a3 v0.10.0a4`)
| PR | Change | Finding it targets |
|---|---|---|
| #7505 | frontend only (`reflex_base/.templates/web/utils/state.js`): a tab records the storage values it sends with `hydrate_and_load` / `update_vars_internal` and does not write a delta value back to local/session storage when it merely echoes one of them; only `sync=True` LocalStorage vars record sent values (a `sync=False` var is always written, as on a3); values a `get_delta` override or handler changed are still written; cookies are still rewritten (renews `max_age`); a `storage` event sends the value stored NOW, not `e.newValue` | A3-11 (MEDIUM, regression vs a2), A3-12 (MEDIUM, pre-existing) |
| #7516 | breaking: the #7461/#7495 class-level default-assignment layer is REMOVED. `BaseStateMeta.__setattr__` raises `TypeError` ("'x' is a state var of S; assigning it on the class would replace the var. Set its default with S.__fields__['x'].default = ..., or declare class-level config as ClassVar.") when the name resolves through the MRO to a state var's `Field` (incl. inherited vars on substates); assigning the var's own Field back is a no-op; `__delattr__` raises the same TypeError for an INHERITED var; `del S.x` on the declaring class still removes the descriptor (delete-then-set replaces the var on purpose). Defaults are now set on the field: `S.__fields__["x"].default = v` / `.default_factory = f`; tests patch the field (`mock.patch.object(S.__fields__["x"], "default", v)`). ClassVars and new names stay assignable. Kept from #7461: saved-state schema without defaults (+ legacy fallback), `reset()` uses `default_value()`, storage-typed field `default_factory()` honored by the compiler, `_isinstance` TypeVar/Protocol. Kept from #7495: dev guard against undeclared mangled names. Docs: base_vars.md "Changing Defaults", component_state.md (per-component `cls.__fields__[...]` + named storage key note), upgrading-to-0-10.md "Assigning a state var through its class" | A3-01, A3-02, A3-04 (now moot: the assignment raises); N-005 / N-039 superseded; A3-03 docs |
| #7513 | docs only: upgrade guide + #7312 changelog entry say writing an inherited var outside `async with self` now raises `ImmutableStateError` | A3-06 |

## Findings to re-verify (full text: `../2026-10-07-a3/FINDINGS.md`; run the ORIGINAL failing repro, positive control on a3 first)
| id | original repro assets (under `prerelease_testing/2026-10-07-a3/`) | expected on a4 | item |
|---|---|---|---|
| A3-11 | `a3_hydration/src/bootecho`, `scripts/run_storm.sh`; verifier scenarios in `a3_hydration/verification/` (3 restored tabs + click, 100 ms RTT proxy, Playwright 7 restored tabs, prod + Redis 9 workers); fix design history `a3_hydration/pr7505/NOTES.md` (+ its matrix driver/results) | 0 storms, all tabs + localStorage converge on the user's last value, dev and prod | a4_hydration |
| A3-12 | `a3_hydration/src/syncstamp`, `scripts/run_stamp.sh`; verifier `/doc/<slug>` + dev-reload scenario | 0 storms, convergence (tabs may legitimately differ only if on_load stamps differ by design — check they end on ONE value) | a4_hydration |
| A3-01 | `a3_class_state/probes/undo_edge/test_undo_edge.py`, `verification/probes/test_v7_undo.py` | every `S.x = ...` / `mock.patch.object(S, "x", ...)` / `monkeypatch.setattr(S, "x", ...)` raises TypeError and leaves the field intact; patching the FIELD round-trips | a4_class_state |
| A3-02 | `a3_class_state/verification/probes/probe_v8_storage.py`, e2e app `a3_class_state/apps/clse2e` | assignment raises; storage defaults set via `__fields__[...]` with a storage value keep storage, name, options (e2e) | a4_class_state |
| A3-04 | `a3_class_state/probes/adv7495.py` case `thread_stress_assign_restore` | assignment raises; field-default patching from threads has no shared undo stack | a4_class_state |
| A3-03 / A3-06 docs | docs at `git show v0.10.0a4:docs/...` (base_vars.md, component_state.md, upgrading-to-0-10.md) and the a4 CHANGELOG.md | statements true, samples run as written on a4 | a4_class_state (docs samples) |

Not changed in a4 (expected unchanged, do NOT re-test unless something looks different): A3-07, A3-08, A3-09, A3-10, A3-13,
N-033, and every issue filed in earlier passes (#7506–#7511, #7498, #7499, #7459, #7479; enterprise#262/#274/#275).

## Regression risk introduced by a4 (hunt here)
- **#7505 (state.js).** A `sync=False` LocalStorage write from a handler lost (the bug found in review); a `get_delta`
  override that sanitises a value no longer reaching localStorage; cookies / SessionStorage handling; F-002 (fresh browser
  gets defaults written) / F-003; two tabs no longer converging (the stale-tab problem A3-12 had); a value set to the same
  value it had, set to "" / cleared, JSON-ish or unicode values; reflex-local-auth login/logout across tabs (its
  `auth_token` is LocalStorage); google-auth bogus-token clearing; enterprise auth token storage + cross-tab logout (N-032)
  — any place that relied on the boot echo being written back.
- **#7516 (metaclass guard).** Anything that legitimately sets an attribute named like a state var on a state CLASS now
  raises: framework internals (dynamic route args `add_var`, `setvar`/auto setters, `ComponentState.create`, mixins,
  `rx._x.client_state`, `rx.SharedState`, upload, `_reload_state_module` / dev hot reload when a state file is edited,
  AppHarness), downstream packages (reflex-local-auth, google-auth, magic-link, reflex-enterprise — grep the wheels for
  class-level writes), user test suites (pytest `monkeypatch` / `mock.patch.object` on a var), apps that configure a
  default at import time (`State.x = ...` — now a TypeError at import: is the message clear, and is it raised at import,
  not later?). `ClassVar` and new attributes must still work; `del` + re-set on the declaring class still works;
  `reset()`, pickling and the schema hash must be unchanged from a3 (a3 ↔ a4 state stores interchangeable).

## Environment
- SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad. Venvs (built by
  `scripts/bootstrap_envs.sh $SB --enterprise`): `a4` (under test), `a3` (previous alpha / positive control), `stable`
  (0.9.12), `driver` (playwright), `a4-ent` / `a3-ent` (+ enterprise a5 offline wheel), `s912-ent-a5`.
- Chromium: `/opt/pw-browsers/chromium`. Artifacts: `prerelease_testing/2026-10-08-a4/<item>/` on branch
  `claude/reflex-prerelease-testing-t0sd90` (the orchestrator commits; agents never run git write commands).
