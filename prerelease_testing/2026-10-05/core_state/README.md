# Published alpha core/state campaign

`reflex==0.10.0a1` and `reflex-base==0.10.0a1`, explicitly pinned from `https://pypi.org/simple`, passed the covered core/state scenarios on Python 3.13.16 and local Chrome through Playwright 1.63.0. No framework source was installed, edited, or imported from this checkout.

## Plan and scope

Read the alpha changelog sections and the linked PR descriptions, isolate the published wheels, and build a small interactive dashboard combining state descriptors, frontend Vars, `rx.memo`, `ComponentState`, and `SharedState`. Run real browser assertions in dev and prod, collect console/network/websocket/server evidence, then probe descriptor and context edge cases directly against the same installed wheels. Follow-up reports cover [upload streams](upload/README.md) and [Redis recovery, rolling deploys and optional databases](redis/README.md).

## Verified results

| Scenario | Dev | Prod | Evidence |
| --- | --- | --- | --- |
| Parent/child independent base and computed vars; inherited event binds parent; parent computed invalidation | Pass | Pass | `evidence/{dev,prod}/browser-results.json` |
| Background substate in-place mutation of inherited frontend list and backend list; both flush and survive browser reload | Pass | Pass | Same browser results and websocket frames |
| Two `ComponentState` instances through one `@rx.memo` body: independent counts, backend mutable audit, computed checksum | Pass | Pass | Dashboard and client scenarios |
| Setter-only `@rx.memo` before conditional reader mounts; unmount/remount reader | Pass | Pass | Client scenario |
| Backend-derived client-state default; `.set`, `.set_value`, `.push`, `.retrieve` with callback | Pass | Pass | Client scenario |
| Nested structural `.deep_equals`, reordered keys, in-place nested mutation | Pass | Pass | Dashboard scenario |
| Negative array/string slices at `-1`, reactive Var bounds and step, positive and negative step length | Pass | Pass | Dashboard scenario |
| Nested `rx.match` event list and subsequent ordinary event | Pass | Pass | Dashboard scenario |
| JSON download preserves `#`, `%`, and Unicode | Pass | Pass | `evidence/{dev,prod}/escaped.json` |
| Direct page with `?self=1` hydrates and responds HTTP 200 | Pass | Pass | Dashboard scenario |
| Two independent browser contexts/tokens link a shared room; frontend/backend mutations fan out; private event stays private; reload, unlink and rejoin | Pass | Pass | Shared scenario |
| Base/backend/computed shadows; base-to-computed and computed-to-base shadows; descriptor ownership; ABC mixin, abstract enforcement and reserved `_abc_impl` | Pass | Pass | `evidence/backend-{dev,prod}.json` |
| Per-state pickle round trips, restored parent ownership, context `LookupError`, documented mode-specific undeclared attribute guard | Pass | Pass | Same backend evidence |

The final browser runs each recorded **71 text/download assertions**, plus hydration, input-value, absent-reader, HTTP-status and distinct-token checks. Dev had zero page errors, console errors, failed requests, or HTTP errors. Prod had zero page errors or observed failed requests/HTTP errors; Chrome's automatic `/favicon.ico` request logged one 404 because this minimal test app has no favicon asset. Its exact console location is retained. App websocket messages and server logs show no application exception.

## Provenance and reproduction

`evidence/provenance.json` records the interpreter, exact dependency graph, module origins and SHA-256 values. All six checked framework modules resolve below `/private/tmp/reflex-alpha-core-state/venv/lib/python3.13/site-packages`; `PYTHONPATH` is unset; no editable/direct-URL distributions are present. `evidence/freeze.txt` records all 45 distributions. Relevant PR descriptions are retained as JSON under `evidence/`.

All executable app copies and generated frontend files live outside the checkout under `/private/tmp/reflex-alpha-core-state/`. Copy these saved sources to an isolated app directory before executing them. Do not execute repository tests or install this checkout.

```sh
UV_CACHE_DIR=/private/tmp/reflex-alpha-core-state/uv-cache /Users/masenf/.local/bin/uv venv --python 3.13 /private/tmp/reflex-alpha-core-state/venv
UV_CACHE_DIR=/private/tmp/reflex-alpha-core-state/uv-cache /Users/masenf/.local/bin/uv pip install --python /private/tmp/reflex-alpha-core-state/venv/bin/python --index-url https://pypi.org/simple --prerelease allow 'reflex==0.10.0a1' 'reflex-base==0.10.0a1' playwright ruff
```

From the neutral app directory, initialize the blank app, place `core_probe.py` at `core_probe/core_probe.py`, and copy `rxconfig.py`, `browser_checks.py` and `provenance.py`. Execute every Python/framework command with `env -u PYTHONPATH REFLEX_DIR=/private/tmp/reflex-alpha-core-state/runtime UV_CACHE_DIR=/private/tmp/reflex-alpha-core-state/uv-cache /Users/masenf/.local/bin/uv run --no-project --python /private/tmp/reflex-alpha-core-state/venv/bin/python ...`.

- Initialization: `reflex init --name core_probe --template blank --no-agents`.
- Dev server: `reflex run --frontend-port 3111 --backend-port 8111`.
- Browser: `browser_checks.py /private/tmp/core-state-evidence http://localhost:3111`.
- Production: in a separate initialized app directory, change both ports and `api_url` in the copied config to 3112, then run `reflex run --env prod --frontend-port 3112 --backend-port 3112`. Prod requires one port for frontend and backend. Pass `http://localhost:3112` to the same browser script.
- Backend: execute the copied `backend_checks.py` with an output JSON argument, once with `REFLEX_ENV_MODE=dev` and once with `REFLEX_ENV_MODE=prod`.

The browser script launches its own headless local Chrome, uses fresh contexts, and chooses a unique shared room for each run. It leaves the user's browser tabs untouched. Package/runtime downloads and launching Chrome required the environment's approved network/process escalation.

## Limits and adversarial review

1. This is functional Chrome/macOS coverage, not a cross-browser matrix or a quantitative performance benchmark. It does not claim the reported compile/state CPU speedups.
2. The original pickle probe covers alpha-to-alpha per-state serialization. The [Redis follow-up](redis/README.md) also passes actual 0.9.12/0.10.0a1 rolling-worker persistence in both directions and reproduces the documented old-worker mutable-backend exception.
3. The Redis follow-up covers corrupt-pickle browser recovery, opportunistic-lock subscription readiness and contention, missing database-extra guidance, and bare SQLAlchemy migrations. Redis pool configuration, expiry, callable-default migrations, duration parsing, lifecycle JSON output and dynamic prod routes belong to other campaign reports.
4. Very large substate SSR stacks, ty-specific annotations, local (`global_ref=False`) client state across separately memoized components, and client `push`/`retrieve` with no mounted client-state user are not covered. The latter two limitations are explicitly described in PR #7286.

The initial app authoring mistakes (positional memo props, an implicit auto-setter, a mixin declaration missing its concrete mode, and treating a root pickle as a full tree) were corrected using the published API. They are not framework findings. No product regression was identified in this core/state cluster. Ruff check and format pass for the standalone reproduction sources; the local Ruff config permits standalone script stdout and omits namespace-package requirements.

The fresh bundled Bun installation appended a campaign-specific PATH block to `~/.zshrc`. The [Redis cleanup evidence](redis/evidence/bun-shell-cleanup.json) records its exact removal, with unrelated shell configuration preserved and no remaining owned-path references in checked shell files.
