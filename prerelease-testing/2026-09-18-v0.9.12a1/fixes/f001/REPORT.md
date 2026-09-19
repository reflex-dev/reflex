<!-- Written by the orchestrator from the fix agent's final response: the harness does not let subagents write
report files. Structured result and evidence: fixes/f001/evidence/, workflow wf_d7e6ae4d-a6e. -->

# f001 — FINDING-001 / reflex-dev/reflex#7211: State metaclass conflict

Branch `fix/finding-001-state-metaclass` in `/home/user/wt/f001`, 2 commits, **not pushed**. Base `origin/main` @ `4cba00435`.

| Commit | Subject |
| --- | --- |
| `6ab3edbc9` | `fix: keep BaseStateMeta as the metaclass of State` |
| `4290548fe` | `docs: note the router state-dict shape change from #7068` |

Evidence: `/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/fixes/f001/evidence/` (`01`–`09`, incl. `09-branch.diff`).

## 1. Root cause (confirmed independently)

- `reflex/istate/validation.py:90` (pre-fix) — `class _StateMeta(BaseStateMeta)`
- `reflex/state.py:629` (pre-fix) — `class BaseState(EvenMoreBasicBaseState, metaclass=_StateMeta)`
- `packages/reflex-base/src/reflex_base/vars/base.py:4036` — `class BaseStateMeta(ABCMeta)`, exported in `reflex_base.vars.__all__`

`type(rx.State)` stopped being `BaseStateMeta` and became `_StateMeta`, a *subclass*. A downstream `class M(BaseStateMeta)` is then a **sibling** of `_StateMeta`, so `class S(rx.State, metaclass=M)` fails.

The decisive mechanical detail — and the reason only one fix shape can work: CPython's `builtin___build_class__` resolves the most derived metaclass (`_calculate_meta`) **before** it calls any metaclass. The `TypeError: metaclass conflict` is raised without executing a single line of `_StateMeta.__new__`, `BaseStateMeta.__new__`, `__init_subclass__` or `__set_name__`. **No hook on `_StateMeta` can intercept it.**

reflex-enterprise 0.9.5 does exactly this at `reflex_enterprise/auth/oidc/state.py:347` (`class OIDCCookieMeta(BaseStateMeta)`) and `:381` (`class OIDCAuthState(ConfigMixin, rx.State, mixin=True, metaclass=OIDCCookieMeta)`).

## 2. The fix

Shape (a): `type(rx.State)` is `BaseStateMeta` again and the #7136 validation runs inside `BaseStateMeta.__new__`. Shape (b) was ruled out by the `__build_class__` detail above, not by taste.

`BaseStateMeta` lives in `reflex-base` and the reserved-name data is `reflex`'s `BaseState` namespace, so the check is installed as a hook rather than inlined:

1. `packages/reflex-base/src/reflex_base/vars/base.py` — module-level `_state_declaration_validator` plus `_set_state_declaration_validator()`. `BaseStateMeta.__new__` calls the validator (when installed) with `(bases, namespace)` as its first statement — before field collection, exactly where `_StateMeta.__new__` used to run.
2. `reflex/istate/validation.py` — `_StateMeta` replaced by the plain function `_validate_state_declaration(bases, namespace)` holding the identical body, plus `_install_state_validation(base_state)`. `_validate_state_name` / `_validate_inherited_members` / `_reserved_state_members` untouched.
3. `reflex/state.py` — `class BaseState(EvenMoreBasicBaseState):` and `_install_state_validation(BaseState)` immediately after the class body.

The guard changed from `isinstance(base, _StateMeta)` to `issubclass(base, BaseState)` — same set of classes, but it keeps working now that third-party metaclasses exist. `BaseState` itself is still unvalidated (the hook is installed after it exists). Non-state models on the same metaclass return early, covered by the pre-existing `test_non_state_models_keep_their_namespace`.

One incidental hardening inside the rewritten code: `base is not EvenMoreBasicBaseState and base is not object` instead of `base not in (...)`. `in` uses `==`, and the whole point is that user metaclasses (which may define `__eq__`) now reach this code; `_linearize_bases` already compares by identity for the same reason.

### Alternatives considered and rejected

