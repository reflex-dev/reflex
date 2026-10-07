# Findings — re-verification on reflex 0.10.0a2 train (r/pre-2026.10.06-37579583012), 2026-10-07

**Status: in progress (interim; updated as clusters report).** Scope: re-run every failing repro from the
[2026-10-06 findings](../2026-10-06/FINDINGS.md) against the newly published train, finish the clusters the
spend limit interrupted, and sweep for regressions the fixes may have introduced. Enterprise is tested with
the user-supplied offline `reflex-enterprise 0.9.7a4` wheel.

## Versions under test
reflex / reflex-base 0.10.0a2; components code/core/gridjs/markdown/moment/plotly/radix/recharts 0.10.0a2;
dataeditor 0.10.0a1; react-player 0.10.0a1; sonner 0.10.0a1; lucide 1.1.0a1; docgen 0.10.0a2; hosting-cli
0.2.0a1 (0.1.73a1 excluded by reflex's metadata); build-sdk 0.1.0a1; release 0.2.0a1; otel 0.2.0a1;
hatch-reflex-pyi 0.10.0a1. All 20 published with wheel+sdist; `.pyi` audit PASS
([packaging/audit.log](./packaging/audit.log)). Python >= 3.11 (3.10 dropped). Baselines: 0.10.0a1 (previous
train) and 0.9.12.

## Pre-flight facts (orchestrator, verified from metadata and the published packages)
- `reflex[db]==0.10.0a2` resolves `sqlmodel 0.0.48`: the `<0.0.45` cap is gone (#7462). No changelog
  fragment mentions #7462 ("Support SQLModel UTC datetime migrations without downgrades") — documentation gap
  to confirm (FINDING-005 follow-up).
- reflex 0.10.0a2 now floors every component package at its new-train alpha (`reflex-components-core >=
  0.10.0a2`, `-dataeditor >= 0.10.0a1`, `-lucide >= 1.1.0a1`, `-sonner >= 0.10.0a1`, ...) and excludes
  `reflex-hosting-cli 0.1.73a1` (#7464) — addresses FINDING-006; behavioral check pending.
- The 0.10.0a2 changelog documents the class-level backend-var read returning `Field` as a (misc) breaking
  change with the `default_value()` guidance, and #7456 turns a formatted backend var into
  `BackendVarFormatError` — FINDING-001's core half is now intentional-and-documented; the enterprise half
  (`__data_source_params_class__`) should be covered by #7465 (dunder names are plain attributes). Pending.
- Smoke: blank app on 0.10.0a2 in dev, driven in Chromium: clean ([smoke/](./smoke/)).

## Re-verification table (filled in as clusters report)

| finding (10-06) | a1 status | a2 result | cluster |
|---|---|---|---|
| F-001 class-level backend var → Field; enterprise AG Grid model wrapper 500 | HIGH regression | pending | reverify_core |
| F-002 first-load client-storage default write-back | HIGH regression | pending | reverify_hydration |
| F-003 computed-var client-storage rewrite dropped at hydration | MED partial regression | pending | reverify_hydration |
| F-004 class-level assignment replaces descriptor | MED regression | pending | reverify_core |
| F-005 sqlmodel<0.0.45 cap | MED regression | cap lifted (metadata); behaviour pending | reverify_db_install |
| F-006 component floors unchanged | MED release-eng | floors raised (metadata); behaviour pending | reverify_db_install |
| F-007 npm SIGTERM hang | MED pre-existing | pending | reverify_db_install |
| F-008 >1 MB storage reconnect storm | MED pre-existing | pending | reverify_hydration |
| F-010 pre-connect nav on_load | LOW pre-existing | pending | reverify_hydration |
| F-011 forward-ref TypeError | LOW regression | pending | reverify_core |
| F-012 PageContext LookupError message | LOW | pending | reverify_core |
| F-013 rx.Model deprecation location | LOW | pending | reverify_core |
| F-014 `reflex component` message | LOW | pending | reverify_core |
| F-015 duplicate npm notice | LOW | pending | reverify_db_install |
| F-016 ty 0-arg / 5-arg | LOW | pending | reverify_core |
| F-017 redis restart token loss | LOW unknown | pending | reverify_hydration |
| F-018 React 19.3 console error | LOW | pending | reverify_core |

## New findings on 0.10.0a2
(none yet)

## Cluster summaries
(pending)
