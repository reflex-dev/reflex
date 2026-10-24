# verify_cc — independent verification of CC-1 and CC-2 (cloud_cli explorer findings), 2026-10-24

Verifier reproduction from the explorer's written repro only, against PUBLISHED packages in the explorer's read-only venvs
`$SB/envs/cloud_cli-new` (reflex 0.10.1a1 + reflex-hosting-cli 0.2.1a1 + reflex-build-sdk 0.1.1a1) and
`$SB/envs/cloud_cli-prev` (reflex 0.10.0 + reflex-hosting-cli 0.2.0 + reflex-build-sdk 0.1.0). No Reflex Cloud
contact: the CLI is pointed at the explorer's stdlib stub `fake_cp.py` (copied unchanged to `scripts/`) through
`REFLEX_CLOUD_BACKEND_URL=http://127.0.0.1:<port>`; isolated `XDG_DATA_HOME`; `REFLEX_TELEMETRY_ENABLED=false`.
Everything ran from `$SB/apps/verify_cc/` (neutral cwd); every CLI run and probe first asserts the venv it imports from.
Ports: stubs on 8740 (new) and 8741 (prev); nothing else bound.

Source was read from the tag (`git -C /home/user/wt-testing show v0.10.1a1:<path>`; also v0.10.0, v0.9.13, v0.9.0,
v0.8.0) and from the installed `reflex_cli` / `reflex_build_sdk` packages in the venvs.

## Setup / rerun

```bash
SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa; R=$SB/apps/verify_cc
mkdir -p $R/logs $R/scripts; cp <DEST>/scripts/* $R/scripts/; cp -r <DEST>/app $R/app-src     # app = explorer's cliapp (rxconfig.py + cliapp/cliapp.py)
for v in new prev; do mkdir -p $R/app-$v; (cd $R/app-$v && REFLEX_TELEMETRY_ENABLED=false $SB/envs/cloud_cli-$v/bin/reflex init --template blank --name cliapp); cp $R/app-src/rxconfig.py $R/app-$v/; cp $R/app-src/cliapp/cliapp.py $R/app-$v/cliapp/; done
cd $R; $SB/envs/driver/bin/python -I scripts/fake_cp.py --port 8740 --state-dir state-8740 &   # new
       $SB/envs/driver/bin/python -I scripts/fake_cp.py --port 8741 --state-dir state-8741 &   # prev
mkdir -p $R/sym/outside_target/nested; echo x > $R/sym/outside_target/file.txt; echo y > $R/sym/outside_target/nested/deep.txt
(cd $SB && uv --no-config venv --python 3.12 -q $R/sym/outside_venv)
mkdir -p $R/probe/cliapp; cp $R/app-src/rxconfig.py $R/probe/; cp $R/app-src/cliapp/cliapp.py $R/probe/cliapp/; touch $R/probe/cliapp/__init__.py
# CC-1
(cd $R/probe && for f in - info debug warning default; do EXPECT_VENV=cloud_cli-new REFLEX_TELEMETRY_ENABLED=false $SB/envs/cloud_cli-new/bin/python -I $R/scripts/loglevel_probe.py $f; done)   # + REFLEX_LOGLEVEL=info ... -
bash scripts/deploy_batch1.sh; bash scripts/deploy_batch2.sh      # real `reflex deploy` matrix (logs/cc1-*.{new,prev}.*, logs/cc2-deploy.*)
# CC-2
bash scripts/sym_matrix.sh new; bash scripts/sym_matrix.sh prev   # `reflex export --backend-only` symlink matrix (logs/sym-*.{new,prev}.*)
```

`scripts/run_cli.sh` is the explorer's runner re-rooted here (stub reset with `SCENARIO`, output in
`logs/<label>.<venv>.{out,err,rc,requests.json}`; `.requests.json` is the stub's request log with timestamps).

## CC-1 — `reflex deploy` hides the #7463 scaling progress lines and its own success line below `--loglevel debug`

