# 0.10.1a2 validation (2026-10-26) — sibling floors

a2 = a1 + #7662 (raise the reflex wheel's sibling floors) + docs-site-only PRs (#7657, #7658, #7660). Only reflex and
reflex-base were re-released (CHANGELOG: "No significant changes"). Scratch: `$SB/a2/`.

| check | result |
|---|---|
| publish (`check_release_versions.py --ref v0.10.1a2`) | 20/20 OK |
| `.pyi` audit reflex / reflex-base a2 | PASS (3 / 0 stubs) |
| a1 vs a2 wheels (reflex, reflex_base) | byte-identical outside `dist-info` → every a1 functional result carries over |
| reflex METADATA | `reflex-components-code>=0.10.1a1`, `-dataeditor>=0.10.1a1`, `lucide>=1.1.1a1`, `reflex-hosting-cli>=0.2.1a1` (was >=0.10.0 / 1.1.0 / 0.2.0); `-core>=0.10.0` unchanged but radix 0.10.1a1 requires core 0.10.1a1 |
| resolution: pip (no `--pre`) fresh on 3.11 / 3.12 / 3.14; pip `-U` and plain re-install over 0.10.0; uv `--prerelease=allow` fresh and `-U` over 0.10.0 | all 7 resolve the whole train: base/reflex a2, code/core/dataeditor/moment/radix 0.10.1a1, lucide 1.1.1a1, hosting-cli 0.2.1a1, build-sdk 0.1.1a1; `pip check` clean. uv without `--prerelease=allow` refuses (as on every alpha, F-006) |
| mixed app (`upgrade_packaging/mixed`), stock pip a2, dev | 23/23 (a1 stock pip: 22/23, data_editor crash #7596 + shiki transformer missing) |
| same, venv upgraded in place from 0.10.0 with `pip install -U`, prod | 23/23 |
| reflex-enterprise 0.9.9 (PyPI) and 0.9.10a1 (offline) with a2 | install + import clean (`-W error::DeprecationWarning`) |
| R101-01 grid repro (`verify_ent910/gridfix`) on a2 | rxe 0.9.9: still broken (memo / other grids stale); rxe 0.9.10a1: fixed |

R101-04: **fixed**. Known pre-existing: 4 glide-data-grid `reading '0'` page errors in the mixed app (both versions).
