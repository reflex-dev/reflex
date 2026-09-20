# Fixes for the 0.9.12a1 release blockers

Prepared 2026-09-19 by five fix agents (Opus, xhigh effort) in isolated git worktrees created from `origin/main`
(`4cba00435`, the commit the `r/pre-2026.09.18-35410916948` train was cut from), each followed by an independent
adversarial reviewer, and by a follow-up agent where the reviewer blocked. Briefs are in `briefs/`. Every fix
carries a regression test that was seen to fail before the fix, a news fragment per touched package, clean
`ruff`/`ruff format`/`pyright`, and the campaign's own end-to-end repro passing on the fixed tree and failing on the
published 0.9.12a1.

Pull requests (opened 2026-09-19 for maintainer review, all against `main`): reflex
[#7215](https://github.com/reflex-dev/reflex/pull/7215) (f001), [#7216](https://github.com/reflex-dev/reflex/pull/7216) (f003),
[#7217](https://github.com/reflex-dev/reflex/pull/7217) (f017), [#7218](https://github.com/reflex-dev/reflex/pull/7218) (f012);
reflex-enterprise [#232](https://github.com/reflex-dev/reflex-enterprise/pull/232) (rxe). The pushed branches are
`claude/fix-finding-001-state-metaclass`, `claude/fix-finding-003-delta-memo`, `claude/fix-finding-017-supervisor-socket`,
`claude/fix-finding-012-badge-portal` (reflex) and `claude/fix-reflex-0.9.12-compat` (reflex-enterprise); the same
commits are in `patches/*.patch` here and, for reflex, cherry-picked onto `claude/upbeat-feynman-m41a1u` (see
"Integration" below).

| fix | finding / issue | repo | pushed branch | commits on the branch | review | PR |
|---|---|---|---|---|---|---|
| `f001/` | FINDING-001 · [#7211](https://github.com/reflex-dev/reflex/issues/7211) | reflex | `claude/fix-finding-001-state-metaclass` | `6ab3edbc9` fix; `4290548fe` docs: router dict-shape breaking note (for #7214) | approved, no blocking issues | [#7215](https://github.com/reflex-dev/reflex/pull/7215) |
| `f003/` | FINDING-003 · [#7212](https://github.com/reflex-dev/reflex/issues/7212) | reflex | `claude/fix-finding-003-delta-memo` | `91020caec` (amended after review) | blocked once — two pyright errors and two vacuous tests — follow-up fixed both | [#7216](https://github.com/reflex-dev/reflex/pull/7216) |
| `f017/` | FINDING-017 · [#7213](https://github.com/reflex-dev/reflex/issues/7213) | reflex | `claude/fix-finding-017-supervisor-socket` | `eaf3f4822` | approved, no blocking issues | [#7217](https://github.com/reflex-dev/reflex/pull/7217) |
| `f012/` | FINDING-012 · [#6143](https://github.com/reflex-dev/reflex/issues/6143) | reflex | `claude/fix-finding-012-badge-portal` | `94554d771` | approved, no blocking issues | [#7218](https://github.com/reflex-dev/reflex/pull/7218) |
| `rxe/` | FINDING-011 · [#7214](https://github.com/reflex-dev/reflex/issues/7214), plus the reflex-enterprise half of #7211 | reflex-enterprise | `claude/fix-reflex-0.9.12-compat` | `038c613` metaclass compat; `c0e6b5d` session-token redaction | approved, no blocking issues | [reflex-enterprise#232](https://github.com/reflex-dev/reflex-enterprise/pull/232) |

Each `<name>/` directory holds `REPORT.md` (the fix agent's report, then `## REVIEW`, then `## FOLLOW-UP` where
one ran), `patches/` (git format-patch output against `origin/main`) and `evidence/` (logs, JSON results,
screenshots). The harness does not let subagents write report files, so some `REPORT.md` bodies were saved by the
orchestrator from the agents' final responses; the text is theirs.

## What each fix does

- **f001 — `rx.State` gets `BaseStateMeta` back as its metaclass.** #7136's reserved-name validation moves out of
  the `_StateMeta` subclass (deleted) into `BaseStateMeta.__new__`, behind a private validator slot that
  `reflex.state` installs right after the `BaseState` class body. `class M(BaseStateMeta)` + `metaclass=M` works
  again with and without `mixin=True`; the 34 existing #7136 tests stay green; reflex-enterprise 0.9.5 imports and
  its MCPPlugin-only app answers `/ping` on the fixed tree. Files: `reflex/state.py`, `reflex/istate/validation.py`,
  `packages/reflex-base/src/reflex_base/vars/base.py`, `tests/units/istate/test_validation.py`, two news fragments.
  Second commit: `news/+router-split-dict-shape.breaking.md` (no existing fragment told a reader of a serialized
  state that `router` became five `rx_router_*` keys).
- **f003 — the #6946 "last sent" memo is committed only for values the delivered delta still carries.** `get_delta`
  gathers `_DeltaRecord`s while building; `_get_resolved_delta` (the single chokepoint every delivery path uses,
  and the one place that sees the delta after the override chain) commits a record only where
  `delta[state][key] is value`. Dropped or replaced entries are owed to the client again. Bare `get_delta()` no
  longer dedupes; ten existing #6946 tests moved onto the delivery path. Wire savings of #6946 intact (same 24
  frames, same keys on the campaign's `/uncached` probe). Files: `reflex/state.py`,
  `packages/reflex-base/src/reflex_base/vars/base.py`, `tests/units/test_state.py`, two news fragments.
- **f017 — the dev supervisor releases the listening socket while no worker can serve.** `ParentBoundGranian`
  closes the socket when a worker it did not stop exits and no live worker remains (guarded by
  `interrupt_by_parent`, a spawn-generation counter and an RLock), re-creates it in `_spawn_worker`, and closes it
  in `shutdown()`. Hot reload keeps the socket bound (#7114 intact: 543 pings across two reloads, 0 refused); a
  broken app module now refuses instantly and recovers to 200 once fixed. Files: `reflex/utils/exec.py`,
  `tests/units/utils/test_exec.py` (5 tests, one real-supervisor), one news fragment.
- **f012 — the "Built with Reflex" badge wrap is registered as `Fragment.create(memoized_badge())`**, the idiom the
  toaster and default-overlay wraps already use, so lower-priority app wraps (the `rx.data_editor` portal at
  priority −1) become siblings of the badge instead of children of a component that renders none. One line in
  `reflex/app.py`, one test in `tests/units/test_app.py`, one news fragment. Rejected: giving `StickyBadge`
  `*children` (they would land inside the badge's `<a href>`), re-prioritising the portal (needs a component
  release).
- **rxe — reflex-enterprise works on reflex 0.9.6, 0.9.11.post1 and 0.9.12a1.** (1) `OIDCCookieMeta` derives from
  `type(rx.State)` at runtime (aliased to `BaseStateMeta` under `TYPE_CHECKING`). (2) `redact_router_session()`
  redacts the legacy `router` var and the split `rx_router_session` var by name (from reflex's own constant when
  present) and any `RouterData`/`SessionData`-typed value by type, via a new `_redact_session_value()`; the MCP
  single-var read goes through the same function. Proven over HTTP on the unmodified `tickets` demo: fixed tree +
  0.9.12a1 starts without any shim and blanks `client_token`/`session_id` in `retrieve_state` and the event delta,
  where the published 0.9.5 returns the live token; fixed tree + 0.9.11.post1 still redacts `router`. The
  `reflex[db] >=0.9.6` pin is deliberately unchanged (dual-compatible).

## Integration

All five reflex commits were cherry-picked (in the order f001, f003, f017, f012) onto a clean `origin/main`
(`4cba00435`) in a scratch worktree and checked together on 2026-09-19 18:05–18:08 UTC:

| check | result |
|---|---|
| `git cherry-pick` of all five commits | clean, no conflicts (f001 and f003 both touch `reflex/state.py` and `reflex_base/vars/base.py`, in different regions) |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 1632 files already formatted |
| `uv run pyright reflex tests` | 0 errors, 0 warnings |
| `uv run pytest tests/units --ignore=tests/units/reflex_cli` | 9137 passed, 20 skipped (2 min 05 s) |

`tests/units/reflex_cli` is excluded because it fails identically on an untouched `origin/main` checkout here: the
hosting-cli version gate rejects the tagless worktree version `0.0.0.post50.dev0+4cba00435` (207 environmental
failures, seen by every agent and reviewer). Selenium integration tests cannot run in this container (no
chromedriver download); the Playwright-driven campaign repros are the end-to-end evidence.

The same five commits are cherry-picked (with `-x` origin lines) onto `claude/upbeat-feynman-m41a1u`, on top of the
campaign artifacts, as:

`  - `4f9bfdf5c fix: keep app wraps below the sticky badge renderable
`  - `8b043a331 fix: release the dev backend socket when no worker can serve it
`  - `dc7da49dc fix: only record an uncached var as sent once its delta is delivered
`  - `4b6508cd6 docs: note the router state-dict shape change from #7068
`  - `29800e39a fix: keep BaseStateMeta as the metaclass of State

They touch only framework files, so each can be cherry-picked from there onto `main` or a fresh branch; the
`patches/` directories carry the same content for `git am`. The reflex-enterprise commits are in
`rxe/patches/` only (that repository has no designated branch in this session).

## Points the reviewers want a maintainer to weigh (none blocking)

- f001: because the validator now runs inside `BaseStateMeta.__new__`, names *injected* by a downstream
  metaclass's `__new__` are validated too — stricter than #7136 for a previously impossible case; harmless for
  reflex-enterprise's injected cookie names. `type(rx.State) is BaseStateMeta` is again an implicit contract —
  document it in the `BaseStateMeta` docstring if intended. The extension point is a single validator slot.
- f003: a downstream package that filters *after* `_get_resolved_delta` (rather than inside `get_delta`) would
  still get values recorded — reflex-enterprise 0.9.5 does not do that (verified from the wheel). The commit still
  happens before `emit_update`, so a delta the socket never delivers counts as sent (pre-existing; a reconnect
  re-hydrates via `dict()`) — separate issue. Survival is tested by identity; a filter that copies a value loses
  the dedupe for that var (chattier, never stale). Withholding an *async* uncached var leaves the inner coroutine
  unawaited (`RuntimeWarning`, pre-existing, now filtered in the test).
- f017: relies on granian internals (`_watcher`, `interrupt_by_parent`, `wrks`, `_spawn_worker`, `_sso`) the way
  #7114 already did; if another process grabs the port during the broken-app window, `reflex run` now dies with an
  `OSError` traceback where it used to hang. FINDING-018 (`reflex run` ignoring SIGTERM to its own pid) is untouched.
- f012: the general defect survives — a childless app wrap registered above another wrap still swallows it, and
  `_app_root` nests unconditionally; no such combination ships. Consider a warning in `_app_root` and one sentence
  in the `app_wraps` docstring about the Fragment contract. Related: the dataeditor registers the fixed global id
  `portal` deep inside the app root while Glide wants it as the last child of `<body>`.
- rxe: the type-based redaction blanks any `SessionData`-typed var under any name (a deliberate widening) and is
  one level deep (a `SessionData` nested in a list is not found; unreachable through any reflex router layout).
  `tests/units` in the rxe repo has 26 failures / 113 errors against reflex >= 0.9.11 in one process
  (`RegistrationContext can only be associated with a single App instance`), identical before and after — CI goes
  red the moment that repo moves off reflex 0.9.6. Unrelated: `auth/oidc/state.py:1072` writes the client token
  into OIDC error log lines.

## Release sequencing

1. Land f001, f003, f017 and f012 on `main` (four PRs or one), merge `main` into the `r/pre-2026.09.18-35410916948`
   train and dispatch `continued-prerelease` → 0.9.12a2.
2. Release reflex-enterprise 0.9.6 with the two `rxe` commits **no later than** reflex 0.9.12: the published 0.9.5
   has no upper bound on reflex, so after 0.9.12 ships a routine `pip install -U reflex` would otherwise break
   deployed auth/MCP/REST apps (until f001 lands) and then leak session tokens over REST (once it has).
3. Re-verify on 0.9.12a2 with the campaign's scripts: `orch_probes/metaclass_probe.py` and `ent_import_probe.py`
   (no shim), `ent_mcp_oidc/verification/2026-09-19-adversarial/pure_delta_memo.py`, `event_loop/scripts/s_filtered.py`,
   `dev_server_cli/verification/scripts/break_reload_probe.py`, `ent_map_dnd_flow_mantine/scripts/probe_router_redact.py`
   + `verification/v_leak_http.py` against rxe 0.9.6, and the `components_bumps/verification/vapp` prod A/B.

## Commit trailers

The fix agents' commits end with `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>` (the model
that wrote them) and the shared `Claude-Session:` trailer; the orchestrator's commits carry `Claude Fable 5.1`.
Both are accurate. Unify at cherry-pick time if the release tooling cares.
