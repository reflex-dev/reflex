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
| `cc1-debug-plain.prev` (`--loglevel debug`, no scenario) | 0 | `Info:` + `Success:` | 1 |

So the success line is hidden on 0.10.0 + 0.2.0 exactly the same way (the explorer's claim holds), and the hosting CLI
0.2.0 does emit it when the level allows. Not a regression in 0.10.1a1; the chain `export(loglevel=
config.loglevel.subprocess_level())` → `console.set_log_level()` in the deploy's export_fn is in v0.10.0 and v0.9.13
`reflex/hosting.py` (line 92 both) and already in v0.9.0 / v0.8.0 `reflex/reflex.py` (the deploy's export lambda), and
the `_log_level = LogLevel.INFO` / "write `REFLEX_LOGLEVEL` only when it changes" logic is in v0.9.13
`reflex_base/utils/log.py` lines 88 / 731-733. What is new in 0.10.1a1 is only that #7463 adds INFO-level progress for
waits of up to 15 s × 11 (165 s, explorer's d06) that this pre-existing reset silences.

### Which other deploy messages are hidden (default level / `--loglevel info`), and which are not

Hidden = everything the hosting CLI logs at DEBUG / INFO / SUCCESS after the export step:

- the #7463 scaling waits for the submission (`cc1-default`) and, by the same `logger.info` in
  `reflex_cli/utils/deploy.py`, for the `--min/--max-instances` bounds retry (explorer's r07/d07/d18: up to 8 × 15 s);
- the deployment status narration while `reflex deploy` watches the deployment (`hosting.watch_deployment_status`
  `note()` → `logger.info`). Stub scenario `GET deployments/<id>/status` → "Deployment is being built." ×2,
  "Deployment is being provisioned.", "deployment completed successfully": `cc1-narr-default.new` prints none of
  them (0 `Info:` lines, 4 status polls, exit 0); `cc1-narr-debug.new` prints `Info: Deployment is being built.` /
  `Info: Deployment is being provisioned.` / `Info: deployment completed successfully` / `Success: deployment
  completed successfully`; `cc1-narr-default.prev` identical to new (5 polls, 0 lines). In a non-TTY run the watch
  phase is therefore completely silent until exit; in a TTY only the rich `console.status("listening to status
  updates!")` spinner moves (not level-gated), and during the scaling waits only the elapsed-time column of the 100 %
  upload bar ticks;
- the final `Success: deployment completed successfully` / `build submitted for approval; it will deploy
  automatically once an approver approves it.`;
- any later `--json` records for the above (`cc1-json.new`).

NOT hidden (so no error is swallowed; severity stays low): `logger.warning` and `logger.error` records, and level-less
`console.print` output. `cc1-bounds500.new` (default level, `--min-instances 1 --max-instances 2`, stub
`instance_bounds` → 500): stdout `Warning: Could not confirm the instance bounds of 'cliapp'; they may or may not have
been applied. …`, stderr `set instance bounds failed: internal`, rc=1. `cc2-deploy.*` (below): the export failure
`Unable to export due to: …` reaches stderr, rc=1. The explorer's r08/r09/r11/r12 `.err` files show the same for the
other error paths. The exit code is correct in every run (0 on success, 1 on every failure).

Workarounds that make the lines visible today: `REFLEX_LOGLEVEL=info reflex deploy …` (or `loglevel="info"` /
`rx.constants.LogLevel.INFO` in `rxconfig.py`), or `--loglevel debug` (very verbose: every zipped file is listed).
A `--loglevel info` flag is a silent no-op for this (see root cause step 2).

## CC-2 — symlinks and `reflex export` / `reflex deploy` (`reflex/utils/build.py` `_zip`)

### Mechanism (v0.10.1a1 lines 107-165; v0.10.0 lines 64-121 are the same walk, #7450 only changed the exclusion test)

`_zip` walks `os.walk(root_directory, topdown=True, followlinks=True)` and resolves each walked directory
(`directory_path = Path(directory_path).resolve()`), so a **directory symlink** whose target lies outside the resolved
app root produces file paths outside the root, and `file.relative_to(root_directory)` (line 164 / 121) raises
`ValueError: '<target>/file' is not in the subpath of '<app>'`. Pruned before descent, and therefore safe: directory
names in `directory_names_to_exclude` (`__pycache__`), anything starting with `.`, anything whose
`<dir>/pyvenv.cfg` exists (`_looks_like_venv_directory`, backend only), and paths excluded by identity with
`--exclude-from-backend`. File entries are joined, not resolved, so a **file symlink** is archived by content, and a
**dangling symlink** (not a dir, so listed as a file) fails later in `zipf.write` with `FileNotFoundError`.

### Matrix: `reflex export --backend-only --zip-dest-dir .` in a fresh app dir per case (`scripts/sym_matrix.sh`,
`logs/sym-<case>.<venv>.{out,err,rc,zip.txt}`); results identical for new (0.10.1a1) and prev (0.10.0)

| case | fixture | rc | result |
|---|---|---|---|
| c00-control | none | 0 | 4 entries |
| c01-dirlink-rel-out | `link_outside -> ../outside_target` | 1 | `ValueError … is not in the subpath of …`, raw traceback; partial `backend.zip` left (2 of 4+ entries, valid zip, `testzip()` None) |
| c02-dirlink-abs-out | `data -> /abs/outside_target` | 1 | same |
| c03-nested-dirlink | `assets/shared -> /abs/outside_target` (symlink below a normal dir) | 1 | same |
| c04-dotvenv-real | real `uv venv .venv` (`bin/python -> /usr/bin/python3.12`, `lib64 -> lib`) | 0 | `.venv` pruned (dot rule): **the realistic `.venv` case does NOT trigger it** |
| c05-venv-nodot-real | real `uv venv venv` | 0 | pruned (`pyvenv.cfg`) |
| c06-venvlink-out | `venv -> /abs/outside_venv` (dir symlink to a venv outside) | 0 | pruned: `pyvenv.cfg` is found through the link before descent |
| c07-filelink-out | `link.txt -> /abs/outside_target/file.txt` | 0 | archived by content (`link.txt`, 13 bytes `outside file`) |
| c08-dangling-link | `dangling -> /nonexistent/target` | 1 | `FileNotFoundError: [Errno 2] … '<app>/dangling'` in `zipf.write`, traceback; empty `backend.zip` (22 bytes) left. **Not in the explorer's claim** — same class, different exception |
| c09-link-in-pycache | `__pycache__/l -> outside` | 0 | pruned by name |
| c10-link-in-dotdir | `.hidden/l -> outside` | 0 | pruned (dot rule) |
| c11-dirlink-excluded | c02 + `--exclude-from-backend data` | 0 | identity exclusion works: usable workaround |
| c12-dirlink-inside | `alias -> cliapp` (target inside the app) | 0 | duplicate entries + Python `UserWarning: Duplicate name: 'cliapp/cliapp.py'` (explorer's other pre-existing note, reproduced) |
| c13-venv-nocfg-link | hand-rolled `env/` without `pyvenv.cfg` holding `lib -> /abs/outside_venv/lib` | 1 | `ValueError` (only `pyvenv.cfg` / the dot rule protect an environment directory) |

The frontend zip (`.web/_static`) is walked the same way but is produced by the build, so a user symlink is not
expected there.

### Through the real `reflex deploy` (`logs/cc2-deploy.{new,prev}.*`; `data -> <outside_target>` added to the
initialized app for the run and removed afterwards)

Both versions: rc=1 after 0.8-0.9 s, stderr `Unable to export due to: '<outside_target>/file.txt' is not in the
subpath of '<app dir>'` (the hosting CLI's `except Exception` around the backend export; no traceback), stdout ends at
`Zipping Backend: … 62% 8/13`; the stub saw `authenticate/me`, `GET apps/<id>`, `validate_cli`, `apps/reserve` and
nothing else (no reserve/upload/submit), and the CLI's `TemporaryDirectory` was removed (no `backend.zip` under `/tmp`
afterwards). So for `reflex deploy` the symptom is a clean one-line error with the offending path, not a crash; the
raw traceback and the leftover partial `backend.zip` are specific to `reflex export`.

Severity stays low: the trigger is a directory symlink (or a dangling link) in the app tree whose target leaves the
app root — monorepo-style `common -> ../shared` / `assets/shared -> …` layouts hit it, a `.venv`/`venv` (real or
symlinked) does not — the failure is deterministic, names the path, exits 1, and `--exclude-from-backend <link>`
avoids it. Pre-existing and identical on 0.10.0 (not a regression).

## Cleanup
Stubs killed by PID (`state-8740/fake_cp.pid`, `state-8741/fake_cp.pid`), ports 8740/8741 verified free; `app-new/.web`,
`app-prev/.web` and `node_modules` deleted; `sym/` case dirs (incl. the throwaway venvs) deleted. Artifacts copied to
`prerelease-testing/runs/2026-10-23-v0.10.1a1/verify_cc/` (`scripts/`, `app/`, `logs/`, this file).
