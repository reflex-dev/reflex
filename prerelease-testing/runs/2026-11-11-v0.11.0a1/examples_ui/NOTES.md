# examples_ui — non-DB reflex-examples, in-place upgrade 0.10.1 -> 0.11.0a1

## Status / resume here
- [x] staged: `$SB/apps/examples_ui` (= `$W`) = copy of `prerelease-testing/fixtures/upgrade` (`bin/stage.sh --no-fetch`)
  + apps copied from `$SB/downloads/reflex-examples` @ ebe19ff into `$W/up/apps/<app>` (github-stats + upload QA patches
  applied, rxconfig venv guard `QA_EXPECT_VENV`). Env: `. $SB/apps/examples_ui/env_eu.sh`.
  NOTE: a first staging attempt with a broken `$W` created `/apps/examples_ui` at the filesystem root (fixture copy only,
  no servers); the sandbox refused my `rm -rf` of it — leave it for a human to delete.
- [x] base venvs `$SB/envs/examples_ui-<app>` = `reflex==0.10.1` + requirements.txt, `-c $W/prev_constraints.txt`
  (freeze of `$SB/envs/prev`), no --prerelease, `--only-binary :all:`. Freezes in `$W/up/freeze/<app>-base.txt`.
- [x] counter, github-stats, overkey (stacked fail + minimal fix) — done
- [ ] reflexle, upload, clock, quiz — running (`$W/logs/seq-<app>.txt`)
- [x] fresh-install matrix n001 (uv/pip x 3.11/3.14/3.15 + plain pip 3.12) + dbcli; pip/uv in-place paths
- [ ] fresh `reflex init --template blank` + run per python; overkey fully-migrated API check; copy artifacts

## How to rerun
```bash
. $SB/apps/examples_ui/env_eu.sh            # SB, W, DEST, venv prefix examples_ui
cd $SB && bash <repo>/prerelease-testing/fixtures/upgrade/bin/stage.sh --no-fetch   # with W set as above
# copy apps: for a in github-stats overkey reflexle upload counter clock quiz; do cp -r $SB/downloads/reflex-examples/$a $W/up/apps/; done
# patch: (cd $W/up/apps && patch -p1 < $W/examples/patches/github-stats_fetchers.diff && patch -p1 < $W/examples/patches/upload-qa-extras.diff)
# harness fix: cp $W/up/scripts/harness_b.py $W/up/scripts/harness.py   (drive_upload.py needs Run.expected_bad; fixture drift)
# base venv per app:
uv --no-config venv --python 3.12 $SB/envs/examples_ui-<app>
uv --no-config pip install --python $SB/envs/examples_ui-<app>/bin/python --only-binary :all: -c $W/prev_constraints.txt -r $W/up/apps/<app>/requirements.txt 'reflex==0.10.1'
cd $W && bash eu/seq_eu.sh <app> base baseprod upgrade up prod cold      # this cluster's driver: eu/seq_eu.sh
```
`eu/seq_eu.sh` phases: base (0.10.1 dev, fresh .web/reflex.lock/profile) -> baseprod (0.10.1 `--env prod`, single port)
-> upgrade (`uv pip install --prerelease=allow 'reflex==0.11.0a1'`, **no -U**, same venv) -> up (dev, same dir/.web/
reflex.lock/browser profile) -> prod (single port 3420 + `REFLEX_API_URL=http://localhost:3420`) -> cold (`rm -rf .web`).
Ports: dev 3420/8420, prod 3420 (same origin so LocalStorage/cookies carry over), GraphQL stub 8438.
Drivers: fixture `up/scripts/drive_*.py` + new `eu/drive_overkey.py`. `eu/logdiff.sh a.log b.log` lists normalized
server-log lines new in b. `eu/pkgjson_cmp.py` = semantic package.json diff.
