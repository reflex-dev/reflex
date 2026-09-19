# rxe — FINDING-011 (reflex-dev/reflex#7214) and the reflex-enterprise half of FINDING-001 (reflex-dev/reflex#7211)

Status: **both defects fixed**, both verified end to end against the published reflex 0.9.12a1.

| | |
|---|---|
| Repository | `reflex-dev/reflex-enterprise` (internal) |
| Worktree | `/home/user/wt/rxe` (worktree of `/home/user/reflex-enterprise`) |
| Branch | `fix/reflex-0.9.12-compat`, 2 commits on top of `origin/main` (`592d5cc`) |
| Commits | `038c613` fix(auth): derive the OIDC cookie metaclass from the installed State metaclass (`Refs reflex-dev/reflex#7211`)<br>`c0e6b5d` fix(api): redact the session token after the router var split (`Fixes reflex-dev/reflex#7214`) |
| Patches | `patches/0001-*.patch`, `patches/0002-*.patch` (`git format-patch origin/main`) |
| Evidence | `evidence/` (before/after test runs, HTTP bodies with tokens masked, server logs, pyright output) |
| Ports used | 3980-3982 / 8980-8982, all released |
| Not done | never pushed, no PR opened, `reflex[db] >=0.9.6` pin left alone (see "Pins") |

---

## Defect 1 — `OIDCCookieMeta(BaseStateMeta)` conflicts with reflex 0.9.12's State metaclass

### Root cause

`reflex_enterprise/auth/oidc/state.py:26` imported `BaseStateMeta` and `:347` declared
`class OIDCCookieMeta(BaseStateMeta)`, used at `:381` by
`class OIDCAuthState(ConfigMixin, rx.State, mixin=True, metaclass=OIDCCookieMeta)`.