### Root cause (pinned from source; identical in v0.10.1a1 and v0.10.0, and already in v0.9.13 / v0.9.0 / v0.8.0)

Call chain of the real `reflex deploy` (reflex `reflex/reflex.py` lazily registers `reflex_cli.v2.deploy:deploy`):

1. `reflex` group callback → `reflex_base.utils.log.enable_managed_logging()` (attaches the console sink at
   `_log_level`, whose module-level initial value is **`LogLevel.INFO`**: `reflex_base/utils/log.py` line 93).
2. The deploy command's eager `--loglevel` option (`reflex_cli/utils/cli_options.py`) →
   `reflex_cli.utils.console.set_log_level(value)` → `reflex_base.utils.log.set_log_level(LogLevel)`, which does
   ```python
   if log_level != _log_level:            # log.py lines 1006-1008
       os.environ["REFLEX_LOGLEVEL"] = log_level.value
   _log_level = log_level
   ```
   so **`--loglevel info` never writes `REFLEX_LOGLEVEL`** (INFO == the initial `_log_level`), whereas `debug`,
   `warning`, `default` do.
3. `reflex_cli.v2.deploy.deploy()` → `reflex.hosting.prepare_deploy()` → `prep.loglevel = get_config().loglevel`.
   `Config.loglevel` defaults to `LogLevel.DEFAULT` (`reflex_base/config.py` line 203) and is only overridden by the
   `REFLEX_LOGLEVEL` env var (lines 377-381) or by `rxconfig.py`. With no flag or with `--loglevel info` it is
   therefore `DEFAULT`.
4. `hosting_cli.deploy(loglevel=prep.loglevel)` → `console.set_log_level(DEFAULT)` (to_logging_level = INFO; still
   fine), then the export step: `reflex.hosting.export_for_deploy()` →
   `export(loglevel=get_config().loglevel.subprocess_level())` (`reflex/hosting.py` line 92) →
   `reflex/utils/export.py` line 50 `console.set_log_level(loglevel)`. `LogLevel.DEFAULT.subprocess_level()` is
   **`WARNING`** (`reflex_base/constants/base.py` line 319), and `export()` applies it to the *current* process (the
   same `reflex` logger the hosting CLI logs through: `reflex_cli` is parented under `reflex` by
   `reflex_base.utils.log.bootstrap`). Nothing restores the level afterwards.
5. Everything the hosting CLI logs after the export below WARNING is dropped: `logger.info("App is being scaled;
   waiting 15 seconds before retrying deployment (scaling retry n/11).")` (`reflex_cli/utils/deploy.py` line 111,
   used for both the submission retry and the `--min/--max-instances` bounds retry), the status narration
   `note()` → `logger.info(message)` in `watch_deployment_status` (`reflex_cli/utils/hosting.py` line 1690) and
   `logger.log(log.SUCCESS, "deployment completed successfully")` / `"build submitted for approval; …"` (lines 1757-1762;
   SUCCESS = 25 < WARNING = 30). `logger.warning` / `logger.error` / `console.print` (level-less) still print.

Why the explorer's driver (`deploy_driver.py`) showed the lines at INFO: it replaces `export_fn`, so step 4 never runs.

`loglevel_probe.py` reproduces steps 1-5 without a build and logs one record per level afterwards
(`logs/loglevel_probe.txt`, both venvs, byte-for-byte the same behavior):

| invocation | `REFLEX_LOGLEVEL` after the flag callback | `get_config().loglevel` → `.subprocess_level()` | level after `export()` | records printed after export |
|---|---|---|---|---|
| (no flag) | unset | DEFAULT → WARNING | WARNING | WARNING, ERROR |
| `--loglevel info` | **unset** (level unchanged, env var not written) | DEFAULT → WARNING | WARNING | WARNING, ERROR |
| `--loglevel default` | `default` | DEFAULT → WARNING | WARNING | WARNING, ERROR |
| `--loglevel warning` | `warning` | WARNING → WARNING | WARNING | WARNING, ERROR |
| `--loglevel debug` | `debug` | DEBUG → DEBUG | DEBUG | DEBUG, INFO, SUCCESS, WARNING, ERROR |
| env `REFLEX_LOGLEVEL=info`, no flag | `info` | INFO → INFO | INFO | INFO, SUCCESS, WARNING, ERROR |

