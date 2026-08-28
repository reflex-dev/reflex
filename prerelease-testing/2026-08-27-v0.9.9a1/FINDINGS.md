# Findings ledger — reflex 0.9.9a1 pre-release testing (2026-08-28)

Orchestrator-maintained running list. Final report assembled from this + workflow agent outputs.

## Versions under test (all published on PyPI ✓, verified via /pypi/<pkg>/<ver>/json)

reflex 0.9.9a1, reflex-base 0.9.9a1, reflex-components-core 0.9.9a1,
reflex-components-radix 0.9.8a1, reflex-components-code 0.9.4a1,
reflex-components-plotly 0.9.5a1, reflex-components-sonner 0.9.2a1,
reflex-components-dataeditor 0.9.2a1, reflex-components-lucide 1.0.4a1,
reflex-components-react-player 0.9.2a1, reflex-docgen 0.9.5a1, reflex-hosting-cli 0.1.71a2.
(markdown 0.9.3 / moment 0.9.3 / recharts 0.9.2 / reflex-release 0.1.0 unchanged, not alpha.)

Environment: Linux container, 4 CPU / 15GB, Node v22.22.2 (floor is 22.22.0), bun 1.3.11,
Python 3.11.15 primary (3.12/3.13/3.14 via uv), Chromium via Playwright, outbound via agent proxy.

## FINDING-001: reflex-enterprise 0.9.4 incompatible with 0.9.9a1 — `dynamic.bundled_libraries` removed (HIGH)

- Breaking change #6382 moved the module-level `bundled_libraries` list from
  `reflex_base.components.dynamic` onto the active `RegistrationContext`. No shim:
  `reflex.components.dynamic.bundled_libraries` now raises `AttributeError` (verified in
  isolated venv with published packages, see repro below).
- Latest published reflex-enterprise (0.9.4) wheel reads it at `reflex_enterprise/vars.py:143`
  (`bundled_libraries = set(dynamic.bundled_libraries)`) inside
  `LiteralLambdaVar._validate_and_extend_return_expr`, used by the LambdaVar machinery that
  dnd, map, and ag_grid components rely on for lambda props whose compiled JS carries imports.
- Expected user impact: `AttributeError: module 'reflex.components.dynamic' has no attribute
  'bundled_libraries'` at compile time for affected enterprise apps on 0.9.9a1.
- Repro (no app needed):
  ```
  uv venv /tmp/v && uv pip install --python /tmp/v/bin/python --prerelease=allow 'reflex==0.9.9a1'
  /tmp/v/bin/python -c "from reflex.components import dynamic; dynamic.bundled_libraries"
  # AttributeError
  ```
  End-to-end demo repro: see enterprise workflow agent results.
- Note: changelog for reflex-base 0.9.9a1 documents the move ("use bundle_library() /
  reset_bundled_libraries() as before") but downstream reflex-enterprise has not been updated;
  either a compat shim (module `__getattr__` reading the active RegistrationContext) or a
  coordinated reflex-enterprise release is needed before 0.9.9 final.

## Environment quirks (benign here, noted for context)

- `reflex init` probes https://registry.npmmirror.com and logs 3x "Failed to connect" before
  falling back (proxy blocks that host). Cosmetic in this environment.
- Vite warns: `configLoader: 'native'` unsupported feature — `import "./vite-plugin-safari-cachebust"
  without a file extension (vite.config.js:4:35)`; suggests adding extension. Framework-owned
  file; will become a hard incompatibility in a future Vite major per warning text. Present in
  dev runs on 0.9.9a1 (vite 8.2.0).
