# Release plan — what blocks reflex 0.10.1 vs what gets filed

Findings referenced as R101-NN (see [FINDINGS.md](./FINDINGS.md)). Rubric (skill): fix before release when a finding is
a confirmed regression vs 0.10.0, security-relevant, significant user impact, or trivially small. Each entry names the
arm that put it there.

## Already in flight
- **reflex-enterprise 0.9.10a1** (offline wheel, 2026-10-26; rxe #279, #282) — re-verified in `verify_ent910/`:
  **R101-01 fixed** (every memoized consumer follows state after grid edits, dev + prod, nested fields, after reload;
  45/45 on the explorer's suite), **R101-07 fixed** (REST `client_ip` = websocket resolution; rate limits keyed on the
  resolved IP), and **R101-22 fixed** as a side effect (grid edits work next to a recharts chart of the same data).
  Accepted limitation: a handler that rejects an edit leaves the typed value in that grid (better than 0.10.0). Gap:
  R101-01 is fixed for AG Grid only — any other component that mutates the objects it receives from state still
  defeats #7273's structural sharing; a reflex-side guard remains worth considering.

## Fix before release

### Confirmed regressions
- **R101-01 — stale memoized consumers after an AG Grid edit (#7273)** — *regression*, medium. Shape of fix, pick one:
  (a) reflex: make structural sharing robust to consumers mutating the store's objects — e.g. compare the delta
  against what the store last *received* (keep the raw delta values, or a cheap version counter per var) rather than
  the live, possibly mutated object; (b) reflex-enterprise: hand AG Grid a copy of `row_data` (or enable `readOnlyEdit`
  and let the backend echo drive the update) so the store's objects are never mutated — fixes AG Grid only; other
  mutating third-party components remain exposed. (a) is the general fix; (b) is the smallest. Regression test: the
  `verify_en1/gridmin` scenario (edit → memo consumer must update).
- **R101-02 — fork preload semantics (#7079)** — *scoped regression*, low (verifier). Fix = a CHANGELOG / docs
  behaviour-change note naming the changed cases (`reflex run --env prod --backend-only` on Linux, every prod run on
  Python 3.14), with the examples (import-time threads incl. logging `QueueListener` and schedulers are dead in workers;
  module-level values and `random.Random()` instances are shared) and the `REFLEX_BACKEND_START_METHOD=spawn` escape
  hatch. Optional: one fork-time log line when the supervisor has extra threads.

### Trivially small (and in new 0.10.1 code)
- **R101-05 — CHANGELOG wording for #7386** — *regression by design* + *trivial*. Add one sentence: dict handlers now
  get the last value of a name submitted more than once even when a control's `id` equals that name (checkbox groups
  with several checked, multi-selects). Reword the reflex-components-core deprecation entry's "also stops adding a field
  keyed by its id … submits 'on'" sentences into future tense (they describe 0.11).
- **R101-06 — malformed / colliding form envelope** — *trivial*, new code path: treat a dict as a form-data envelope only
  when its entries are a list of 2-item lists (fixes both the socket-garbage traceback and the `__reflex_form_data__`
  name collision).
- **R101-13 — `[None]` in `list[str]` / `getlist()` for an empty id'd checkbox group** — *trivial*, new API: skip `null`
  id-ref values (or map an empty group to `[]`) when building FormData entries.

## Decisions needed from a maintainer
- **R101-04 — sibling floors of the reflex wheel.** `reflex` requires only `>=0.10.0` of components-core / -code /
  -dataeditor, `>=1.1.0` lucide, `>=0.2.0` hosting-cli, so `pip install -U reflex` keeps the old siblings and the train's
  component fixes (#7437, #7607 — a state-backed data_editor column without `type` still crashes the page) and the
  hosting-cli fixes are not delivered. The sibling-floor policy only raises floors for *needed* unreleased APIs. Raise
  the floors to the 0.10.1 releases at the final? (Cheap; follows the user-visible fix list.)
- **R101-03 — hatch-reflex-pyi hook robustness.** Not a 0.10.1 blocker (the final's newest base is 0.10.1), but every
  future alpha has the same gap and a future base that removes a symbol silently drops stubs. Pin the hook's
  `dependencies` to the runtime floors and/or set `PYI_GENERATOR_RAISE_FAILED_IMPORTS=1` in the hook so a build fails
  loudly. Also note uv reuses a cached sdist build for later wheel installs.
- **R101-08 — React Compiler coverage.** Experimental and default-off: fix the docs sentence now; codegen changes
  (call `addEvents` directly instead of the IIFE, hoist `rx.cond` test expressions, avoid render-time `refs[...]`
  writes) and a skip-summary log can follow.
- **R101-09 — `trusted_proxy_hops` token validation.** Hardening: `ipaddress.ip_address()` on the selected token
  (strip `:port` / brackets) with fallback to the peer, plus a docs line. Cheap; could ride with the 0.10.1 breaking
  change it hardens.
- **R101-07 — reflex-enterprise REST API client_ip.** Not reflex's code, but it undercuts the 0.10.1 breaking change
  (#7614) for enterprise users: rxe's REST event API should resolve `client_ip` with reflex's `trusted_proxy_hops`.
  Ship together with 0.10.1 if rxe cuts a release.

## File as issues, fix after release
### reflex
- R101-10 `reflex deploy` progress / success hidden below `--loglevel debug` (console level left at WARNING after the
  export; `--loglevel info` never reaches the config).
- R101-11 `reflex export` crashes on a directory symlink resolving outside the app, or on a dangling symlink.
- R101-12 uv cannot build the `reflex` alpha sdist (pre-release floors in the build env) — alpha-only; document the
  `-b` build-constraints workaround or relax `require-runtime-dependencies` for alphas.
- R101-14 `radio_cards(as_child=...)` — optional compile warning for the removed prop.
- R101-15 non-str storage vars (type error per instantiation; strings round-trip).
- R101-16 background-task rehydration leaves storage vars at defaults until reload.
- R101-17 close staked async-var wrappers for withheld keys in `_commit_delta_records` (or document `.close()`).
- R101-18 stale `postcss.config.js` after removing TailwindV4Plugin.
- R101-19 moment: unknown props become CSS; provider `format` overrides a child's `from_now`.
- R101-20 typing gaps (ty `rx.Field[rx.Model | None]`, `auto_complete=True`, `data_editor(columns=["A"])`,
  `VarData(position=)` deprecation invisible to checkers, ty `rx.EventHandler[spec]`).
- R101-22 recharts deep-freezes shared state objects (an editable AG Grid next to a chart of the same data cannot be
  edited) — consider passing recharts a copy, or document.
### reflex-enterprise
- R101-07 (above), R101-21 MCP OAuth consent race on Redis; unchanged: rxe#262 (N-033), rxe#269 (N-026), rxe#245
  (not re-run). rxe still passes the deprecated `VarData(position=)` (dnd.py ×3, combobox.py) — drop it to silence the
  DeprecationWarning users see once per compile.

## Suggested sequencing
1. R101-01 (structural sharing; touches `state.js`) — first, it is the only functional regression; include the
   gridmin regression test.
2. R101-06 + R101-13 (form envelope / FormData construction; `state.js` getFormData + `reflex_base/utils/form.py`) —
   one PR, after or rebased on 1 (same file).
3. CHANGELOG / docs PR: R101-02, R101-05, R101-08 docs sentence, R101-09 docs line — independent, can land in parallel.
4. Maintainer calls: R101-04 floors at materialization time; R101-03 hook pin; R101-09 code hardening.
5. Then cut 0.10.1a2 and re-run: `verify_en1/gridmin`, `verify_ct/ctform`, `events_state` form comparison, and a stock
   `pip install reflex==<final>` smoke.