reflex 0.9.12 (reflex-dev/reflex#7136) changed `rx.State`'s metaclass:

```
reflex 0.9.11.post1  type(rx.State) = reflex_base.vars.base.BaseStateMeta
reflex 0.9.12a1      type(rx.State) = reflex.istate.validation._StateMeta   (a sibling subclass of BaseStateMeta)
```

Two sibling subclasses of `BaseStateMeta` cannot both be the metaclass of one class, so the
`OIDCAuthState` statement raises `TypeError: metaclass conflict` at import. Every
`AuthPlugin` / `MCPPlugin` / `EventHandlerAPIPlugin` app reaches that import from `post_compile`,
so the backend worker dies at startup while vite keeps serving the page.

### Fix

`reflex_enterprise/auth/oidc/state.py` — read the metaclass off the installed reflex:

```python
if TYPE_CHECKING:
    from reflex.vars import BaseStateMeta

    _StateMetaclass = BaseStateMeta      # keeps the __new__ override type-checked
else:
    _StateMetaclass = type(rx.State)     # BaseStateMeta <= 0.9.11, _StateMeta >= 0.9.12

class OIDCCookieMeta(_StateMetaclass):
```

One declaration that is correct on every reflex version, past and future — the metaclass
identity is never hard-coded. `BaseStateMeta` is the only such use in the package
(`grep -rn BaseStateMeta` returns exactly those two lines).

### Alternatives considered and rejected

* `class OIDCCookieMeta(type(rx.State))` directly — same runtime behaviour, but pyright cannot
  resolve a call expression as a base class, so the `__new__` override would stop being checked.
* Waiting for reflex-dev/reflex#7211 to be fixed upstream — reflex-enterprise 0.9.5 is already
  published with `reflex[db] >=0.9.6` and **no upper bound**, so rxe must be self-sufficient here.
  If reflex also fixes its side, this change stays correct (`type(rx.State)` would simply be
  `BaseStateMeta` again).
* Rebinding `reflex.vars.BaseStateMeta` (what the campaign's `oidc_meta_shim.py` does) — a global
  monkeypatch of the framework; fine for a QA probe, not a fix.

---

## Defect 2 — the REST/MCP session-token redaction was a silent no-op

### Root cause

`reflex_enterprise/plugins/event_handler_api.py:733 redact_router_session()` looked the session up
by var name:

```python
router_key = "router" + FIELD_MARKER
for sub in state_dict.values():
    if isinstance(sub, dict) and router_key in sub:
        sub[router_key] = _redact_router_value(sub[router_key])
```

reflex 0.9.12 (reflex-dev/reflex#7068) made `router` a property with **no backing field** and split
the data into five base vars. The root state dict on 0.9.12a1 is exactly
`is_hydrated`, `rx_router_session`, `rx_router_headers`, `rx_router_page`, `rx_router_url`,
`rx_router_route_id` — no `router` key at all, so the loop matched nothing and returned the dict
untouched. Everything downstream inherited the hole:

* `resolve_state_dict()` (`:901`) → `POST /_reflex/retrieve_state` and the MCP `reflex://state`
  resources (`mcp_builtin_resources.py:199`)
* `sanitize_agent_delta()` (`:852`) → the ndjson stream of `POST /_reflex/event/<state>/<handler>`,
  `queue_event()`'s merged delta, and the buffered MCP follow-up updates
  (`mcp_auth/tools.py:580`)
* `mcp_builtin_resources.py:374` single-var read — additionally special-cased the var **named**
  `router`, which does not exist on 0.9.12, while `rx_router_session` was readable by name and
  returned raw.

The leaked `client_token` is the server-generated session identifier the caller never presented
(it is not the bearer), and rxe's own comment at `_ROUTER_SESSION_SECRETS` calls handing it back a
session-takeover vector.

### Fix

`reflex_enterprise/plugins/event_handler_api.py`:

* new `_redact_session_value()` blanks `client_token` / `session_id` on session data in any of the
  three shapes it arrives in — the `SessionData` dataclass, reflex's mutable proxy around it, or the
  already-serialized dict (the `queue_event` path JSON-round-trips before sanitizing).
  `_redact_router_value()` now delegates to it instead of repeating the blanking logic.
* `redact_router_session()` walks each state's vars once and redacts on **either** signal:
  * the var name — `router` (reflex < 0.9.12) or `rx_router_session`, taken from
    `reflex_base.constants.route.ROUTER_SESSION` when the installed reflex has it (it does from
    0.9.12) and falling back to the literal otherwise;
  * the value's type — `RouterData` / `SessionData`. `isinstance` sees through reflex's mutable
    proxy (verified on both versions), so no unwrapping is needed in the loop.

  The type match is the part that matters for the next release: the defect being fixed is not
  "the name changed" but "a rename turned a security control into a no-op with no signal". A
  value carrying a `SessionData` is now redacted whatever var it sits under.
* the docstrings that described the redaction as keying on `router` were corrected
  (`strip_field_markers`, `sanitize_agent_delta`, `resolve_state_dict`).

`reflex_enterprise/plugins/mcp_builtin_resources.py` — the single-var read routes every value
through `redact_router_session()` instead of special-casing `var_name == "router"`. The function is
inert for anything that is not router data, so no var name is hard-coded on that path any more.

Public signature of `redact_router_session(state_dict) -> state_dict` (mutated in place) is unchanged,
as the brief required.

### Alternatives considered and rejected

* **Name-keyed only** (add `rx_router_session` beside `router`): the minimal change, and it fixes the
  reported leak. Rejected as the whole fix because it reproduces the exact failure mode — the next
  framework rename silently disables the redaction again. The name keys are kept (they are the only
  thing that can match an already-serialized dict) and the type match backs them up.
* **Type-keyed only**: cannot match the JSON-round-tripped dict on the `queue_event` path, where the
  session is a plain `{"client_token": ...}` dict by the time `sanitize_agent_delta` sees it.
* **Value scanning** (search the dict for the session token string): explicitly ruled out by the
  brief, and wrong — it would blank legitimate app data that happens to equal the token and would
  need the token in hand at redaction time.
* **Dropping the `rx_router_*` vars from API responses entirely**: a bigger behaviour change than the
  defect warrants; handlers and agents legitimately read the URL, page params, headers and client IP.

---

## Regression tests

`tests/units/plugins/test_event_handler_api.py` (7 new tests, + a `_secret_paths` walker modelled on
the campaign's `probe_router_redact.py` `find_token`):

| test | what it pins |
|---|---|
| `test_redact_router_session_blanks_split_session_var` | `rx_router_session` carrying a `SessionData` |
| `test_redact_router_session_blanks_serialized_split_session_var` | the same after JSON round-trip (dict) |
| `test_redact_router_session_blanks_legacy_router_var` | the legacy `router` var still redacts |
| `test_redact_router_session_blanks_serialized_legacy_router_var` | legacy var, serialized |
| `test_redact_router_session_blanks_real_root_state_dict` | **layout-agnostic**: builds the router the way `EventHandlerAPIPlugin` does, redacts a real `State(...).dict()`, asserts the sentinel appears nowhere — this is the campaign probe as a unit test, and it passes on whichever layout the installed reflex uses |
| `test_sanitize_agent_delta_blanks_session_and_strips_markers` | the delta surface, redaction before marker-stripping |
| `test_redact_router_session_blanks_proxied_session_under_any_var_name` | proxy transparency + the type match under a var name nobody hard-coded |

`tests/units/auth/test_oidc_state.py` (3 new, one parametrized over two provider states):

| test | what it pins |
|---|---|
| `test_oidc_cookie_meta_composes_with_installed_state_metaclass` | `issubclass(OIDCCookieMeta, type(rx.State))` and `isinstance(OIDCAuthState, OIDCCookieMeta)` |
| `test_oidc_cookie_meta_assigns_partitioned_cookie_descriptors[…]` | the metaclass still stamps `_oidc_<provider>_<attr>_partitioned` cookies — the behaviour that must not change with the base class |

### Before the fix (`evidence/before_fix.txt`, source stashed, new tests in place)

```
### unfixed SOURCE + new tests, v12 (reflex 0.9.12a1)
FAILED …::test_redact_router_session_blanks_split_session_var
FAILED …::test_redact_router_session_blanks_serialized_split_session_var
FAILED …::test_redact_router_session_blanks_real_root_state_dict
FAILED …::test_sanitize_agent_delta_blanks_session_and_strips_markers
FAILED …::test_redact_router_session_blanks_proxied_session_under_any_var_name
5 failed, 2 passed, 47 deselected

### unfixed SOURCE + new tests, v11 (reflex 0.9.11.post1)        4 failed, 3 passed
### unfixed SOURCE + new tests, repo .venv (reflex 0.9.6)        4 failed, 3 passed

### unfixed SOURCE, v12 — metaclass test module cannot even be collected
E   TypeError: metaclass conflict: the metaclass of a derived class must be a (non-strict) subclass …
ERROR tests/units/auth/test_oidc_state.py
```

The two legacy-`router` tests pass before the fix by design: they are the guard that the fix does not
regress reflex < 0.9.12.

### After the fix (`evidence/after_fix.txt`)

```
v12 (0.9.12a1)   new tests: 10 passed    touched modules: 159 passed    tests/units: 26 failed, 890 passed, 113 errors
v11 (0.9.11.p1)  new tests: 10 passed    touched modules: 159 passed    tests/units: 26 failed, 890 passed, 113 errors
.venv (0.9.6)    new tests: 10 passed    touched modules: 159 passed    tests/units:  9 failed, 1015 passed,  5 errors
```

The pre-existing failures are unchanged by this diff — measured directly: `tests/units` on the
**unfixed** tree is `26 failed, 880 passed, 113 errors` on v11 and `9 failed, 1005 passed, 5 errors`
in the repo `.venv`, i.e. exactly `+10 passed` and nothing else moves. See "Open questions" for what
those pre-existing failures are.

---

## End-to-end verification

All three servers were the **unmodified `demos/tickets`** app (`EventHandlerAPIPlugin`, no auth
configured), started with `CI=true REFLEX_TELEMETRY_ENABLED=false … reflex run` in dev mode.

### 1. In-process probe — the campaign's own `scripts/probe_router_redact.py`, unedited

```
fixed worktree + reflex 0.9.12a1      VERDICT OK
fixed worktree + reflex 0.9.11.post1  VERDICT OK
published rxe 0.9.5 + reflex 0.9.12a1 (envs/ent, untouched)   VERDICT LEAK
    -> ['.reflex___state____state.rx_router_session_rx_state_.client_token']
```

### 2. Import, without any shim

```
fixed worktree, v12:  import reflex_enterprise.auth.oidc.state  -> OK
fixed worktree, v11:  import reflex_enterprise.auth.oidc.state  -> OK
published rxe 0.9.5 + 0.9.12a1:                                 -> TypeError: metaclass conflict
```

### 3. HTTP — `evidence/e2e_http_912.txt`, bodies in `evidence/*_912_*.{json,ndjson}` (tokens masked)

`v_leak_http.py` (the campaign's verifier script, with the port and state name from argv and the
saved bodies masked) issues an anonymous app bearer at `POST /_reflex/auth/token`, then reads
`POST /_reflex/retrieve_state` and `POST /_reflex/event/tickets___tickets____ticket_state/seed`.

| | control: published rxe 0.9.5 + reflex 0.9.12a1 (port 8981, rxconfig metaclass shim — the published package cannot start without it) | fixed worktree + reflex 0.9.12a1 (port 8980, **no shim**) |
|---|---|---|
| backend starts | only with the shim | yes, unmodified demo |
| `retrieve_state` | `rx_router_session.client_token = <live UUID>` | **NONE (redacted)** |
| event delta (ndjson) | same live token | **NONE (redacted)** |
| leaked token == caller's bearer? | no — a server-side identifier the caller never had | — |
| verdict | `LEAK` | `OK` |

The fixed response keeps the var and blanks only the secrets, which is the point:

```json
"rx_router_session": {"client_token": "", "client_ip": "0.0.0.0", "session_id": ""}
```

### 4. HTTP on the previous framework — `evidence/e2e_http_911.txt`

Fixed worktree + reflex 0.9.11.post1 (port 8982): root state keys are `is_hydrated`, `router`;
`router.session.client_token` is `""`; both surfaces `NONE (redacted)`; verdict `OK`. The fix is
genuinely dual-compatible at the HTTP level, not only in unit tests.

---

## Checks run

| check | result |
|---|---|
| `ruff check .` | All checks passed! |
| `ruff format .` | 284 files already formatted (one test file was reformatted while writing) |
| `pyright reflex_enterprise tests` | 220 errors, 9 warnings — **byte-identical to the pre-change run**; `diff` of the two diagnostic lists is empty (`evidence/pyright_before.txt`, `evidence/pyright_after.txt`). The 220 are pre-existing. |
| `pytest tests/units` | see the table above; +10 passed, no other change, on all three reflex versions |
| `.pyi` stubs | not applicable — no component `create` signature or prop changed |

Ruff/format/pyright were run with the worktree's own `.venv` (reflex 0.9.6), the version CI uses.

---

## Pins

**`reflex[db] >=0.9.6` should stay as it is** — left unchanged, as the brief instructed, and I
recommend keeping it:

* Both fixes are dual-compatible by construction and are proven on reflex 0.9.6 (the floor),
  0.9.11.post1 and 0.9.12a1 — unit tests on all three, HTTP on the last two. Raising the floor to
  `>=0.9.12` would strand users on 0.9.6-0.9.11 for no benefit, and reflex-dev/reflex#7214's
  "ideally with a `reflex>=0.9.12` lower bound" suggestion assumes a 0.9.12-only fix, which this is
  not.
* No upper bound is needed either: neither fix names a reflex version, and neither reads a private
  reflex API. `type(rx.State)` and `reflex.istate.data.{RouterData,SessionData}` are stable public
  surface.
* **The already-published reflex-enterprise 0.9.5 has no upper bound on reflex**, so the moment
  reflex 0.9.12 ships to PyPI, `pip install -U reflex` on a deployed enterprise app takes it down
  (metaclass) and, if reflex fixes the metaclass on its side without rxe, silently starts leaking
  session tokens (redaction). That is a release-sequencing problem this branch cannot solve:
  **reflex-enterprise 0.9.6 carrying these two commits has to be on PyPI before, or at the same
  time as, reflex 0.9.12.** If it cannot be, reflex 0.9.12 should consider yanking-by-metadata the
  combination (e.g. rxe 0.9.5 + reflex >= 0.9.12) rather than leaving it to resolve.

---

## Risks and behaviour changes

* **A var whose value is a `RouterData`/`SessionData` is now redacted whatever it is called.** If an
  app deliberately exposed its own `SessionData`-typed var over the REST/MCP surface, its
  `client_token`/`session_id` will now come back blank. I judged this correct (it is the same secret,
  by the same type), but it is a behaviour change worth a maintainer's eye.
* **`redact_router_session()` now iterates every var of every state** instead of doing one dict
  lookup per state. `strip_field_markers()`, which runs on the same dicts on every one of these
  paths, already does exactly that, so the cost is a constant factor on an existing pass — two
  `isinstance` checks and a string compare per var, no allocation, no unwrapping.
* **The MCP single-var read now always calls `redact_router_session()`.** For a non-router var this
  builds one two-level dict and iterates one entry; the value is returned unchanged.
* **`reflex_enterprise.plugins.event_handler_api` now imports `reflex_base.constants.route` at module
  import** (inside a `try`). `reflex_base` is a hard dependency of reflex and the module is tiny.
* `reflex.vars.BaseStateMeta` is no longer imported at runtime by `auth/oidc/state.py` — it remains a
  public reflex export, nothing else in rxe used it, and it is still imported for type checking.

---

## Open questions for the maintainers

1. **Release sequencing** (the important one): see "Pins". reflex-enterprise 0.9.6 with these commits
   must not land after reflex 0.9.12.
2. **`tests/units` does not pass against reflex >= 0.9.11 in a single-process run.** Independent of
   this diff and identical before and after it: `26 failed, 113 errors` on both 0.9.11.post1 and
   0.9.12a1, versus `9 failed, 5 errors` on 0.9.6. Nearly all of them are
   `ReflexRuntimeError: A RegistrationContext can only be associated with a single App instance`
   from test fixtures that build several `App`s. That is a test-harness incompatibility with newer
   reflex, not a product defect, but it means CI on this repo will go red as soon as it moves off
   0.9.6 — worth its own issue before the 0.9.6 release.
3. **No regression test covers the MCP `_resolve_single_var` router path.** A meaningful one cannot
   be written today: on reflex ≤ 0.9.11 reading `router` was already redacted (it would pass before
   and after), and on 0.9.12a1 the surrounding `test_mcp.py` tests cannot run at all for reason (2).
   The path is covered indirectly — it now calls the unit-tested `redact_router_session()` with no
   var-name condition.
4. **Server logs still carry the client token.** `auth/oidc/state.py:1072` prefixes OIDC error log
   lines with `self.router.session.client_token`. Unchanged by this train (the `router` property read
   works fine on 0.9.12a1) and it is a server-side log, not an API response — flagging it only
   because it is the one remaining place the token is written out in full.
5. **Should reflex offer a redaction hook?** reflex-dev/reflex#7214 raises this. This fix does not
   need one, but a framework-declared "these vars are session secrets" list would let downstream code
   stop guessing at names entirely.

---

## Deviations from the brief

* The brief's commit trailer specified `Co-Authored-By: Claude Fable 5.1`. The session's own
  attribution instruction (which post-dates and explicitly replaces earlier attribution guidance)
  specifies `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`; the commits carry
  that line, with the same `Claude-Session:` trailer. Rewrite the trailer on cherry-pick if the
  other spelling is wanted.
* The `[mcp]` extra resolved fine in both scratch venvs (`mcp 1.30.0`), so nothing was dropped there.
  `oidc-provider-mock`, `pytest-mock` and `pytest-retry` had to be added to both venvs for
  `tests/units` to collect.
* A third venv was added beyond the two the brief asked for: `v12pub`
  (reflex 0.9.12a1 + the published rxe 0.9.5 wheel + `aiosqlite`) to run the HTTP **control**. The
  read-only `envs/ent` has no `aiosqlite`, so the `tickets` demo's `/seed` handler errors there and
  the event-delta surface could not be compared.

## Reproducing this

```bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad/fixes/rxe
# venvs: $SB/v12 (0.9.12a1 + editable worktree), $SB/v11 (0.9.11.post1 + editable worktree),
#        $SB/v12pub (0.9.12a1 + published rxe 0.9.5 wheel)
cd /home/user/wt/rxe
$SB/v12/bin/python -m pytest tests/units/plugins/test_event_handler_api.py tests/units/auth/test_oidc_state.py -q
$SB/v11/bin/python -m pytest tests/units/plugins/test_event_handler_api.py tests/units/auth/test_oidc_state.py -q
cd $SB && ./v12/bin/python probe_router_redact.py /fixes/rxe/v12     # VERDICT OK

# HTTP (ports 3980/8980 fixed, 3981/8981 control)
cd $SB/apps/tickets_fixed     && CI=true REFLEX_TELEMETRY_ENABLED=false $SB/v12/bin/reflex    run --frontend-port 3980 --backend-port 8980
cd $SB/apps/tickets_published && CI=true REFLEX_TELEMETRY_ENABLED=false $SB/v12pub/bin/reflex run --frontend-port 3981 --backend-port 8981
cd $SB && NO_PROXY=localhost,127.0.0.1 ./v12/bin/python v_leak_http.py http://localhost:8980 /tmp/rs.json /tmp/ev.ndjson
```

`apps/tickets_published/rxconfig.py` carries the QA-only metaclass shim (clearly marked, not a fix)
so the published package can start at all; `apps/tickets_fixed` is the demo unmodified.

---

## REVIEW

Independent adversarial review, 2026-09-19. Verdict: **approve — no blocking issues.** Everything the
fix agent claimed was re-run from scratch by the reviewer and reproduced; the two additions below are
the reviewer's own controls, not the fix agent's.

Scratch (reviewer): `.../scratchpad/fixes/rxe-review/`. Ports used: 3990-3992 / 8990-8992, all released.
Worktree left clean at `c0e6b5d`; the only tracked-file writes were `git checkout origin/main -- <3 src
files>` / `git checkout HEAD -- <same>` pairs for the before/after runs, each verified clean afterwards.

### 1. Diff against the repository's coding rules

Minimal and on-target: 3 source files, 2 test files, 2 news fragments, no drive-by refactors, public
signature of `redact_router_session()` unchanged. `_redact_session_value()` is a genuine de-duplication
(`_redact_router_value` now delegates instead of repeating the blanking), and moving `import dataclasses`
out of the function body to the module top is a strict improvement. Google-style docstrings with
Args/Returns on the new helper; no block comments; tests are module-level functions in the mirrored paths
(`tests/units/plugins/test_event_handler_api.py`, `tests/units/auth/test_oidc_state.py`); inline imports
inside tests match this file's established convention. News fragments: one per defect under the repo-root
`news/`, in the style and length of the existing `news/223.bugfix.md`. No `pyi_hashes.json` in this repo
and no component signature touched, so nothing to regenerate. The `try/except ImportError` around
`reflex_base.constants.route.ROUTER_SESSION` is **not** dead code — verified: the name exists on 0.9.12a1
and raises `ImportError` on both 0.9.11.post1 and 0.9.6.

### 2. Checks re-run by the reviewer (worktree `.venv`, reflex 0.9.6 — the version CI uses)

| check | result |
|---|---|
| `ruff check .` | All checks passed! |
| `ruff format --check .` | 284 files already formatted |
| `pyright` on the 3 touched modules | 46 errors — **diff against the same run with the sources reverted to `origin/main` is empty** (line numbers normalised). No new diagnostics. |
| `pytest` touched modules, reflex 0.9.12a1 / 0.9.11.post1 / 0.9.6 | 159 passed on each |
| `pytest tests/units`, reflex 0.9.6 | before 13F/1011P/5E → after 9F/1015P/5E; failure-name sets compared: **zero new failures**, 4 previously-failing new tests now pass (3 `test_highcharts.py` entries move in the other direction between runs — pre-existing flakiness, unrelated) |
| `pytest tests/units`, reflex 0.9.11.post1 (`--continue-on-collection-errors`) | before 30F/886P/113E → after 26F/890P/113E; **zero new failures**, identical 113 errors |

The 113 errors on reflex >= 0.9.11 are all `ReflexRuntimeError: A RegistrationContext can only be
associated with a single App instance` from fixtures that build several `App`s — identical before and
after this diff, confirming the fix agent's open question 2 (a test-harness incompatibility, not a
product defect, but this repo's CI goes red the moment it moves off reflex 0.9.6).

### 3. Regression tests are real (reviewer saw fail → pass)

Sources reverted with `git checkout origin/main -- <3 files>`, new tests left in place, reflex 0.9.12a1:

```
tests/units/auth/test_oidc_state.py  -> ERROR at collection
    reflex_enterprise/auth/oidc/state.py:381: in <module>
    TypeError: metaclass conflict: the metaclass of a derived class must be a (non-strict) subclass …

tests/units/plugins/test_event_handler_api.py  -> 6 failed, 48 passed
    FAILED …::test_redact_router_session_blanks_split_session_var
    FAILED …::test_redact_router_session_blanks_serialized_split_session_var
    FAILED …::test_redact_router_session_blanks_real_root_state_dict
    FAILED …::test_sanitize_agent_delta_blanks_session_and_strips_markers
    FAILED …::test_redact_router_session_blanks_proxied_session_under_any_var_name
    FAILED …::test_is_public_handler_filters_exempt_handlers   (pre-existing test, also metaclass)
```

Same revert on reflex 0.9.11.post1: 4 failed, 50 passed (the two legacy-`router` tests pass before and
after by design — they are the dual-compat guard). With the fix restored: 159 passed on 0.9.12a1,
0.9.11.post1 and 0.9.6.

### 4. End-to-end, re-run independently by the reviewer

In-process, the campaign's own unedited `scripts/probe_router_redact.py` from a neutral cwd:

```
fixed worktree + reflex 0.9.12a1      VERDICT OK
fixed worktree + reflex 0.9.11.post1  VERDICT OK
published rxe 0.9.5 + reflex 0.9.12a1 VERDICT LEAK
    -> ['.reflex___state____state.rx_router_session_rx_state_.client_token']
```

HTTP, unmodified `demos/tickets`, `CI=true REFLEX_TELEMETRY_ENABLED=false … reflex run` (dev), the
campaign's `verification/v_leak_http.py` with only `BASE` taken from argv:

| | fixed tree + 0.9.12a1 (:8990, **no shim**) | published rxe 0.9.5 + 0.9.12a1 (:8991, shim — it cannot start without one) | fixed tree + 0.9.11.post1 (:8992) |
|---|---|---|---|
| backend `/ping` | 200 | 200 | 200 |
| `retrieve_state` | `NONE (redacted)` | `client_token = cffcd5dc-…` | `NONE (redacted)` |
| event ndjson delta | `NONE (redacted)` | same live token | `NONE (redacted)` |
| var kept, secrets blanked | `"rx_router_session": {"client_token": "", "client_ip": "127.0.0.1", "session_id": ""}` | — | `"router": {"session": {"client_token": "", "client_ip": "0.0.0.0", …}}` |

The control confirms the verifier is not vacuous, and the leaked token is not the caller's bearer
(`equals bearer? False`). Scanned both fixed-tree bodies for UUID-shaped strings: the only hits are the
demo's own `ticket_id`s. Reviewer bodies: `rs_fixed_912.json`, `ev_fixed_912.ndjson`, `rs_pub_912.json`,
`ev_pub_912.ndjson`, `rs_fixed_911.json`, `ev_fixed_911.ndjson` under the reviewer scratch dir.

Metaclass, beyond the one-line import: the shipped `demos/oidc` app module (real provider states +
`register_auth_endpoints`) imports cleanly on the fixed tree under both 0.9.12a1 and 0.9.11.post1, and
`OIDCCookieMeta.__mro__[1]` is `reflex.istate.validation._StateMeta` on the former,
`reflex_base.vars.base.BaseStateMeta` on the latter. The same import on published rxe 0.9.5 + 0.9.12a1
still raises `TypeError: metaclass conflict`.

### 5. Attempts to break the fix (reviewer probes, run on 0.9.12a1 and 0.9.11.post1)

All pass identically on both versions — no exception, no mangling, no leak:

* `None` for a whole state; a var holding a list/str/int under the `router` and `rx_router_session` keys;
  a `router` dict with no `session`; `session = None` — all returned untouched.
* An app var named `router` holding `{"session": {"user": "bob"}}` (no secret fields) is **not** mangled.
* Idempotent: redacting twice is a no-op the second time.
* 500 session-valued vars in one state: all blanked, no "dictionary changed size during iteration"
  (values are replaced, never added/removed, so the in-loop `sub[key] = …` is safe).
* `strip_field_markers(redact_router_session(...))` keeps the redaction, i.e. the documented ordering holds.
* On a real `State(...).dict()`: only `rx_router_session_rx_state_` satisfies `isinstance(v, SessionData)`
  — `rx_router_headers`/`page`/`url`/`route_id` do not, so nothing else is touched.
* `dataclasses.replace` is safe on both classes: `SessionData` and `RouterData` are frozen with all
  fields `init=True` (including `RouterData._page`, which `replace` round-trips correctly).

Non-buggy paths checked by reading: `enqueue_stream_delta` **diverts** the target token's deltas into a
queue instead of emitting them to the websocket, and `get_pending_updates` redacts already-drained
updates, so the in-place mutation `redact_router_session` performs cannot reach a live browser client.
`resolve_state_dict` redacts before the exempt-state filter and before `strip_field_markers`, unchanged.
`grep` confirms no other reflex-enterprise surface serialises state to an API caller.

### 6. Nits (none blocking)

1. **The redaction is one level deep.** A `SessionData` nested inside a list or an inner dict is not
   found (`{"v": [SessionData(...)]}` still carries the token). Not reachable through any reflex layout
   past or present, and the pre-fix code was equally shallow — but the docstring's "wherever the session
   data lives" overstates it slightly. One clause would fix that.
2. **`_redact_router_value`'s dict branch returns unchanged when `router["session"]` is a dataclass**
   (a mixed serialized/live shape). Unreachable today — `.dict()` gives an all-live shape and the
   `queue_event` path an all-serialized one — but it is the one asymmetry left between the two branches.
3. **`sanitize_agent_delta` does `dict(delta)` and then mutates the inner per-state dicts in place**, so
   the caller's delta is modified despite the copy at the top level. Pre-existing, and harmless on all
   three current call sites (each owns its delta), but the shallow copy reads as if it were protective.
4. **No direct test of `mcp_builtin_resources._resolve_single_var`** — the fix agent's own open question
   3, and its reasoning is right: the path is exercised indirectly through the unit-tested
   `redact_router_session()` and now carries no var-name condition at all.
5. **The type-based match is deliberate defence-in-depth beyond the minimal name fix**, and with it the
   behaviour widening the report flags (any `SessionData`-typed var is blanked whatever it is called).
   The reviewer agrees with the call — the defect is "a rename silently disabled a security control", and
   the type match is what stops it recurring — but it is the one design choice in this diff a maintainer
   might want to weigh in on, and the report already surfaces it.
6. **Commit trailer** says `Claude Opus 5 (1M context)` where the brief asked for `Claude Fable 5.1`;
   rewrite on cherry-pick if the other spelling is wanted. Both patches in `patches/` were verified to
   reproduce `HEAD` byte-for-byte.

### 7. Would a maintainer merge this as-is?

Yes. Two real defects, correct root-cause analysis, minimal and version-agnostic fixes, regression tests
that fail first for the right reason, clean lint/format, no new type errors, no new test failures on any
of the three reflex versions, and end-to-end proof on both the fixed and the published trees. The fix
agent's open questions are the right ones — in particular **release sequencing**: reflex-enterprise 0.9.6
carrying these commits must reach PyPI no later than reflex 0.9.12, and the reviewer endorses keeping the
`reflex[db] >=0.9.6` floor (dual compatibility is proven at the HTTP level on 0.9.11.post1, not just in
unit tests).
