ITEM: dataeditor
KIND: new
REF: -
TITLE: Beginning a data editor edit by typing loses initial characters
SEVERITY: medium
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: Fresh /de page, click row 2 Name cell, type Zed without first pressing Enter, then press Enter: the captured edit and grid contain d. Run focused_driver.py --groups de_edit. For human-speed proof run typing_driver.py: type Slow at 120ms per character, observe low; separately press S, wait 800ms, type low, observe Slow.
EVIDENCE: prerelease_testing/2026-10-07/dataeditor/de/runs/{alpha2-dev,alpha-dev,stable-dev,alpha2-prod,stable-prod}/results.json; de/runs/{stable-typing,alpha2-prod-typing}/results.json. Explicit Enter-opened text/int/float editing controls all pass.
ROOT_CAUSE_GUESS: unknown; the first overlay is lazily imported in the published Glide bundle and waiting for it avoids loss, but exact timing/focus cause is unproven.

## Exact replay

Set ROOT to the checkout containing these artifacts; use a new scratch directory.

```sh
ROOT=/path/to/reflex
export REFLEX_TEST_SB=/tmp/reflex-dataeditor-repro-2
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
