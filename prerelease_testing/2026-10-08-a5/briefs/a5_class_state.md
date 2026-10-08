# Brief: a5_class_state — #7519 (`Field.set_default`, copy-at-definition, error owner) on 0.10.0a5, plus class-state regressions re-run

Read first: `/home/user/reflex/prerelease_testing/2026-10-08-a5/AGENT_BRIEF.md` (hard rules), then
`/home/user/reflex/prerelease_testing/2026-10-08-a5/CAMPAIGN_STATE.md`. Artifacts →
`/home/user/reflex/prerelease_testing/2026-10-08-a5/a5_class_state/`; scratch `$SB/apps/a5_class_state/`.
Ports: frontend 3300-3339 / backend 8300-8339. Build your own venvs with pytest / pytest-mock (a5, a4, 0.9.12; Python
3.11 and 3.14 once for the core probes). The a4 pass's probes are in `/home/user/reflex/prerelease_testing/2026-10-08-a4/a4_class_state/`
and `.../verify_class_state/` — COPY and re-run them.

Read reflex-dev/reflex#7519 (GitHub MCP) and `git -C /home/user/reflex show ee14ac5c2` first.

## Part 1 — #7519 regression hunt (a5 vs a4 back to back; 0.9.12 for anything users relied on)
- **Copy at definition** (`_default_arguments` now deep-copies a mutable class-body default once at class definition):
  (a) a module-level list/dict used as a default and populated AFTER the class statement (registry / plugin / lazily
  loaded config patterns, `OPTIONS.append(...)` after the class, a dict filled by decorators) — what do new sessions see
  on 0.9.12, a4, a5? (b) a default that cannot be deep-copied (an object holding a `threading.Lock`, an open file, a
  client) on a backend var and a frontend var — where does each version fail (import / first instance / never) and is the
  error clear? (c) very large defaults (a 50 MB list / numpy array / DataFrame backend var) — memory and import time a4 vs
  a5. (d) defaults shared deliberately by identity (an object compared with `is` later) — still a copy on every version?
  (e) `rx.field(default=[...])`, `rx.field(default_factory=...)`, `rx.Field[...]`, Pydantic/dataclass objects as defaults,
  `rx.Base` models, ComponentState `.create` many times, mixins, substates — instances isolated, `reset()` correct,
  pickling / Redis round trip, schema hash unchanged vs a4.
- **`Field.set_default`**: every documented form (`set_default(10)`, `set_default(["a"])`, `set_default(default_factory=...)`,
  neither / both → TypeError), on frontend vars, backend vars, storage vars (a storage value keeps storage name/options),
  inherited vars (changing the parent's field affects substates — as documented), ComponentState per-component defaults
  inside `get_component`, after instances exist (only new sessions / `reset()` see it), dev and prod (+ Redis workers).
  Run every sample in `git show v0.10.0a5:docs/vars/base_vars.md`, `docs/state_structure/component_state.md` and
  `docs/changelog/upgrading/upgrading-to-0-10.md` as written; every statement must be true.
- **Error message owner**: assignment over a var through the declaring state, a substate, a mixin-using state, a
  ComponentState instance class, an `add_var` dynamic var on parent and child (A4-01) — does the message name the right
  state and give a fix that actually works?

## Part 2 — re-run the identified class-state regressions on a5 (positive control on the broken version first)
- A3-01 / A3-02 / A3-04 / F-004 / N-039: class assignment and class patching raise (control a3 fails as recorded); the
  converted field-API repros (now with `set_default`) pass; thread stress on fields ends on the declared default.
- N-005: storage default via `set_default(rx.LocalStorage(..., name=...))` keeps storage, name, options — e2e dev and
  prod + Redis (copy `a4_class_state/apps/c4e2e`).
- N-008: `self._sneaky__name = 1` raises in dev; own/base/mixin mangled names fine.
- N-004: schema hash a5 == a4 == a3; a4 ↔ a5 pickle / disk / Redis interchange; 0.9.12 → a5 loads.
- A4-01 / A4-02 status on a5 (expected unchanged — report if #7519 changed them).
- Dev hot reload of a state file (5 edits) and AppHarness two apps — still clean.

Report in the structured format of AGENT_BRIEF.md with `REVERIFIED:` lines for F-004, N-005, N-039, N-008, N-004, A3-01,
A3-02, A3-04, A4-01, A4-02. Classify every issue as regression vs a4 / vs 0.9.12 / intended (documented) / pre-existing.
