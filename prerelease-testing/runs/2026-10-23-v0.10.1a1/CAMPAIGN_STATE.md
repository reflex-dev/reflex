# Campaign state (compact context) — 0.10.1a1 pre-release pass (2026-10-23)

Agents read this first. Then `AGENT_BRIEF.md` (this directory), then your fixture area's README under
`prerelease-testing/fixtures/<area>/`.

## What is under test
- **reflex 0.10.1a1 + reflex-base 0.10.1a1**, released from `r/pre-2026.10.23-40018338326` at `c5f7cf3e4` (tag
  `v0.10.1a1`; branch point = `main` @ `656e8c7e9`). Re-released in this train (all `a1`): reflex-components-code /
  -core / -dataeditor / -moment / -radix 0.10.1a1, reflex-components-lucide 1.1.1a1, reflex-hosting-cli 0.2.1a1,
  reflex-release 0.2.1a1, reflex-build-sdk 0.1.1a1. Unchanged: gridjs / markdown / plotly / react-player / recharts /
  sonner / docgen 0.10.0, hatch-reflex-pyi 0.10.0, reflex-otel 0.2.0.
- Preflight (orchestrator): `check_release_versions.py --ref v0.10.1a1` → 20/20 published (wheel + sdist).
  `.pyi` audit → PASS, 122 stubs, wheel == sdist, no foreign stubs. Published reflex wheel pins
  `reflex-base==0.10.1a1`, `reflex-components-{moment,radix}>=0.10.1a1`, but only `>=0.10.0` on
  `reflex-components-{core,code,dataeditor}` and `>=1.1.0` on lucide (a user can end up with reflex 0.10.1a1 + core
  0.10.0: worth checking). All 77 changed published source files byte-identical between the tag and `envs/new`.
  Blank app dev + prod: clean.
- **reflex-enterprise 0.9.8** (already released; PyPI wheel, needs `CI=true`; requires `reflex[db]>=0.9.6`). No offline
  wheel this pass: prod / export with the PyPI wheel needs `fixtures/enterprise/account_stub.py`.
- Previous release (baseline): **reflex 0.10.0**. Also released since: a 0.9.13 backport (`v0.9.13`).

