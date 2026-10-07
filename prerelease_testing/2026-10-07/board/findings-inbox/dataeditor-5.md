ITEM: dataeditor
KIND: new
REF: -
TITLE: Radix form synthetic clicks trigger uncaught errors when a DataEditor is present
SEVERITY: low
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: Run the independent delete_app fixture and drive_form_grid.py as shown below. Checkbox/switch/radio changes produce three undefined[0] errors with a grid, zero without it. All three controls still update. Full composed forms reproduce in alpha1/alpha2/stable; independent minimal controls reproduce in alpha2/stable.
EVIDENCE: prerelease_testing/2026-10-07/dataeditor/verification/results/form-grid/{alpha2,stable}/results.json and screenshots; adjacent glide-click-excerpt.txt and radix-click-excerpt.txt; NOTES-verification.md; forms/runs/*/*/results.json.
ROOT_CAUSE_GUESS: Published Glide data-grid global click handler treats non-MouseEvent as TouchEvent and reads ev.changedTouches[0]; Radix hidden inputs dispatch plain Event('click'), which lacks changedTouches. This source-level explanation matches independently captured event constructors; no framework fix was attempted.

## Exact replay

```sh
ROOT=/path/to/reflex
export REFLEX_TEST_SB=/tmp/reflex-form-grid-repro
ART="$ROOT/prerelease_testing/2026-10-07/dataeditor"
bash "$ART/de/scripts/bootstrap_from_freezes.sh"
export SB="$REFLEX_TEST_SB"
export QA_ENV=alpha2
mkdir -p "$SB/apps/form-grid"
cp -R "$ART/verification/delete_app/." "$SB/apps/form-grid/"
cd "$SB/apps/form-grid"
REFLEX_TELEMETRY_ENABLED=false uv --no-config run --no-project --python "$SB/envs/$QA_ENV/bin/python" reflex run --frontend-port 3435 --backend-port 8435
```

From a second neutral-directory terminal with the same SB and ART:

```sh
cd "$SB"
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/verification/scripts/drive_form_grid.py" http://localhost:3435 "$SB/form-grid-results"
```

Stop the server, use QA_ENV=stable and a separate copy of the same app to reproduce the baseline. The driver intentionally fails for the grid case while the no-grid control remains clean.
