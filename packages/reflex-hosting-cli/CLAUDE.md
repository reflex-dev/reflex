# reflex-hosting-cli — Coding Agent Guidelines

Standalone workspace package that ships the `reflex cloud ...` CLI and the programmatic surface (`login`, `logout`, `deploy`) imported by the main `reflex` framework. Published to PyPI independently from `reflex` and tagged with prefix `reflex-hosting-cli-` (see `pyproject.toml` → `uv-dynamic-versioning`).

The root project's `CLAUDE.md` still applies (uv, ruff, pyright, Google-style docstrings, no block comments). This file adds package-specific rules.

## Layout

```
src/reflex_cli/
  cli.py              # v1 entry — DISABLED, calls disabled_v1_hosting()
  deployments.py      # v1 deployments group — DISABLED
  __init__.py
  constants/          # base (Reflex/LogLevel/Dirs), compiler, hosting (URLs, version pins)
  core/
    config.py         # Config dataclass: loads cloud.yml or pyproject.toml [tool.reflex-cloud]
                      # RegionOption / VmType Literals live here — keep in sync with backend
  utils/
    hosting.py        # ~2.2k lines — HTTP client, auth, project/app/deployment helpers
    console.py        # rich-based console (NOT the one from reflex main)
    dependency.py     # requirements.txt / url helpers
    exceptions.py     # ReflexHostingCliError hierarchy
    __init__.py       # exports `disabled_v1_hosting`
  v2/
    cli.py            # programmatic login/logout/deploy used by reflex/reflex.py
    deployments.py    # `hosting_cli` click group (entry point); check_version()
    apps.py / project.py / secrets.py / vmtypes_regions.py   # click subgroups
    utils.py          # COMPAT SHIM ONLY (reflex 0.6.5→0.6.6) — do not extend
```

## v1 vs v2

- v1 (`reflex_cli/cli.py`, `reflex_cli/deployments.py`) is the legacy alpha hosting service, **decommissioned 2024-12-05**. Every entry point routes through `disabled_v1_hosting()` and exits 1. Do not revive these — add new commands under `v2/`.
- v2 is the current Reflex Cloud CLI. The aggregate click group is `reflex_cli.v2.deployments.hosting_cli`; `apps`, `project`, `secrets`, plus all `vmtypes_regions` commands are attached there.
- If `typer` is importable, `hosting_cli` is rebound to a `typer.Typer` via `_patch_typer` so it composes with the main `reflex` Typer app. Don't assume `hosting_cli` is always a `click.Group`.

## Consumers

- `reflex/reflex.py` imports `hosting_cli`, `cli as hosting_cli` (programmatic), and `check_version` from this package. Any signature change to `v2.cli.login/logout/deploy` is a breaking change for the framework — bump the constants and provide a fallback.
- `deploy()` accepts an `export_fn` whose arity differs between reflex `<=0.7.6` and newer (the include_db arg). The version branch in `v2/cli.py` must keep handling both — don't drop the old path until `MINIMUM_REFLEX_VERSION` is raised past 0.7.6.

## Version pins (`constants/hosting.py`)

- `ReflexHostingCli.MINIMUM_REFLEX_VERSION` — hard fail in `hosting_cli` callback if reflex is older.
- `ReflexHostingCli.RECOMMENDED_REFLEX_VERSION` — soft deprecation warning.

When raising either, also remove the now-dead compat branches (the `<= 0.7.6` `export_fn` calls, the `v2/utils.py` shim once minimum is past 0.6.6).

## Backend URL

`Hosting.HOSTING_SERVICE` / `HOSTING_SERVICE_UI` resolve in this order:
1. `REFLEX_CLOUD_BACKEND_URL` / `REFLEX_CLOUD_URL`
2. `CP_BACKEND_URL` / `CP_WEB_URL` (legacy aliases — keep them)
3. `https://build.reflex.dev`

Tests and tools must respect the env vars; never hardcode `build.reflex.dev`.

## Config (`core/config.py`)

- Loaded from `./cloud.yml` first, then `[tool.reflex-cloud]` in `./pyproject.toml`. `from_yaml_or_toml_or_none(env=...)` is the canonical entry; `env=` selects a sub-key under `env.<name>`.
- `RegionOption` and `VmType` are `Literal[...]` — when adding regions/VM sizes, update both these literals and any backend-side reference. Validation happens via `_validate_dispatch` at `__post_init__`.
- `_cloud_config_path` is a private dataclass field (leading underscore) and is intentionally skipped by validation — keep that pattern for any future internal fields.

## Auth & token storage

- Tokens persist at `Reflex.DIR/hosting_v1.json` (platformdirs-resolved). `hosting_v0.json` is the v1 location, kept only for cleanup migrations.
- All authenticated calls go through `hosting.get_authenticated_client(token=..., interactive=...)`. Do not roll a new auth path — extend that helper.

## Dependencies

Runtime deps are deliberately minimal: `click >=8.2`, `httpx`, `packaging`, `platformdirs`, `rich`. Optional imports (lazy-loaded inside functions): `yaml`, `tomllib` (stdlib 3.11+), `python-dotenv`, `typer`. Keep new imports lazy if they are only needed for one command path — startup time matters for the CLI.

## Tests

There are no tests inside this package — coverage lives at the repo root under `tests/units/` (and integration tests exercise the main `reflex` CLI). When changing behavior here, add unit tests at `tests/units/reflex_cli/...` mirroring the source path (per the root `CLAUDE.md` convention for sub-packages).

## Style notes specific to this package

- The codebase uses Google-style docstrings with explicit `Args/Returns/Raises`. Several `__post_init__` methods carry `# noqa: DAR401` to silence darglint about indirectly-raised errors — preserve those.
- `console.error(...)` followed by `raise click.exceptions.Exit(1)` (or `SystemExit(1)`) is the standard error pattern. Don't `sys.exit()` directly; don't print bare `Exception` messages — funnel through `console`.
- Avoid adding to `v2/utils.py` (compat shim). New shared helpers go in `reflex_cli/utils/`.