- **Validate in `BaseState.__init_subclass__`** (no reflex-base change). Rejected: it runs after `BaseStateMeta.__new__` rewrote the namespace, so `__fields__`/`__own_fields__`/`__inherited_fields__` are always present and always look declared. The check would have to ignore them and would stop rejecting a state that declares `__fields__` itself — `test_reserved_state_var[__fields__]` would regress.
- **Keep `_StateMeta` and resolve the most derived metaclass from it.** Impossible, see §1.
- **Monkeypatch `BaseStateMeta.__new__` from reflex.** Same effect, no declared contract, breaks when reflex-base is imported without reflex.
- **Leave it to reflex-enterprise** (`OIDCCookieMeta(type(rx.State))`). Not sufficient: 0.9.5 is published and declares `reflex[db]>=0.9.6` with no upper bound, so shipping 0.9.12 as-is bricks every deployed enterprise auth/MCP/REST app on the next `pip install -U`. `BaseStateMeta` is public, so any third-party state metaclass breaks too.

## 3. Regression test

`tests/units/istate/test_validation.py` (the module holding the #7136 tests, mirroring the module changed):

- `test_state_metaclass_is_base_state_meta` — `type(BaseState) is BaseStateMeta` and `type(State) is BaseStateMeta`.
- `test_custom_state_metaclass[False|True]` — a `_CookieMeta(BaseStateMeta)` modelled on enterprise's `OIDCCookieMeta` (injects an annotated backend var, forwards `**kwargs`) used as `class CustomState(State, mixin=<param>, metaclass=_CookieMeta)`; asserts metaclass, `_mixin`, the injected field and a normal field.
- `test_custom_state_metaclass_validates_reserved_names` — #7136 still rejects `get_fields` through a custom metaclass.

Before the fix (`evidence/01-regression-test-before-fix.log`):

```
FAILED tests/units/istate/test_validation.py::test_state_metaclass_is_base_state_meta
FAILED tests/units/istate/test_validation.py::test_custom_state_metaclass[False]
FAILED tests/units/istate/test_validation.py::test_custom_state_metaclass[True]
FAILED tests/units/istate/test_validation.py::test_custom_state_metaclass_validates_reserved_names
4 failed, 34 passed in 0.12s
```

with `TypeError: metaclass conflict ...` on the three class statements. After the fix (`evidence/05`): `38 passed`. The 34 pre-existing #7136 tests pass on both sides.

## 4. End-to-end verification (campaign repro)

**4.1 `orch_probes/metaclass_probe.py`, copied unmodified** (`evidence/02-metaclass-probe.log`):

| interpreter | `type(rx.State)` | result |
| --- | --- | --- |
| `envs/prev` (0.9.11.post1) | `reflex_base.vars.base.BaseStateMeta` | 3 × OK |
| `envs/shared` (published 0.9.12a1) | `reflex.istate.validation._StateMeta` | **2 × FAIL** (BaseStateMeta-derived, and the `mixin=True` variant), 1 OK |
| `/home/user/wt/f001/.venv` (fixed) | `reflex_base.vars.base.BaseStateMeta` | 3 × OK |

The fixed tree matches 0.9.11.post1 line for line.

**4.2 reflex-enterprise 0.9.5 import** (`evidence/03-enterprise-import.log`). Failure side, throwaway venv, published packages only:

```
uv venv v_pub --python 3.11
uv pip install --python v_pub/bin/python --prerelease=allow 'reflex==0.9.12a1' reflex_enterprise-0.9.5-py3-none-any.whl
v_pub/bin/python -c "import reflex_enterprise.auth.oidc.state"
->   File ".../reflex_enterprise/auth/oidc/state.py", line 381, in <module>
       class OIDCAuthState(ConfigMixin, rx.State, mixin=True, metaclass=OIDCCookieMeta):
     TypeError: metaclass conflict: ...
```

Pass side, wheel installed `--no-deps` into the worktree venv (plus `asgiproxy joserfc httpx psutil 'mcp>=1.14.0,<2'`), `ent_import_probe.py` with only its `/envs/ent/` guard relaxed: **23/23 modules import, 13/13 attributes resolve, `BAD = 0`**, `type(OIDCAuthState) is OIDCCookieMeta`.

**4.3 MCPPlugin-only app** (`evidence/04-mcpapp-fixed.log`). `ent_mcp_oidc/apps/mcpapp` copied to scratch, run from the fixed venv on my own port:

```
cd <scratch>/apps/mcpapp && REFLEX_TELEMETRY_ENABLED=false CI=true \
  /home/user/wt/f001/.venv/bin/reflex run --backend-only --backend-port 8900
GET http://127.0.0.1:8900/ping -> 200 "pong"
```

`metaclass conflict` occurrences in the log: 0. `Traceback`: 0. The campaign recorded `000` on published 0.9.12a1 and `200` on 0.9.11.post1. Server stopped by pid; no listeners left on 3900-3909 / 8900-8909.

## 5. Checks

| check | result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format .` | 1628 files left unchanged |
| `uv run pyright reflex tests` | 0 errors, 0 warnings |
| `uv run pyright packages/reflex-base/src/reflex_base/vars/base.py` | 0 errors, 0 warnings |
| `uv run pytest tests/units --ignore=tests/units/reflex_cli` | **9126 passed, 20 skipped** |

Two caveats, both verified pre-existing on the unmodified tree:

- `tests/units/reflex_cli/**` — **207 failures on `origin/main` with no changes applied** (environment/credential dependent). Ignored above; unaffected by this change.
- `tests/units/test_state.py::test_state_manager_lock_warning_threshold_contend` failed once, then passed 4/4 including in the full run. Timing-based with non-CI thresholds (`LOCK_EXPIRATION = 300` ms, `LOCK_WARN_SLEEP = 0.15` s), flaky under load — other fix agents are running on this box. Nothing on the fix's path runs during that test.

No `.pyi` regeneration needed (no component `create` signature or prop changed); `pyi_hashes.json` untouched.

## 6. News fragments

- `news/+state-metaclass-conflict.bugfix.md` (reflex)
- `packages/reflex-base/news/+state-metaclass-conflict.bugfix.md` (reflex-base — its source changed)
- `news/+router-split-dict-shape.breaking.md` — second deliverable, separate commit, no code change

Shape change confirmed on both versions before writing the router note:

```
0.9.11.post1  State(...).dict()['reflex___state____state'] -> [..., 'router_rx_state_']
this branch   State(...).dict()['reflex___state____state'] -> [..., 'rx_router_headers_rx_state_',
              'rx_router_page_rx_state_', 'rx_router_route_id_rx_state_', 'rx_router_session_rx_state_',
              'rx_router_url_rx_state_']
```

Same for `get_delta()`. Neither `news/7068.breaking.md` (new base vars + shadowing error), `news/7068.deprecation.md`, `news/7068.performance.md` nor `packages/reflex-base/news/7068.*` tells a downstream reader of a serialized state which keys to read now — which is what broke enterprise's REST redaction (#7214).

## 7. Risks and behaviour changes

1. **`type(rx.State)` changes identity again**, back to what 0.9.11.post1 had. Code written against the alpha as `class M(type(rx.State))` keeps working (probe case 2 passes on all three interpreters).
2. **The validator now sees namespace mutations made by a subclass metaclass.** With `metaclass=M`, `M.__new__` runs before `BaseStateMeta.__new__`, so names *injected* by `M` are validated too. Stricter than #7136 was for the (previously impossible) custom-metaclass case, and correct. Enterprise's injected names (`_access_token_data`, `_id_token`, `_refresh_token`, `_granted_scopes`) are not reserved.
3. **The hook fires for every class `BaseStateMeta` creates**, including non-state models, returning after one `any(issubclass(...))` pass. Class creation is not a hot path; same shape as the old `isinstance` guard.
4. **reflex-base gains a private, underscore-prefixed extension point.** Single global validator; a second installer would replace the first. reflex-base imported without reflex runs with no validator, as before #7136.
5. `reflex/istate/validation.py` no longer exports `_StateMeta` — private, added in this unreleased alpha, unreferenced in the repo.

## 8. Open questions for the maintainers

1. **Should reflex-enterprise still change `OIDCCookieMeta` to derive from `type(rx.State)`?** This fix makes 0.9.5 work unmodified, so it is no longer urgent, but the framework now has a reason to keep `type(rx.State) is BaseStateMeta` permanently. If that is not a contract you want, say so in the changelog and fix enterprise too; if it is, the `BaseStateMeta` docstring should say it (I did not add that — it reads as an API commitment that is yours to make).
2. **One validator slot or a list?** I used a single slot: exactly one caller, and a list costs an allocation and an iteration per state class.
3. **`REFLEX_STATE_ALLOW_RESERVED_NAMES=1`, promised in #7136's description, does not exist in the source** (also noted by the campaign). Out of scope here — I did not add it — but the PR description and shipped behaviour disagree.
4. **`news/+router-split-dict-shape.breaking.md` is filed under reflex's `news/`** though the var split is described in `packages/reflex-base/news/7068.performance.md`. The observable shape is `state.dict()` / the delta, which is reflex's API — move it if you prefer.

## 9. Deviations from the brief

- **`REPORT.md` was not written.** This session's harness refuses report files from subagents ("Subagents should return findings as text… Include this content in your final response instead"), and I did not route around that block with a shell heredoc. The full report is this message; all logs and the branch diff are under `fixes/f001/evidence/`.
- **Commit trailer.** The brief specified `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; this session's own attribution instruction names the model actually doing the work, so the commits carry `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`. The `Claude-Session:` trailer is as specified. Retrailer the commits if the release tooling matches the exact string.
- The worktree venv now additionally contains `reflex-enterprise==0.9.5` (installed `--no-deps`, as directed) and its runtime deps. Venv only; the git tree is clean.


## REVIEW (independent adversarial reviewer — APPROVED; verdict recorded by the orchestrator from the agent's structured result)

- regression test seen to fail-then-pass by the reviewer: True
- e2e repro re-run by the reviewer on the fixed tree: True
- blocking issues: none
- nits:
  - Redundant second guard: reflex/istate/validation.py:22 adds a module global `_validated_state_base` and validation.py:107 re-checks `base_state is None` on every state class creation, although reflex_base/vars/base.py:4086 already guards on `_state_declaration_validator is not None` and the two are only ever set together in `_install_state_validation` (validation.py:122-130). A closure or `functools.partial(_validate_state_declaration, base_state)` installed by `_install_state_validation` would capture the base, drop the extra module global and remove a dead branch from the hot-ish path. CLAUDE.md: 'Don't repeat validation or be over-defensive'.
  - No test for the new reflex-base extension point under the mirrored subpackage path `tests/units/reflex_base/vars/test_base.py` (CLAUDE.md's mirrored-tests rule). Defensible - `_set_state_declaration_validator` is only observable with `reflex` installed, and `tests/units/istate/test_validation.py` covers the behaviour end to end - but a one-line test that `BaseStateMeta.__new__` calls an installed validator would pin the contract from the package that owns it.
  - Commit trailer deviates from the brief: both commits carry `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>` instead of the brief's `Claude Fable 5.1 <noreply@anthropic.com>`. The `Claude-Session:` trailer is correct. Re-trailer at cherry-pick time if the release tooling matches the exact string.
  - Behaviour note worth one line in the changelog fragment or the `BaseStateMeta` docstring: because the validator now runs inside `BaseStateMeta.__new__`, names *injected* by a downstream metaclass's `__new__` are validated too (I confirmed a metaclass injecting `dirty_vars` is now rejected with `StateValueError`). This case was mechanically impossible before, so it is not a regression, and reflex-enterprise 0.9.5's injected names (`_access_token_data`, `_id_token`, `_refresh_token`, `_granted_scopes`) are unaffected - but it is the one semantic difference from #7136 and is currently only recorded in the fix report, not in anything a downstream reader sees.
  - `news/+router-split-dict-shape.breaking.md` is a single 3-sentence paragraph (CLAUDE.md asks for 'a sentence or two'), and it sits in the repo-root `news/` although the var split itself is documented in `packages/reflex-base/news/7068.performance.md`. Both are defensible - the observable shape is `reflex`'s `state.dict()`/delta API - but the maintainer may want it trimmed or moved.

### Reviewer summary

APPROVED - no blocking issues. A maintainer would merge this as-is.

NOTE ON REPORT.md: I did not append the "## REVIEW" section. This harness instructs subagents not to write report/summary .md files and to return findings as text instead (the same block the fix agent hit). Everything below is ready to paste under a `## REVIEW` heading in /home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/fixes/f001/REPORT.md.

== WHAT I VERIFIED MYSELF (not taken from the fix agent) ==

1) DIFF REVIEW (git diff origin/main...HEAD, 7 files, +142/-37)
Minimal and on-target: `_StateMeta` deleted (grep confirms zero remaining references anywhere in the repo, including .pyi and pyi_hashes.json), `BaseState` back to `class BaseState(EvenMoreBasicBaseState)` (reflex/state.py:629), the #7136 body moved verbatim into `_validate_state_declaration` (reflex/istate/validation.py:94-119) and invoked as the first statement of `BaseStateMeta.__new__` (packages/reflex-base/src/reflex_base/vars/base.py:4086-4087) - the same point in the sequence `_StateMeta.__new__` occupied. No drive-by refactors, no `isinstance` workarounds, Google-style docstrings on all three new functions, plain inline comments only (no section banners), tests at module level in the mirrored path `tests/units/istate/test_validation.py`, news fragments for both touched packages (`news/` + `packages/reflex-base/news/`). `pyi_hashes.json` correctly untouched - none of the three touched files appear in its 122 entries and no component signature changed. `Callable` is imported at runtime (collections.abc, base.py:19) and the module has `from __future__ import annotations`, so the new module-level annotation is safe on the declared `requires-python >=3.10`.
Guard-equivalence: the predicate flip from `isinstance(base, _StateMeta)` to `issubclass(base, base_state)` selects the identical class set (`_StateMeta` was only ever the metaclass of `BaseState` and its descendants), and `BaseStateMeta.__new__` already calls `issubclass(base, EvenMoreBasicBaseState)` over the same `bases` two lines later, so the new `issubclass` introduces no new failure mode. The `base not in (...)` -> `base is not ...` change is identity-only and is justified now that user metaclasses (which may define `__eq__`) reach this code; `_linearize_bases` already does the same.
Packaging skew risk checked and cleared: the fix splits across `reflex` and `reflex-base`, but published metadata pins `Requires-Dist: reflex-base==0.9.12a1` exactly (and pyproject.toml:390-393 declares a lockstep with `pin-exact = true`), so no install can pair a new `reflex` with a `reflex-base` lacking `_set_state_declaration_validator`.

2) CHECKS RE-RUN BY ME FROM /home/user/wt/f001
- `uv run ruff check .` -> All checks passed
- `uv run ruff format --check .` -> 1628 files already formatted
- `uv run pyright reflex tests` (full, in foreground) -> 0 errors, 0 warnings, 0 informations
- `uv run pyright` on the four touched modules -> 0 errors
- `uv run pytest tests/units --ignore=tests/units/reflex_cli` -> 9126 passed, 20 skipped (126s), run TWICE: once with `-p no:randomly` and once with the default random ordering. No flakes either time, including `test_state_manager_lock_warning_threshold_contend` which the fix agent saw flake.
- `uv run pytest tests/units/istate tests/units/test_state.py` -> 368 passed; `uv run pytest tests/units/reflex_base` alone (no `reflex` import path) -> 489 passed, 1 skipped.

3) REGRESSION TEST IS REAL - I SAW FAIL-THEN-PASS
Single shell chain, source-only revert, restored in the same chain:
  git checkout origin/main -- packages/reflex-base/src/reflex_base/vars/base.py reflex/istate/validation.py reflex/state.py
  uv run pytest tests/units/istate/test_validation.py -q -p no:randomly
  -> 4 failed, 34 passed; all four with `TypeError: metaclass conflict: the metaclass of a derived class must be a (non-strict) subclass of the metaclasses of all its bases` raised on the class statements at test_validation.py:235 and :252
  git checkout HEAD -- <same three paths>  -> `git status --porcelain` empty, `git diff HEAD --stat` empty
With the fix: `38 passed`. The 34 pre-existing #7136 tests are green on both sides.

4) E2E CAMPAIGN REPRO RE-RUN BY ME (ports 8910, telemetry off)
- `orch_probes/metaclass_probe.py` copied unmodified, three interpreters:
    fixed worktree venv -> `type(rx.State) = reflex_base.vars.base.BaseStateMeta`, 3x OK
    envs/shared (published 0.9.12a1) -> `type(rx.State) = reflex.istate.validation._StateMeta`, 2x FAIL (BaseStateMeta-derived, and the `mixin=True` variant)
    envs/prev (0.9.11.post1) -> 3x OK
  The fixed tree matches 0.9.11.post1 line for line.
- reflex-enterprise 0.9.5 (installed --no-deps in the worktree venv): `import reflex_enterprise.auth.oidc.state` succeeds; `type(OIDCAuthState) is OIDCCookieMeta`; `OIDCCookieMeta.__bases__ == (BaseStateMeta,)`. Full `ent_import_probe.py` (only its `/envs/ent/` assert relaxed): 22/22 modules OK, 13/13 attributes OK, BAD = 0.
- `ent_mcp_oidc/apps/mcpapp` (MCPPlugin-only) copied to scratch, `CI=true REFLEX_TELEMETRY_ENABLED=false .venv/bin/reflex run --backend-only --backend-port 8910` -> `GET /ping` 200 `"pong"`; 0 occurrences of `metaclass conflict` and 0 `Traceback` in the log. Campaign recorded 000 on published 0.9.12a1. Server killed by its own pid; `ports.py` shows no listeners left in 3900-3919/8900-8919.

5) REGRESSION HUNT - I TRIED TO BREAK IT
- Behaviour parity harness, 11 #7136 cases run on BOTH published 0.9.12a1 and the fixed tree, identical results on every one: plain mixin before/after the state, model mixin before/after the state, direct reserved var, handler shadowing a builtin, non-state model keeping its namespace, dataclass mixin, normal parent/child substate, `rx_router_url` shadowing (`BaseVarShadowsInheritedVarError`). The validation surface is unchanged.
- Adversarial cases on the fixed tree: reserved name via a custom metaclass -> StateValueError; reserved name *injected* by a custom metaclass -> StateValueError (stricter, see nit 4); handler shadowing via custom metaclass -> EventHandlerShadowsBuiltInStateMethodError; non-state model on `BaseStateMeta` -> unvalidated, as intended; `rx.ComponentState` with a custom metaclass -> constructs and `.create()` works; `mixin=True` state mixin with a custom metaclass consumed by a real state -> `shared` in `User.vars`; a metaclass overriding `__eq__` to always return True -> still constructs correctly (the identity-comparison hardening earns its place); ABC mixin -> fine; `add_var` with a reserved name -> still rejected.
- Runtime, not just construction: a `mixin=True` state with a `BaseStateMeta`-derived metaclass, consumed by a concrete substate - vars/backend_vars correct (`_injected` from the metaclass lands in `backend_vars`), delta correct, `_serialize()`/`_deserialize()` round-trip preserves values and class identity with the custom metaclass intact, and `pickle.loads(pickle.dumps(cls)) is cls`. That covers the redis/disk state-manager path.
- Performance: the hook costs ~0.4 us per non-state `BaseStateMeta` class creation (14.20 vs 13.79 us/class, best of 3 x 4000) - and the fixed tree is actually *faster* than published 0.9.12a1 on both class-creation benchmarks (16.20 us/class non-state, 1730 vs 1620 us/class for a state subclass), since a metaclass layer was removed. Class creation is not a hot path either way.

6) SECOND DELIVERABLE (`news/+router-split-dict-shape.breaking.md`)
Claim independently verified on 0.9.11.post1 vs the fixed tree: `State(...).dict()` goes from `['router_rx_state_']` to the five `rx_router_{headers,page,route_id,session,url}_rx_state_` keys, and `get_delta()` shows the same five once the router vars are dirty (0.9.11.post1: `['router_rx_state_']`). I also confirmed no existing fragment covers it - `news/7068.breaking.md` documents the new base vars and the shadowing error, `news/7068.performance.md` and `packages/reflex-base/news/7068.performance.md` document the storage change, none tells a reader of a serialized state which keys to read. The gap is real and the wording is accurate.

VERDICT: the root-cause analysis is correct (the conflict is raised by `__build_class__`/`_calculate_meta` before any metaclass code runs, so shape (b) from the brief is genuinely impossible, not merely unattractive), shape (a) is implemented minimally, the #7136 behaviour is bit-for-bit preserved, and the release blocker is gone on the real enterprise surface. Cherry-pickable as two clean commits (`6ab3edbc9`, `4290548fe`); worktree is clean at `4290548fe`.
