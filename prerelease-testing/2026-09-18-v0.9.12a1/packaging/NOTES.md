# packaging — Phase 5 audit of the 2026-09-18 train (orchestrator, 2026-09-19)

## Publication and stubs

`check_release_versions.py --ref origin/r/pre-2026.09.18-35410916948`: **19/19 packages published**
(wheel + sdist) — `specs.txt`. Chained with `&&` into `audit_pyi.py --manifest-ref <ref>`: **PASS, 122 stubs
ship correctly in both wheel and sdist, no foreign stubs** (`audit_pyi.log`; per-package counts match
`pyi_hashes.json`: reflex 3, core 36, radix 65, recharts 6, react-player 3, code 2, one each for
dataeditor/gridjs/lucide/markdown/moment/plotly/sonner, none for the pure-python packages).

## Dependency pins in the published `reflex-0.9.12a1` wheel (`pins_and_sdist.log`)

| requirement | published | changelog / pyproject intent |
|---|---|---|
| `reflex-base` | `==0.9.12a1` (exact) | lockstep `pin-exact = true` — OK |
| `reflex-components-moment` | `>=0.9.4` | floor raised to the 0.9.4 stable that carries the react-moment 2.0.2 migration — OK |
| `reflex-components-radix` | `>=0.9.9` | floor; the 0.9.10a1 alpha is NOT required — a bare `pip install --pre reflex==0.9.12a1` still resolves it (uv `--prerelease=allow` too, verified in `../smoke/NOTES.md`), but an in-place `--upgrade` of an old venv can leave 0.9.9 |
| `reflex-components-core` | `>=0.9.6` | floor; same remark (0.9.10a1 carries #7124/#7130/#6860 fixes) |
| other component packages | `>=0.9.0` | floors unchanged |
| `reflex-hosting-cli` | `>=0.1.71` | 0.1.72 stable resolves |
| `granian[reload]` | `>=2.7.4` | resolves 2.8.3 |
| `reflex-components-core` → `reflex-base` | `>=0.9.9` | core 0.9.10a1 accepts older reflex-base; it imports `CommonTag` (#7121) — see the breaking-surface note below |

Resolution matrix (`python_matrix.log`): `uv pip install --prerelease=allow --dry-run reflex==0.9.12a1`
resolves the identical all-alpha set on Python **3.10, 3.12, 3.13, 3.14** (42/40 packages). Python 3.15.0rc2 is
installable via `uv python install 3.15`; the `vars_typing` cluster tries the train on it.

## sdist installability

- `uv pip install reflex-0.9.12a1.tar.gz` **fails to build**: `reflex-base references a workspace in
  tool.uv.sources ... but is not a workspace member` — the published sdist still carries the monorepo
  `[tool.uv.sources]`. **Pre-existing** (previous campaign FINDING-006, filed as reflex-dev/reflex#7088), not new.
- `pip install reflex-0.9.12a1.tar.gz` works and resolves the same alpha set.
- `uv pip install reflex_base-0.9.12a1.tar.gz` works.

## Breaking-change surface (downstream grep)

Enterprise wheel 0.9.5 grepped for names this train touched (`../orch_probes/NOTES.md` has the import sweep):
`RouterData`/`router_data`/`.router` (event_handler_api, auth, oidc), `get_delta` override (oidc state),
`dirty_vars` (auth), `EventChain.create` (dnd, map), `VarData` (flow), `bundled_libraries`
(`rxe.vars.get_bundled_libraries` with the RegistrationContext path), `lazy_loader.attach`, `console.*`,
and `from reflex.vars import BaseStateMeta` (oidc) — the last one is the confirmed import regression.

`reflex-local-auth 0.5.0` and `reflex-global-hotkey 1.2.3` (`thirdparty/probe_imports.py`): every
`from reflex... import ...` line in their wheels executes on 0.9.12a1 and on 0.9.11.post1 (5 distinct
lines: `reflex.utils.imports`, `reflex.event.EventSpec`, `reflex.event.{EventHandler,EventType,key_event,KeyInputInfo}`,
`reflex.{Fragment,Var}`); their `rx.*` attribute surface (`rx.LocalStorage`, `rx.session`, `rx.set_focus`,
`rx.set_value`, `rx.app.ComponentCallable`, ...) resolves. Runtime behavior is covered by `up_examples_b`.

`reflex_components_core.datadisplay` (#7124) and the `CommonTag` rename (#7121) are exercised by the
`components_bumps` cluster.
