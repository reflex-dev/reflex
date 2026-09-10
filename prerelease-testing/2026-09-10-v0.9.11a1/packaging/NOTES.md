# packaging — Phase 5 audit of the 2026-09-10 train (orchestrator)

## Discovery + presence on PyPI

```
uv run --script .claude/skills/prerelease-test/scripts/check_release_versions.py --ref origin/r/pre-2026.09.10-34457666442
```

17 packages in the train (logs/specs.txt). First run at 09:01 UTC: **`reflex-otel==0.1.0a1` NOT ON
PYPI** — the "Release from changelog" run 34457698833 for this branch had its
`publish (reflex-otel, 0.1.0a1)` job fail at `uv publish` with
`400 Non-user identities cannot create new projects. This was probably caused by successfully
using a pending publisher but specifying the project name incorrectly` (job 102808226580); the
`report` job then failed with "release leg 'publish' ended 'failure'". The package appeared on
PyPI at 09:10 UTC (a manual/re-run publish); rerunning the discovery script afterwards reports
"All packages are published and installable." Recorded as a finding about the release process
(new package's trusted publisher not pre-configured), resolved for this train.

## .pyi stubs in wheel vs sdist

```
uv run --script .claude/skills/prerelease-test/scripts/check_release_versions.py --ref <ref> --specs > specs.txt \
  && xargs uv run --script .claude/skills/prerelease-test/scripts/audit_pyi.py --manifest-ref <ref> < specs.txt
```

PASS for all 17 packages: 121 stubs ship in both wheel and sdist, byte-identical, no foreign
stubs, counts match `pyi_hashes.json` (logs/audit_pyi.log). reflex-otel ships none (manifest: 0).

## Dependency pins vs changelog claims (PyPI metadata + installed sources)

- reflex 0.9.11a1: `reflex-base==0.9.11a1` (lockstep), `wrapt<2.4,>=1.17.0` (changelog: allow
  2.2/2.3 — resolves 2.3.0), `reflex-hosting-cli>=0.1.71`, new extra `testing` = psutil,
  selenium, uvicorn (#6974/#7008); `db` = alembic/pydantic/sqlmodel; `pydantic` =
  `reflex-base[pydantic]`. No opentelemetry dependency anywhere in reflex/reflex-base (as the
  reflex-base changelog states); reflex-otel requires `reflex-base>=0.9.11a1`,
  `opentelemetry-api>=1.30,<2`, `-instrumentation(-asgi)>=0.49b0,<1` — the dev pin was lifted.
- Component pins in the installed alphas match the changelogs: react-moment@2.0.2 + moment@2.30.1
  + moment-timezone@0.6.3 + moment-duration-format@2.2.2 (moment 0.9.4a1); shiki /
  @shikijs/transformers 4.4.3 (code 0.9.5a1); react-plotly.js@4.1.0 + plotly.js@3.7.0 (plotly
  0.9.6a1); recharts@3.10.1; sonner@2.0.8; @radix-ui/react-form@0.1.16, react-dialog@1.1.23,
  react-accordion@1.2.20 (radix 0.9.9a1). reflex-base installer constants: Bun VERSION =
  MIN_VERSION = 1.4.0, Node MIN 22.22.0, isbot 5.2.2, postcss 8.5.26, postcss-import 17.0.0,
  vite 8.2.2.

## Installing from sdist

- `uv pip install --no-binary reflex --no-binary reflex-base 'reflex==0.9.11a1'` **fails** before
  building: "`reflex-base` references a workspace in `tool.uv.sources` (e.g.
  `reflex-base = { workspace = true }`), but is not a workspace member" (logs/sdist_install.log).
  The `reflex` sdist ships the monorepo root `pyproject.toml` verbatim, including
  `[tool.uv.sources]` (every workspace package `.workspace = true`) and `[tool.uv.workspace]`
  (logs/reflex-0.9.11a1-sdist-tool.uv.sources.txt), which uv rejects when the sdist is built
  outside the workspace. **Pre-existing**: identical failure with `reflex==0.9.10.post2`
  (logs/sdist_install_0910.log). `reflex-base`'s own sdist builds fine under uv.
- `pip install --no-binary reflex,reflex-base,reflex-otel --pre reflex==0.9.11a1 reflex-otel==0.1.0a1`
  succeeds (33 s, logs/sdist_install_pip.log); the built reflex carries its 3 `.pyi` stubs and
  radix its 65; `reflex_base.otel.enabled` is False; imports work.