### End-to-end with the real `reflex deploy` (warm `.web`, stub scenario: `POST deployments` → 409
`x-reflex-error-code: app_scaling` twice, then 200; `logs/cc1-*.new.*`)

| run (new, 0.10.1a1 + 0.2.1a1) | rc | "App is being scaled" lines | "deployment completed successfully" | `Info:` lines | stub: `POST deployments` |
|---|---|---|---|---|---|
| `cc1-debug` (`--loglevel debug`) | 0 | 2 | `Info:` + `Success:` | 7 | 3, one request id, at +0 / +15.0 / +30.0 s |
| `cc1-default` | 0 | **0** | **none** | 0 | 3, at +0 / +15.0 / +30.0 s |
| `cc1-info` (`--loglevel info`) | 0 | **0** | **none** | 0 | 3 |
| `cc1-envinfo` (`REFLEX_LOGLEVEL=info`, no flag) | 0 | 2 | `Info:` + `Success:` | 3 | 3 |
| `cc1-json` (`--json`, default level) | 0 | **no record** | **no record** | — | 3 |

`cc1-json.new.out` holds exactly 5 JSON-lines records: three `warning` records from the export (sitemap plugin,
Radix deprecation) and two `info` records from logger `reflex.console` (the level-less `console.print` lines
"deployment progress can now be viewed …" / "you are now safe to exit …", which JSON mode emits regardless of the
level). No record for the scaling waits, none for the success: a machine consumer of `--json` has only the exit code.

At the default level stdout ends with the 100 % "uploading the build" bar followed, 30 s later, by "deployment progress
can now be viewed on the website … you are now safe to exit this command …" — nothing is printed during the two 15 s
waits (`cc1-default.new.out` vs the `ts` column of `cc1-default.new.requests.json`); stderr is empty; exit 0 is the
only success signal.

Baseline (prev, 0.10.0 + 0.2.0; `logs/cc1-*.prev.*`; the scaling scenario is only used where noted, because
hosting-cli 0.2.0 has no scaling retry and fails the 409 with `deployment failed: The scale is finishing.` rc=1 —
`cc1-debug.prev`, the explorer's d01/r01 prev result):

| run (prev) | rc | "deployment completed successfully" | `Info:` lines |
|---|---|---|---|
| `cc1-default.prev` (plain success, no scenario) | 0 | **none** | 0 |
| `cc1-envinfo.prev` (`REFLEX_LOGLEVEL=info`) | 0 | `Info:` + `Success:` | 1 |
| `cc1-debug-plain.prev` (`--loglevel debug`, no scenario) | PENDING | | |

So the success line is hidden on 0.10.0 + 0.2.0 exactly the same way (the explorer's claim holds), and the hosting CLI
0.2.0 does emit it when the level allows. Not a regression in 0.10.1a1; the chain `export(loglevel=
config.loglevel.subprocess_level())` → `console.set_log_level()` in the deploy's export_fn is in v0.10.0 and v0.9.13
`reflex/hosting.py` (line 92 both) and already in v0.9.0 / v0.8.0 `reflex/reflex.py` (the deploy's export lambda), and
the `_log_level = LogLevel.INFO` / "write `REFLEX_LOGLEVEL` only when it changes" logic is in v0.9.13
`reflex_base/utils/log.py` lines 88 / 731-733. What is new in 0.10.1a1 is only that #7463 adds INFO-level progress for
waits of up to 15 s × 11 (165 s, explorer's d06) that this pre-existing reset silences.

Other post-export messages at the default level: PENDING (cc1-narr-*, cc1-bounds500)

## CC-2 — symlinks and `reflex export` / `reflex deploy` (`reflex/utils/build.py` `_zip`)

PENDING

## Cleanup
PENDING
