ITEM: dataeditor
KIND: new
REF: -
TITLE: DataEditor on_delete binding dispatches selection then errors before clearing the cell
SEVERITY: medium
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: /de, select Name row 6, press Delete. Selection reaches Python but no edit arrives, Zeta remains, and browser throws TypeError undefined.length. Run focused_driver.py --groups de_edit. Independent bound/unbound Delete and Backspace controls reproduce only with on_delete bound on stable and alpha2; see verification/.
EVIDENCE: prerelease_testing/2026-10-07/dataeditor/de/runs/alpha2-dev/results.json, groups.de_edit; de/runs/alpha2-dev/shots/alpha2-dev-edit-delete.png; all baseline/production equivalents; de/logs/generated-snippets.txt.
ROOT_CAUSE_GUESS: published dataeditor.py:365 exposes ordinary EventHandler; generated onDelete callback returns addEvents, whose queueEvents is async. Glide calls shiftSelection on a non-boolean return and accesses columns.length. No synchronous boolean/GridSelection adapter is generated.

## Exact replay

Set ROOT to the checkout containing these artifacts; use a new scratch directory.

```sh
ROOT=/path/to/reflex
export REFLEX_TEST_SB=/tmp/reflex-dataeditor-repro-3
ART="$ROOT/prerelease_testing/2026-10-07/dataeditor/de"
bash "$ART/scripts/bootstrap_from_freezes.sh"
cd "$REFLEX_TEST_SB/apps/dataeditor"
./scripts/start_server.sh alpha2 dev 3420 8420
```

In another terminal, use the same REFLEX_TEST_SB, then:

```sh
cd "$REFLEX_TEST_SB/apps/dataeditor"
uv --no-config run --no-project --python "$REFLEX_TEST_SB/envs/driver/bin/python" python scripts/focused_driver.py http://localhost:3420 runs/repro --label repro --groups de_edit
```

The intended reproduction returns exit1 for the failing assertion and saves results/screenshots. Stop the server before changing versions. Full baseline/mode and typing-delay commands are in `prerelease_testing/2026-10-07/dataeditor/NOTES-de.md`.
