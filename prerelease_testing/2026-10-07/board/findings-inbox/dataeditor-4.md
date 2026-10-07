ITEM: dataeditor
KIND: new
REF: -
TITLE: Escape immediately after single-image preview activation leaves preview open
SEVERITY: low
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: /de, double-click first-row Image cell; press Escape. The .carousel preview remains. Run focused_driver.py --groups de_overlay: single-image Escape fails without any outside-click fallback; Escape after clicking next arrow in multi-image preview and text-editor Escape pass.
EVIDENCE: prerelease_testing/2026-10-07/dataeditor/de/runs/alpha2-prod/shots/alpha2-prod-single-overlay-after-escape.png; all five focused results groups.de_overlay. Stable and alpha dev reproduce as well.
ROOT_CAUSE_GUESS: unknown; focus routing is a candidate because clicking a carousel control changes Escape behavior.

## Exact replay

Set ROOT to the checkout containing these artifacts; use a new scratch directory.

```sh
ROOT=/path/to/reflex
export REFLEX_TEST_SB=/tmp/reflex-dataeditor-repro-4
ART="$ROOT/prerelease_testing/2026-10-07/dataeditor/de"
bash "$ART/scripts/bootstrap_from_freezes.sh"
cd "$REFLEX_TEST_SB/apps/dataeditor"
./scripts/start_server.sh alpha2 dev 3420 8420
```

In another terminal, use the same REFLEX_TEST_SB, then:

```sh
cd "$REFLEX_TEST_SB/apps/dataeditor"
uv --no-config run --no-project --python "$REFLEX_TEST_SB/envs/driver/bin/python" python scripts/focused_driver.py http://localhost:3420 runs/repro --label repro --groups de_overlay
```

The intended reproduction returns exit1 for the failing assertion and saves results/screenshots. Stop the server before changing versions. Full baseline/mode and typing-delay commands are in `prerelease_testing/2026-10-07/dataeditor/NOTES-de.md`.
