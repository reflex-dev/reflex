# Release plan — what blocks reflex 0.9.12a1 → 0.9.12 vs what gets filed

**Status: IN PROGRESS** — updated as clusters and verifiers finish. Rubric (from the campaign playbook):
fix before release = confirmed regression vs 0.9.11.post1, OR security-relevant, OR significant user
impact / trivially small. Everything else is filed as an issue and fixed after. Each entry names the
arm of the rubric that put it there, so a maintainer can disagree with a specific judgment.

## Already in flight

_(pending — open PRs checked at the end of the campaign)_

## Fix before release

### Confirmed regressions

- **FINDING-001 — `rx.State`'s new metaclass breaks downstream `BaseStateMeta` subclasses; reflex-enterprise
  0.9.5 AuthPlugin and MCPPlugin apps cannot start on 0.9.12a1** (CRITICAL). Arm: confirmed regression
  (import sweep + framework-only repro on both versions; blast radius measured end to end by `ent_mcp_oidc`).
  Shape of the fix, framework side: keep `type(rx.State) is reflex.vars.BaseStateMeta` — run #7136's
  `_validate_state_name`/`_validate_inherited_members` from `BaseStateMeta.__new__` (guarded on "a base is a
  `BaseState`") instead of introducing `reflex.istate.validation._StateMeta`; or make `_StateMeta` compose
  with sibling `BaseStateMeta` subclasses (e.g. resolve the most-derived metaclass dynamically in
  `BaseState.__init_subclass__`). Regression test: `class M(BaseStateMeta)` + `class S(rx.State, mixin=True,
  metaclass=M)` must construct (`orch_probes/metaclass_probe.py`). Add a changelog note either way. A
  lockstep reflex-enterprise release switching to `class OIDCCookieMeta(type(rx.State))` is the downstream
  half, but it does not rescue the already-published 0.9.5 against a released 0.9.12.

- **FINDING-003 — a `@rx.var(cache=False)` withheld from the delivered delta is never re-sent** (MEDIUM,
  regression claimed by `ent_mcp_oidc`, verification pending; `event_loop` asked for a pure-reflex repro).
  Arm: confirmed regression if the verifier holds it. Shape: record the "last sent" key after the delta has
  been filtered/emitted (or expose the memo update to `get_delta` overrides), not at compute time.

### Trivially small / significant impact

- **FINDING-004 — `deps=["router"]` deprecation warning is dead code** (LOW, `router_vars`, pending
  verification). Arm: trivially small — the changelog promises the warning; the guard at
  `reflex/state.py:1205-1219` can never be true. Either emit the warning from where the string dep is
  resolved, or drop the deprecation line from the changelog.

## File as issues, fix after release

### reflex-dev/reflex

- FINDING-005 — computed vars reading `self.router` depend on all five router fields; narrow `deps=` cannot
  narrow; navigation delta −47% measured vs −67% claimed (LOW, perf gap, `router_vars`).
- FINDING-006 — backend (underscore) var shadowing across substates still silently ignored (LOW,
  pre-existing gap in #7077's scope, `router_vars`).
- Pre-existing, re-observed: `uv pip install reflex-<ver>.tar.gz` fails on the workspace `tool.uv.sources`
  (issue #7088); `reflex run` keeps running and prints "Backend running at …" after the app module raised at
  import (both versions; makes FINDING-001 look like a hang).

### reflex-dev/reflex-enterprise

- Switch `OIDCCookieMeta` to derive from `type(rx.State)` (forward-compatible on both versions) and stop
  importing the OIDC state module from `MCPPlugin.post_compile`'s exemption check when `AuthPlugin` is not
  configured (would have kept MCP-only apps alive). `_override_base_method` is a private reflex helper the
  wheel depends on.
- `/_reflex/cookies/sync` answers 405 (new) / 404 (prev) with two `net::ERR_ABORTED` per browser run
  (pre-existing, previous campaign).

## Decisions needed from a maintainer

- FINDING-002 — the #7132 changelog entry ("keep saving state … when a state defines a var named
  `_get_was_touched`") describes behavior #7136 made unreachable: the declaration now raises
  `StateValueError`. Reword/drop the entry, or fold it into #7136's breaking note.
- FINDING-007 — PR #7136's description promises `REFLEX_STATE_ALLOW_RESERVED_NAMES=1` as a temporary escape
  hatch; nothing in the published packages reads it. Ship the flag or correct the migration text.
- #7077 ships a hard `BaseVarShadowsInheritedVarError` (the PR discussion considered a warning). Intended?
  Apps that silently redeclared an inherited var on 0.9.11.post1 now fail at import with no opt-out.
- The metaclass change itself (FINDING-001) is unannounced; if it is kept, it needs a Breaking Changes
  entry naming `BaseStateMeta` and the `type(rx.State)` spelling.

## Suggested sequencing

1. FINDING-001 framework fix first (one PR, regression test from `orch_probes/metaclass_probe.py`), then
   re-run `orch_probes/ent_import_probe.py` and the `ent_mcp_oidc` harness without the shim.
2. FINDING-003 once the `event_loop` verifier reports (independent files: `reflex/state.py` delta path vs
   `reflex/istate/validation.py`, so it can land in parallel with 1).
3. FINDING-004 and the changelog decisions (002, 007, metaclass note) can ride one docs/changelog PR.
