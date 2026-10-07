# Cluster `upgrade_sweep`: 0.9.12 -> 0.10.0a2 in-place upgrade sweep + stock-install smoke (2026-10-07)

INTERIM VERSION - being filled in incrementally; the final sections are appended at the end of the run.

Host: 4-CPU Linux container shared with 3 other agents; Python 3.12.3, Node 22, bun 1.4.2, uv 0.11.32, Playwright 1.63 / Chromium.
Everything installed from PyPI into isolated venvs under `$SB/envs/upgrade_sweep-*` (never from a checkout). Servers were run one at
a time on reserved ports 3140-3159 / 8140-8159 (redis on 8159, GitHub stub on 8158).
`SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad`, `W=$SB/apps/upgrade_sweep`.

## Headline results so far

* No upgrade regression found for form-designer, github-stats, clock or twitter (0.9.12 -> 0.10.0a2 in place, then cold `rm -rf .web`):
  every flow that passes on 0.9.12 passes on a2, identical console-error signatures, no page errors / failed requests; a2 results are
  identical to the saved 0.10.0a1 results of 10-06 (see `logs/compare_a1_a2.txt`).
* NEW, unrelated to the reflex code but release-relevant: a fresh `reflex[db]` install (both 0.9.12 and 0.10.0a2) now resolves
  SQLAlchemy 2.1.3 (sqlmodel 0.0.48, uploaded 2026-10-06T21:44Z, raised its cap to `SQLAlchemy<2.2`), which no longer pulls `greenlet`;
  `import reflex.model` (and so `reflex run`/`reflex db *` of every db app) dies with
  `ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed`.
* F-002 (client-storage defaults written on first load) FIXED (positive control + real apps), F-005 (sqlmodel cap) FIXED,
  F-006 (component floors) FIXED, F-014 unchanged.