## What changed since 0.10.0 (`git log --oneline v0.10.0..v0.10.1a1`; read every CHANGELOG.md top entry on the tag)
| PR | Change | Risk (what to hunt) |
|---|---|---|
| #7079 | prod granian workers forked from a supervisor that preloaded the app; `REFLEX_BACKEND_START_METHOD` | fork-safety (threads, DB engines, Redis clients, asyncio loops created at import), per-worker state, Redis multi-worker delivery, signals / shutdown, memory |
| #7113 | dev reload worker forked from the supervisor (no forkserver); `REFLEX_STRICT_HOT_RELOAD` | hot reload correctness (stale modules, new pages/states, broken-then-fixed module), CLI-16 |
| #7542 / #7538 / #7558 | worker cap 8; no "Unexpected exit" log; `--json` forwards SIGINT | lifecycle / signal fixtures |
| #7453 / #7052 | prod frontend work serialized per `.web`; atomic + locked `reflex.json` | concurrent `reflex export` / `run --env prod`; read-only `REFLEX_DIR` |
| #7304 (#7258) | app package without `__init__.py` | the old "no dispatch function" registry item |
| #7273 | frontend state updates keep identity of unchanged objects (structural sharing) | stale UI: in-place mutations, list reorder, nested dict/dataclass, foreach keys, memo, client_state |
| #7441 | state read from ONE shared frontend store, providers flattened | every state read path: substates, ComponentState, memo, custom components / hooks, enterprise |
| #7586 | hooks render in declaration order; `VarData(position=)` / `HookPosition` deprecated | custom components with `add_hooks`, third-party / enterprise components, window_event_listener, clipboard |
| #7234 | opt-in `react_compiler` / `REFLEX_REACT_COMPILER` | dev + prod builds and runtime with it ON; off by default must be unchanged |
| #7553 | state-schema hash on connect; prod reloads once / banner on mismatch | false positives (identical builds, hot reload, multiple workers, prerender), reload loops, cooldown |
| #7435 | unknown frontend substates skipped | mixed-version frontends |
| #7645 / #7639 | React 19.3.1, Vite 8.3.4, PostCSS, radix primitives bumps; Bun 1.4.4 | builds, warnings, upgrade path, `.web/package.json` diff |
| #7386 | `rx.form.FormData` multi-value, TypedDict coercion; id-based form fields DEPRECATED (checkbox/switch now submit "on") | behavior change for existing forms (dict handlers, checkbox bool), compile warnings, sliders, controlled inputs |
| #7614 | **breaking**: `router.session.client_ip` ignores X-Forwarded-For unless `trusted_proxy_hops` | security: spoofing, off-by-one hops, IPv6, multiple headers, prod vs dev |
| #7588 / #7602 | repeated request headers combined; non-UTF-8 header bytes accepted | cookie handling, #7360 redaction still intact |
| #7551 / #7605 | oversized hydrate payload reported; backoff when the connection closes pre-connect | big LocalStorage / cookies; reconnect loops; toast |
| #7545 / #7568 / #7603 / #7572 | sync=True vars sharing a name; storage-dependent computed vars once per load; storage type validation; hydration override dependents | HYD-01/02/08/09 regressions |
| #7407 | global `rx._x.client_state` readers mounting late | cond / late-mounted readers |
| #7415 / #7585 / #7447 | cancel page-load chains on disconnect; background task rehydrates expired session; background handler drops dispatch-time tree | on_load side effects, Redis expiry, memory |
| #7500 / #7636 / #7592 / #7410 | dict.values()/items() mutation tracking; rx.Model args; pydantic introspection; async var filter | mutable proxies, warnings |
| #7402 / #7401 / #7443 / #7547 / #7626 / #7606 | event sequences; EventCallback binding; modify_state errors; NameError in annotations; BaseStateMeta docs; `get_leaf_vars` | class-state model (STATE-05, STATE-11…21) |
| #7518 / #7565 / #7573 / #7405 / #7544 / #7587 | Unicode StringVar ops; `(-x) ** 2`; tailwind `important`; CDN sub-path fallback; error events without Error | compiled JS correctness |
| #7345 / #7593 / #7418 / #7438 / #7629 | checkbox_group/cards controlled value + form props; radio_cards as_child removed; input auto_complete; progress ARIA; accordion SSR warning | components |
| #7591 / #7607 / #7604 / #7437 | moment_provider + options; data_editor column defaults; lucide import_var; shiki transformers | components (CMP-11 moment locale) |
| #7406 / #7413 / #7419 / #7403 / #7401 | typing (pyright / ty) | user-visible type errors |
| #7411 / #7440 / #7566 / #7556 | sdists installable with uv; reflex.model without greenlet; `-D` dev deps; `reflex init` app_name check | packaging / upgrade |
| #7340 / #7390 / #7434 / #7463 / #7546 / #7452 / #7450 | hosting CLI: tier table, log formatting, token guidance, deploy scaling retry, auth status, non-interactive deploy, archive speed | needs a fake control plane |
| reflex-release 0.2.1a1 (#7645) | allow towncrier 26 | `reflex-release` commands with towncrier 26 |
| reflex-build-sdk 0.1.1a1 (#7463) | `transports.default_transport()` | API |

## Findings to re-verify (from `REGISTRY.md`; positive control FIRST)
The "re-verify on every pass" shortlist (REGISTRY.md §Re-verify, items 1–17), plus: the registry's open-unfiled
"no dispatch function when the app package has no `__init__.py`" (claimed fixed by #7304) and C21
`rx.remove_local_storage` syncing `null`; F-017 / F-008 / F-010 context items (report only if changed).
Known and filed (do NOT re-report unless changed): every `filed, open` row in `REGISTRY.md` relevant to your item.

## Items and ports
| item | covers | ports (frontend / backend) |
|---|---|---|
| preflight (orchestrator) | publish, wheel contents, `.pyi` audit, blank-app smoke | 3100-3119 / 8100-8119 |
| `process_model` | #7079 #7113 #7542 #7538 #7558 #7453 #7052 #7304, lifecycle, Redis multi-worker, CLI-16, EVT-04 | 3200-3219 / 8200-8219 |
| `frontend_store` | #7273 #7441 #7586 #7234 #7553 #7435 #7645 + compiled-JS fixes | 3220-3239 / 8220-8239 |
| `hydration_net` | #7551 #7605 #7545 #7568 #7603 #7572 #7407 #7588 #7602 #7614, HYD-01/02/08/09, #7360 | 3140-3159 / 8140-8159 |
| `events_state` | #7386 forms, #7402 #7401 #7415 #7585 #7447 #7500 #7636 #7592 #7410 #7443 #7547 #7626 #7606, STATE-05/11…21 | 3300-3319 / 8300-8319 |
| `components_typing` | radix / moment / dataeditor / lucide / code changes, typing changes, CMP-11, CMP-31 | 3240-3259 / 8240-8259 |
| `enterprise` | rxe 0.9.8 on 0.10.1a1 vs 0.10.0: demos, auth, AG Grid, MCP, ENT-01/02/16/29/30, HYD-15 | 3600-3639 / 8600-8639 |
| `upgrade_packaging` | reflex-examples 0.10.0 → 0.10.1a1 in place, package.json diff, Python 3.11–3.15, pip/uv, sdists, mixed sibling floors, third-party sweep, PKG-05/08/09 | 3460-3499 / 8460-8499 |
| `cloud_cli` | reflex-hosting-cli 0.2.1a1 against a fake control plane, deploy archive, reflex-release 0.2.1a1 + towncrier 26, build-sdk | 3260-3279 / 8260-8279 |
| verifiers | independent reproduction | 3700-3799 / 8700-8799 (20-port block each, assigned in the brief) |

## Environment
- `SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa`; venvs `new` (0.10.1a1), `prev`
  (0.10.0), `new-ent` / `prev-ent` (+ reflex-enterprise[mcp] 0.9.8 + oidc-provider-mock), `driver`; all Python 3.12,
  `pydantic<2.15` (2.14.1), sqlalchemy 2.1.6, granian 2.8.5. Build extra venvs as `$SB/envs/<item>-<name>`.
- 4 CPUs, 15 GB RAM, ~18 GB free disk: delete `.web/` and `node_modules/` after use; at most one app server set per agent.
- Chromium `/opt/pw-browsers/chromium`. `$SB/downloads/`: reflex-examples, reflex-local-auth, reflex-magic-link-auth,
  reflex-google-auth (pinned commits in `fixtures/upgrade/README.md`). reflex-enterprise checkout at
  `/home/user/reflex-enterprise` (tag `v0.9.8` fetched; READ only, copy demos out).
- Artifacts: `prerelease-testing/runs/2026-10-23-v0.10.1a1/<item>/` in worktree `/home/user/wt-testing` (branch
  `testing/prerelease`; the orchestrator commits).
