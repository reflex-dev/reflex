# Fixtures

Reusable inputs for pre-release passes: our own sample apps, Playwright drivers, Python probes, pytest suites and run
scripts, consolidated from eight campaigns (one up-to-date copy of each, superseded copies dropped) and re-validated on
the released **reflex 0.10.0** (+ reflex-enterprise 0.9.7) on 2026-10-09. Each area's README lists every fixture with
the finding IDs it re-verifies (see `../REGISTRY.md`), exact run commands, the expected result on 0.10.0, known-benign
quirks, and which rows were re-run on 0.10.0 versus carried from the a5 records.

| area | covers | ports (frontend / backend) | size |
|---|---|---|---|
| [`hydration/`](./hydration/README.md) | browser storage and hydration (F-002, F-003 / cvstore), `sync=True` cross-tab storms and convergence (A3-11, A3-12, A4-03), router data and credential exposure (#7360), auth-package storage checks, reconnect / prenav / Redis-restart probes | 3140-3159 / 8140-8159, 3660-3679 / 8660-8679 | 0.45 MB |
| [`class_state/`](./class_state/README.md) | the state class model: class reads / writes and patching (F-001, F-004, N-005, N-039, A3-01/02/04), `set_default` and copy-at-definition (A5-01…05), add_var / auto-setter collisions (A4-01/02), dev guard (N-008), state-store compatibility (N-004), hot reload, AppHarness, docs samples, downstream greps | 3300-3339 / 8300-8339 | 0.3 MB |
| [`enterprise/`](./enterprise/README.md) | reflex-enterprise: OIDC cross-tab logout (N-032), auth suites, the 36-check auth matrix + MCP, expiry, deep links, protected storage (A3-09, A3-10), cookie sync (N-033), AG Grid (N-025, enterprise#273), demo smoke (dnd, flow, mantine, map, AG Grid), reflex-azure-auth | 3600-3639 / 8600-8639 (Redis 8629, IdP 8638, account stub 8639) | 0.6 MB |
| [`upgrade/`](./upgrade/README.md) | installs (N-001, F-005, F-006, F-014), in-place upgrades of reflex-examples apps incl. pickled Redis sessions and rollback, `.web/package.json` diffs, third-party sweep and auth-package demos, events suite, `reflex run --json` / signal lifecycle (A3-07, A3-08, F-007), upgrade-guide samples, blank-app smoke | 3460-3519 / 8460-8519 | 0.7 MB |

The orchestrator's preflight uses 3100-3119 / 8100-8119; independent verifiers take a free range from the area they
verify (e.g. 3320-3339 for class_state, 3660-3679 for hydration).

## Conventions

- **Run from a copy, never from the checkout.** Copy an area to scratch (`cp -r <area> $SB/apps/<area>/src`, or the
  area's own staging script) and run it there; scripts resolve their files from their own location. Python with a reflex
  checkout or worktree as the working directory imports the unreleased source.
- **`SB` is required** (the scratch root holding `envs/`, `apps/`, `downloads/`). Venv names default to what
  `../scripts/bootstrap_envs.sh` builds: `new`, `prev`, `ctrl-<version>`, `new-ent`, `prev-ent`, `driver`; override with
  the area's variables (`NEW`, `PREV`, `CTRL`, `ENT_NEW`, `DRIVER`, …). Areas that need extra test dependencies build
  their own venvs with their `build_*` script (class_state: pytest / pytest-mock; enterprise: a pytest + playwright
  driver venv).
- Every probe and app asserts which venv it runs in (`assert f"/envs/{EXPECT_VENV}/" in reflex.__file__`).
- Client-side commands use `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1`; the servers never get it.
- Outputs (logs, screenshots, frame dumps, JSON results) go to the area's work dir under `$SB/apps/`, never into the repo.
  The few `expected/` files are small baselines the drivers compare against.

## Inputs that are fetched or supplied at run time (never committed)

- **reflex-examples** at commit `ebe19ff00dfee36f9d67a9a584840c6745950b05`, and the auth demo packages
  (`masenf/reflex-local-auth@a61d50d8`, `masenf/reflex-magic-link-auth@352c675b`, `masenf/reflex-google-auth@753a0298`):
  `upgrade/bin/stage.sh` fetches them with `git archive` and applies our patches from `upgrade/examples/patches/` and
  `upgrade/tp/patches/`.
- **reflex-enterprise**: either a user-supplied offline wheel (`ENT_WHEEL`; it reports enterprise tier and needs no
  account) or the PyPI wheel (`ENT_SPEC`) with `CI=true`. The PyPI wheel refuses `reflex run --env prod` / `reflex export`
  for a logged-out user; `enterprise/account_stub.py` answers the account check on 127.0.0.1 for prod runs (set
  `ENT_ACCOUNT_STUB=0` to skip it with an offline wheel). The enterprise demos and the upstream auth tests come from a
  **reflex-enterprise checkout** at the release tag (`enterprise/grid/bin/fetch_demos.sh`,
  `enterprise/auth/a4auth/fetch_upstream.sh`; default `/home/user/reflex-enterprise`). Never commit the wheel or
  enterprise source.
- The mock OIDC IdP (`oidc-provider-mock`, port 8638) is started by the enterprise scripts; `upgrade/tp/az` reuses it.
- Only dummy credentials appear in the fixtures (`qa-fixture-token`, `qa-dummy-token`, a dummy Google client ID, the mock
  IdP's `az-secret`).

## Known maintenance points

- `class_state/probes/probe_docs.py` embeds 0.10.0 docs text: update its rows when the docs change (`docs_blocks.py`
  diffs every python block of a docs page between versions generically).
- `upgrade/up/scripts/clock_common.py` hardcodes October UTC offsets for the clock app: check after a DST change.
- reflex-examples, the auth demo packages and the enterprise demos are pinned: bump the pins deliberately and re-record
  the expected results when you do.
