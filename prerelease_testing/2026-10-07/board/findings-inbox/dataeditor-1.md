ITEM: dataeditor
KIND: new
REF: -
TITLE: DataEditor get-cell callback escapes foreach variable scope
SEVERITY: medium
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: Start the source app as alpha2-dev on 3420/8420 via NOTES-de.md. Visit /de-foreach, or run focused_driver.py --groups de_foreach. Equivalent stable 3421, alpha 3422, alpha2-prod 8423, stable-prod 8424 also fail.
EVIDENCE: prerelease_testing/2026-10-07/dataeditor/de/runs/alpha2-dev/results.json; de/runs/alpha2-dev/shots/alpha2-dev-de-foreach.png; corresponding baseline and production results; de/logs/generated-snippets.txt. Zero editors render and page becomes the Reflex error boundary.
ROOT_CAUSE_GUESS: published reflex_components_dataeditor/dataeditor.py:472-499 add_hooks emits getData callback containing g_rx_state_ outside the map lambda. Independent memo-wrapped foreach control renders successfully; see verification/.

## Exact replay

Set ROOT to the checkout containing these artifacts; use a new scratch directory.

```sh
ROOT=/path/to/reflex
export REFLEX_TEST_SB=/tmp/reflex-dataeditor-repro-1
ART="$ROOT/prerelease_testing/2026-10-07/dataeditor/de"
bash "$ART/scripts/bootstrap_from_freezes.sh"
cd "$REFLEX_TEST_SB/apps/dataeditor"
./scripts/start_server.sh alpha2 dev 3420 8420
```

In another terminal, use the same REFLEX_TEST_SB, then:

```sh
cd "$REFLEX_TEST_SB/apps/dataeditor"
uv --no-config run --no-project --python "$REFLEX_TEST_SB/envs/driver/bin/python" python scripts/focused_driver.py http://localhost:3420 runs/repro --label repro --groups de_foreach
```

The intended reproduction returns exit1 for the failing assertion and saves results/screenshots. Stop the server before changing versions. Full baseline/mode and typing-delay commands are in `prerelease_testing/2026-10-07/dataeditor/NOTES-de.md`.
