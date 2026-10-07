# Forms and component browser checks, macOS second pass

Status: in progress. These are observations, not a release verdict. Framework source is unchanged.

Host: macOS 26.6.2 (25G83), arm64, Python 3.12.14. Published-package environments and full freezes are in `forms/environment/`. Chromium 153 and Playwright WebKit are driven by Playwright 1.63.0. All app imports assert the selected isolated environment path.

The copied 10-06 fixture is under `forms/app/`; the old driver is retained as `forms/scripts/original_driver.py`. `drive_forms.py` adds an isolated select matrix, exact nested-dialog key checks, and corrected Recharts tick selection. Live DOM inspection showed `<text orientation="bottom">` inside `recharts-cartesian-axis-tick-label`, so the older `.recharts-xAxis` and guessed `.recharts-cartesian-axis-tick` selectors are invalid for this installed version. Memo charts may omit the first tick, so assertions validate every rendered value rather than require a zero tick.

## Reproduction

Use any scratch directory outside a checkout. The commands below reproduce this run's environment (replace ROOT with your checkout path):

```sh
ROOT=/Users/masen/.codex/worktrees/3564/reflex
SB=/private/tmp/reflex-prerelease-macos-pass2
DEST="$ROOT/prerelease_testing/2026-10-07/dataeditor/forms"
mkdir -p "$SB"
cd "$SB"
for E in forms-alpha2 forms-alpha forms-stable driver; do
  uv --no-config venv --python 3.12 "$SB/envs/$E"
  uv --no-config pip install --python "$SB/envs/$E/bin/python" --prerelease=allow -r "$DEST/environment/$E.txt"
done
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python -m playwright install chromium webkit
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$DEST/scripts/run_matrix.py" "$SB" --version alpha2 --mode dev --groups select_matrix,forms,recharts,plotly,radix,code,download,match,memo_names
```

The runner copies source into scratch, starts one app on 3430/8430 (dev) or 3431 (prod), writes server/driver logs and JSON/screenshots under `forms/runs/<version>-<mode>/`, then terminates its process group. It never imports framework code from the checkout. Use `--version stable` or `--version alpha` for the baselines; `--mode prod` for the production build. `--browsers chromium` restricts to one engine. Fresh browser contexts isolate each group.

## Initial observations

- The separate select matrix demonstrates that named selects submit values on alpha2; id-only select is absent. The earlier finding inaccurately described the saved id-only fixture as named. Baseline classification is pending.
- Dialog submission reaches both the dialog handler and the outer form handler; closed dialog keys occur in outer payloads. Baseline classification is pending.
- Form page emits `undefined (reading '0')` page errors with full stacks preserved. The fixture embeds a data editor; this needs isolation before attribution.
- Initial chart assertions used the wrong selector. A source edit during that initial run also interrupted its background counter via HMR; discard that preliminary chart result and use the subsequent unmodified-source run.
- Initial smoke fixture lacked the documented app package `__init__.py`, producing a state namespace mismatch. The normal package fixture passed; this was setup error, not a release finding.
