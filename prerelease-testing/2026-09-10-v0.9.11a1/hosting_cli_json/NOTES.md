# hosting_cli_json — reflex-hosting-cli 0.1.72a1 agent-usability + `reserve_stdout` (2026-09-11)

Cluster: PR [#6917](https://github.com/reflex-dev/reflex/pull/6917) ("make the cloud CLI
agent-usable": `--json` everywhere, non-interactive off a TTY, `--follow` opt-in),
PR [#6963](https://github.com/reflex-dev/reflex/pull/6963) (version comparison vs
reflex-0.7.6.post1), and `reflex_base.utils.log.reserve_stdout()`.

No Reflex Cloud account was available, so everything here is the offline-observable
surface: exit codes, stdout/stderr separation, JSON purity, help text, TTY detection,
and two code paths driven directly with the network stubbed.

## Environments

| name | contents | role |
|---|---|---|
| `$SB/envs/smoke` | reflex 0.9.11a1 + reflex-base 0.9.11a1 + reflex-hosting-cli 0.1.72a1 | system under test |
| `$SB/envs/base0910` | reflex 0.9.10.post2 + reflex-base 0.9.10.post2 + reflex-hosting-cli **0.1.71** | previous stable baseline |
| `$SB/envs/hcj_mixed` | reflex 0.9.10.post2 + reflex-base 0.9.10.post2 + reflex-hosting-cli **0.1.72a1** | the changelog's "older reflex-base" caveat |
| `$SB/envs/driver` | playwright | browser driver + test harness python |

`SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad`.
All installs are PyPI-only; every probe asserts the venv path of the package it imports and
runs from `/tmp`, never from the reflex checkout.

Recreate the mixed env (run `uv` from a neutral cwd, never inside `/home/user/reflex`):

```
cd $SB
uv venv $SB/envs/hcj_mixed --python 3.11
uv pip install --python $SB/envs/hcj_mixed/bin/python --prerelease=allow \
  'reflex==0.9.10.post2' 'reflex-hosting-cli==0.1.72a1'
```

Every command below sets `REFLEX_TELEMETRY_ENABLED=false NO_COLOR=1 COLUMNS=200` and runs
with **no cloud token** (there is no `~/.reflex/hosting_v1.json` and no
`REFLEX_ACCESS_TOKEN` unless a case sets one).

## Rerun

```
SB=/tmp/.../scratchpad ; D=<this dir>

# 1. off-TTY sweep of all 34 `reflex cloud` leaves x 6 flag variants (~100 s)
cd /tmp && $SB/envs/driver/bin/python $D/scripts/sweep_pipe.py $SB/envs/smoke/bin/reflex   $D/logs a1
cd /tmp && $SB/envs/driver/bin/python $D/scripts/sweep_pipe.py $SB/envs/hcj_mixed/bin/reflex $D/logs mixed
cd /tmp && $SB/envs/driver/bin/python $D/scripts/sweep_pipe.py $SB/envs/base0910/bin/reflex  $D/logs base0910

# 2. the same leaves under a real pty, stdin a pty nobody types into (~30 min: 18 x 2 hangs)
cd /tmp && $SB/envs/driver/bin/python $D/scripts/sweep_pty.py $SB/envs/smoke/bin/reflex $D/logs a1pty 40

# 3. which of --json / --interactive / --loglevel each leaf accepts
cd /tmp && $SB/envs/driver/bin/python $D/scripts/option_matrix.py $SB/envs/smoke/bin/reflex   $D/logs/option_matrix_a1.json
cd /tmp && $SB/envs/driver/bin/python $D/scripts/option_matrix.py $SB/envs/base0910/bin/reflex $D/logs/option_matrix_base0910.json

# 4. reserve_stdout() directly (pipes; then stdout-pty; then stderr-pty)
cd /tmp && $SB/envs/driver/bin/python $D/scripts/reserve_runner.py $SB/envs/smoke/bin/python $D/scripts/reserve_probe.py $D/logs/reserve_a1.json "/envs/smoke/"
cd /tmp && $SB/envs/driver/bin/python $D/scripts/reserve_pty_probe.py        $SB/envs/smoke/bin/python $D/logs
cd /tmp && $SB/envs/driver/bin/python $D/scripts/reserve_pty_stderr_probe.py $SB/envs/smoke/bin/python $D/logs

# 5. #6963 version comparison + the group callback's version gate
cd /tmp && $SB/envs/smoke/bin/python $D/scripts/version_probe.py > $D/logs/version_probe_a1.json

# 6. `apps logs --follow` semantics, with the two hosting helpers stubbed
cd /tmp && $SB/envs/smoke/bin/python $D/scripts/follow_probe.py > $D/logs/follow_probe_a1.json

# 7. a rejected token vs --no-interactive (stdin = an open pipe nobody writes to)
cd /tmp && $SB/envs/driver/bin/python $D/scripts/bad_token_hang.py $SB/envs/smoke/bin/reflex    a1       $D/logs 90
cd /tmp && $SB/envs/driver/bin/python $D/scripts/bad_token_hang.py $SB/envs/base0910/bin/reflex base0910 $D/logs 90

# 8. reflex init / run --json purity, and the app driven in Chromium
cd $D/jsonapp   && $SB/envs/smoke/bin/reflex init --template blank --json > $D/logs/init_json.out 2> $D/logs/init_json.err
cd $D/deployapp && $SB/envs/smoke/bin/reflex run --json --loglevel debug \
                     --frontend-port 5620 --backend-port 10020 > $D/logs/run_json.out 2> $D/logs/run_json.err &
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python \
  /home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py http://localhost:5620/ \
  --actions '[{"click":"#inc"},{"expect_text":"1"}]' --report $D/logs/drive_dev.json
```

The full per-command stdout/stderr of all four sweeps is in `logs/raw_sweeps.tar.gz`
(`raw_<label>/<command>__<variant>.{out,err}`); `evidence/` holds the individual files
cited below.

## Results table

| # | check | result |
|---|---|---|
| 1 | 34 `reflex cloud` leaves off a TTY, `--json`: stdout is empty or exactly one JSON document | **pass** |
| 2 | same, `--json --loglevel debug`: debug records on stderr, document alone on stdout | **pass** |
| 3 | same: all human text on stderr in `--json` mode (0 leaks in 34x3 runs) | **pass** |
| 4 | no-token auth failure exits 1 with `Token is required for non-interactive mode.` | **pass** |
| 5 | 34 leaves under a pty: interactive path taken, `--no-interactive` overrides in 0.4 s | **pass** |
| 6 | `--json` under a pty still blocks at the login prompt (18 of 34 leaves) | **fail** → ISSUE-2 |
| 7 | `--interactive` / `--no-interactive` accepted by every leaf | **fail** → ISSUE-3 (pre-existing) |
| 8 | `--json` accepted by every leaf ("Every `reflex cloud` command now takes `--json`") | **fail** → ISSUE-4 |
| 9 | `apps logs --help` documents `--follow` default off and why | **pass** |
| 10 | `apps logs --follow true` accepted and restores paging | **pass** |
| 11 | `apps logs --follow true --json` "refused outright" | **fail** → ISSUE-5 (silently ignored) |
| 12 | `reflex deploy --help` shows `--interactive`; off-TTY default is non-interactive | **pass** |
| 13 | `reflex deploy --json` off-TTY: JSON log records only, exit 1, no prompt | **pass** |
| 14 | `reserve_stdout()`: prints/logs/rules/tables/prompts move to stderr, back after release | **pass** |
| 15 | `reserve_stdout()`: spinner renders on stderr (stderr a tty) | **pass** |
| 16 | `reserve_stdout()`: progress bars "rendered to stderr" per the changelog | **anomaly** → ISSUE-6 (disabled instead) |
| 17 | `reserve_stdout()` nesting / exception safety / context-manager use | **anomaly** → ISSUE-7 |
| 18 | `reserve_stdout()` is process-global, not thread-local | **anomaly** (documented below) |
| 19 | #6963: `0.7.6.post1` / `.post2` now take the 6-argument `export_fn` path | **pass** |
| 20 | #6963: no spurious version warning under 0.9.11a1 / 0.9.10.post2 / 1.0.0rc1 / 0.7.6.post1 | **pass** |
| 21 | mixed: hosting-cli 0.1.72a1 + reflex-base 0.9.10.post2, `--json` alone | **pass** (clean) |
| 22 | mixed: `--json --loglevel debug` puts records on stdout ahead of the document | **anomaly** → ISSUE-8 (documented in the changelog, undetected at runtime) |
| 23 | `reflex init --json` and `--json --loglevel debug` stdout is strict JSON-lines | **pass** |
| 24 | `reflex run --json --loglevel debug` (dev, frontend+backend) stdout is strict JSON-lines | **fail** → pre-existing FINDING-016 |
| 25 | app served under `--json` driven in Chromium (load, 2 clicks, state round trip) | **pass** |
| 26 | a rejected token ignores `--no-interactive` and hangs at the login prompt | **fail** → ISSUE-1 |
| 27 | argv scan: `-j`, `-ij`, `--json --no-json`, `--no-json --json` | **pass** |
| 28 | `--token --json` (`--json` consumed as a value) leaves stdout empty, exit 0 | **anomaly** → ISSUE-9 |
| 29 | `reflex cloud token --print/--set/--clear` off a TTY | **pass** (one nit, ISSUE-10) |
| 30 | `reflex cloud regions\|vmtypes\|config --json` exit 0 after a failure | **fail** → campaign FINDING-015 (pre-existing) |
| 31 | per-command latency (PyPI `check_version` round trip on every cloud command) | **pass** (~0.44 s with or without network) |
| 32 | commands needing a live cloud account (`delete --json` `"deleted": false`, real `apps list` payloads) | **skipped** (no account) |

## Issues

### ISSUE-1 (HIGH, pre-existing): a rejected token ignores `--no-interactive` and hangs forever

`reflex_cli/utils/hosting.py:get_authenticated_client` consults `interactive` **only when no
token is present at all**:

```python
env_token = get_existing_access_token() if not token else ""
if not token and not env_token and not interactive:
    logger.error("Token is required for non-interactive mode.")
    raise click.exceptions.Exit(1)

client = get_authentication_client(token)
if isinstance(client, UnAuthenticatedClient):
    return client.authenticate()          # browser login + blocking prompt
return client
```

So a token that exists but is rejected (expired, rotated, wrong org — the normal CI failure)
falls through to `authenticate()`, which opens a browser and waits at
`please hit 'Enter' or 'Return' after login on website complete:` **regardless of
`--no-interactive`, `--json`, or stdout not being a terminal**.

Repro (stdin must be an open pipe nobody writes to; `</dev/null` hides it behind an
immediate EOF abort):

```
cd /tmp && $SB/envs/driver/bin/python <thisdir>/scripts/bad_token_hang.py \
  $SB/envs/smoke/bin/reflex a1 /tmp/out 90
```

or by hand:

```
cd /tmp
rm -f /tmp/never; mkfifo /tmp/never; exec 9<> /tmp/never   # a pipe that never delivers
REFLEX_TELEMETRY_ENABLED=false REFLEX_ACCESS_TOKEN=bogus-token-123 \
  timeout 45 $SB/envs/smoke/bin/reflex cloud apps list --json --no-interactive <&9 > out 2> err
echo "rc=$?"          # 124 -- timeout killed it; without `timeout` it never returns
exec 9>&-; rm -f /tmp/never
# err ends with "please hit 'Enter' or 'Return' after login on website complete:";
# out is 0 bytes (the reservation holds while it hangs)
```

| case | 0.9.11a1 + 0.1.72a1 | 0.9.10.post2 + 0.1.71 |
|---|---|---|
| no token, `--json --no-interactive` | exit 1 in 0.4 s | exit 1 in 0.6 s |
| `--token bogus --json` | **hang** (90 s timeout) | **hang** |
| `--token bogus --json --no-interactive` | **hang** | **hang** |
| `REFLEX_ACCESS_TOKEN=bogus`, `--json --no-interactive` | **hang** | **hang** |
| `REFLEX_ACCESS_TOKEN=bogus`, plain | **hang** | **hang** |
| `REFLEX_ACCESS_TOKEN=bogus`, `cloud whoami --json` | exit 1 in 0.7 s | exit 1 in 0.9 s |
| `REFLEX_ACCESS_TOKEN=bogus`, `project list --json --no-interactive` | **hang** | **hang** |

**Identical on 0.9.10.post2, so not a regression** — but it is the exact failure #6917 set out
to remove, and it falsifies the shipped help text ("so a pipe, a CI job or an agent is never
left waiting at a prompt") and the changelog ("a pipe, a CI job or an agent is refused with an
error instead of waiting at a prompt that nobody answers"). `reserve_stdout` still holds while
it hangs — stdout stays 0 bytes — so an agent sees no output at all and no exit.
`reflex cloud whoami` is the only command immune, because it never starts a login.

Evidence: `logs/badtoken_a1.json`, `logs/badtoken_base0910.json`,
`evidence/badtoken_a1_bad_token_env_nointeractive.{out,err}`,
`evidence/badtoken_base0910_bad_token_env_nointeractive.err`, `logs/bogus_token.txt`.

### ISSUE-2 (MEDIUM): `--json` does not imply non-interactive, so a pty hangs the "agent" flag

Interactivity is derived from `sys.stdout.isatty()` and nothing else, so under a pseudo-terminal
— `script -qfc`, `docker run -t`, tmux, any pty-based agent wrapper — `--json` still takes the
interactive path and blocks at the login prompt. 18 of 34 leaves hang with `--json` alone;
`--no-interactive` returns in 0.4 s for every one of them.

```
cd /tmp && $SB/envs/driver/bin/python <thisdir>/scripts/sweep_pty.py $SB/envs/smoke/bin/reflex /tmp/out a1pty 40
# tty_json column: 18 x rc=TIMEOUT at 40.0 s, stdout 0 bytes, prompt on stderr
```

The reservation itself behaves correctly here — the prompt renders to stderr and stdout stays
byte-empty (`evidence/raw_a1pty.cloud_apps_list__tty_json.{out,err}`) — the command simply never
returns. A caller asking for a machine-readable document is by construction not a person at a
keyboard; `--json` implying `--no-interactive` (or `--json` warning when it resolves interactive
to on) would close this. Not a regression: 0.1.71 hangs the same way with or without a pty,
because its `--interactive` defaulted to on everywhere.

Evidence: `logs/sweep_a1pty.json`, `evidence/raw_a1pty.cloud_apps_list__tty_*.{out,err}`.

### ISSUE-3 (LOW, pre-existing): four leaves reject `--interactive` / `--no-interactive` with exit 2

`cloud whoami`, `cloud regions`, `cloud vmtypes` and `cloud token` carry no interactive option,
so a uniform agent wrapper that appends `--no-interactive` to every cloud command dies with
`Error: No such option '--no-interactive'.` and exit 2 on those four:

```
cd /tmp
$SB/envs/smoke/bin/reflex cloud whoami --json --no-interactive   # exit 2
$SB/envs/smoke/bin/reflex cloud regions --no-interactive         # exit 2
$SB/envs/smoke/bin/reflex cloud vmtypes -i                       # exit 2
```

Functionally none of the four needs it (whoami never logs in, regions/vmtypes do not
authenticate), so the impact is the inconsistency plus the changelog's blanket
"Pass `--interactive` to restore the old behavior", which cannot be followed for them.
`--loglevel` is likewise missing from `cloud config` and `cloud apps build-logs`, so
`reflex cloud config --loglevel debug` exits 2 while `reflex cloud config` exits 0
(`evidence/raw_a1.cloud_config__debug.err`).

**Identical in 0.1.71** (`logs/option_matrix_base0910.json`) — pre-existing, not a regression.

### ISSUE-4 (LOW): `reflex cloud token` has no `--json`, contradicting "every command"

The changelog says "Every `reflex cloud` command now takes `--json`"; the PR body says "all 33
commands". There are 34 leaves and `cloud token` is the one without it. Its help explains why
(`--print` writes the raw token to stdout), so this is a changelog-wording gap rather than a
missing feature, but an agent enumerating `reflex cloud --help` and appending `--json` hits
`Error: No such option '--json'.` / exit 2 on it.

```
cd /tmp && $SB/envs/smoke/bin/reflex cloud token --print --json   # exit 2
```

Evidence: `logs/option_matrix_a1.json` (full help text per command), `logs/misc_checks.txt`.

### ISSUE-5 (LOW): `apps logs --follow true --json` is silently ignored, not "refused"

The PR says following is "refused outright in JSON mode, where paging belongs to the caller".
In the shipped code it is dropped without a word:

```python
following = follow and interactive and not as_json
```

Offline the command dies at authentication first, so this needs the two hosting helpers
stubbed. `scripts/follow_probe.py` invokes the real `apps_mod.app_logs` command object through
`CliRunner` with `hosting.get_authenticated_client` / `hosting.get_app_logs` replaced by fakes
serving two pages:

```
cd /tmp && $SB/envs/smoke/bin/python <thisdir>/scripts/follow_probe.py
```

| case | pages fetched | prompted | exit | message about `--follow` |
|---|---|---|---|---|
| `app1` (default) | 1 | no | 0 | — |
| `app1 --follow true --interactive` | 1 then prompts | **yes** | 0 | — |
| `app1 --follow true --json` | 1 | no | 0 | **none** |
| `app1 --follow true --json --interactive` | 1 | no | 0 | **none** |
| `app1 --follow true --no-interactive` | 1 | no | 0 | **none** |

The JSON document does carry `cursor`, so nothing is lost functionally; a script that asked to
follow just silently gets one page. Not a regression (0.1.71 had no `--json` on this command at
all). Evidence: `logs/follow_probe_a1.json`.

The help text and the default itself are correct: `--follow` is `BOOLEAN`, defaults to off,
`--follow true` restores paging, `--follow` with no value is a clean
`Error: Option '--follow' requires an argument.` and `--follow maybe` lists the accepted
spellings (`logs/follow_matrix.txt`).

### ISSUE-6 (LOW): progress bars are suppressed while stdout is reserved, not moved to stderr

reflex-base changelog: "rendering log records, tables, rules, prompts, spinners and progress
bars **to stderr** for as long as it is set". `console.progress()` instead builds the bar with
`disable=_log.is_json_mode() or _log.is_stdout_reserved()`, so it renders nowhere:

```
cd /tmp && $SB/envs/driver/bin/python <thisdir>/scripts/reserve_pty_stderr_probe.py $SB/envs/smoke/bin/python /tmp/out
```

| surface | unreserved | reserved |
|---|---|---|
| `console.print` / `print_table` / `rule` | stdout | **stderr** |
| `console.status()` spinner | stdout | **stderr** |
| `console.progress()` bar | stdout | **absent** (`disable=True`) |

stdout stays clean either way, which is what matters; the consequence is that a long `--json`
operation shows no progress at all rather than progress on stderr. Doc-vs-code wording gap.
Evidence: `logs/reserve_pty.stdout.txt` / `.stderr.txt`, `logs/reserve_ptyerr.*`, `logs/reserve_a1.json`.

### ISSUE-7 (LOW): `reserve_stdout()` has no scope — no nesting, no exception safety, not a context manager

`reserve_stdout(reserved=True)` sets a module boolean and returns `None`.

```
cd /tmp && $SB/envs/driver/bin/python <thisdir>/scripts/reserve_runner.py \
  $SB/envs/smoke/bin/python <thisdir>/scripts/reserve_probe.py /tmp/reserve.json "/envs/smoke/"
```

- `reserve_stdout(True); reserve_stdout(True); reserve_stdout(False)` leaves it **unreserved** —
  no depth counter, so an inner release cancels an outer reservation.
- a `raise` between `reserve_stdout(True)` and `reserve_stdout(False)` leaves stdout reserved
  for the rest of the process (`META reserved_after_exception=True`).
- `with reserve_stdout():` raises `TypeError: 'NoneType' object does not support the context
  manager protocol`, although the name reads like a context manager.
- it is a process global, not thread-local: a worker thread's `console.print` is redirected to
  stderr while the main thread holds the reservation (`MARK thread console.print` lands on
  stderr).

None of this bites the CLI, which pairs the set with `ctx.call_on_close` in
`reflex_cli/utils/output.py:_hold_reservation`, but it is a public reflex-base API as of this
release and an embedder gets no scoped form. (The context-manager and exception points were
already noted in `orch_probes/NOTES.md`; the nesting and threading behaviour is new here.)

### ISSUE-8 (LOW, documented): against reflex-base 0.9.10, `--json --loglevel debug` corrupts the document, with no warning

The changelog documents this, and it reproduces exactly. In `$SB/envs/hcj_mixed`
(reflex-base 0.9.10.post2 + hosting-cli 0.1.72a1):

```
cd /tmp && $SB/envs/hcj_mixed/bin/reflex cloud project selected --json --loglevel debug
# stdout:
#   Debug: Unable to read selected project from .../hosting_v1.json due to: ...
#   {"project_id": null, "name": null, "error": null}
# stderr: (empty)
```

versus 0.9.11a1, where the Debug line is on stderr and stdout holds the document alone.
19 of 34 leaves differ this way (`json_debug` column of `logs/sweep_mixed.json` vs
`logs/sweep_a1.json`). `--json` at the default log level stays clean in both.

Why the CLI's own fallback does not help: `reflex_cli/utils/log.py` takes the full fallback path
(its own `RichConsoleHandler`, which does honour `is_stdout_reserved()`) only when `reflex_base`
is **absent**. With reflex-base 0.9.10 present it exports `SUCCESS` / `is_json_mode` /
`set_log_level`, so `HAS_REFLEX_BASE` is True and rendering is delegated to reflex-base's
handler, which writes to its own stdout console. Only the second import (`reserve_stdout` /
`is_stdout_reserved`) falls back, giving the CLI a boolean nothing consults.

reflex 0.9.11a1 pins `reflex-base==0.9.11a1`, so this only reaches a user who upgrades
reflex-hosting-cli on its own — realistic once 0.1.72 is final, since reflex pins the hosting
CLI by floor. Nothing detects or warns about the combination at runtime. Evidence:
`evidence/raw_mixed.cloud_project_selected__json_debug.{out,err}` vs
`evidence/raw_a1.cloud_project_selected__json_debug.{out,err}`.

### ISSUE-9 (INFO): `--json` consumed as another option's value silently empties stdout

Documented as a deliberate trade-off in `reflex_cli/utils/output.py` ("a message on stderr costs
a little context, one inside the document costs the whole parse"), recorded because the visible
result is a success with no output at all:

```
cd /tmp && $SB/envs/smoke/bin/reflex cloud project selected --token --json
# exit 0, stdout 0 bytes, stderr: "Warning: no selected project. ..."
```

The argv scan reserves stdout on the literal `--json`, click binds it as the value of `--token`,
so `as_json` is False and the human message goes to stderr — leaving nothing on stdout.
All the intended argv-scan behaviours are correct: `-j`, `-ij` (combined shorts, prompt on
stderr, stdout empty), and last-flag-wins for `--json --no-json` / `--no-json --json`
(`logs/argv_scan_checks.txt`, `logs/misc_checks.txt`).

### ISSUE-10 (INFO): `reflex cloud token --clear` reports success when there was nothing to clear

```
cd /tmp && $SB/envs/smoke/bin/reflex cloud token --clear
# exit 0, stdout: "Success: Cleared the stored access token."
```

with no `~/.local/share/reflex/hosting_v1.json` present. Everything else about `cloud token` is
clean off a TTY: `--print` with no token exits 1 on stderr, `--set bogus` exits 1 with
`Token rejected, nothing was saved: 403 Forbidden`, `--set -` reads the token from stdin,
and `--print --set x` / no flag at all exit 2 with an explicit message (`logs/token_cmd.txt`).

### Also observed (no issue filed)

- `reflex cloud project list --token <bad> --json` ends with
  `Unable to get projects: EOF when reading a line` — a raw `EOFError` string surfacing as a
  user-facing error (`logs/bogus_token.txt`). Same on 0.9.10.post2.
- `reflex cloud vmtypes` with **no** `--json` prints `[]` on stdout after a 403; `regions`
  prints nothing. Both exit 0. That is the campaign's FINDING-015 (pre-existing), confirmed
  again here in all four sweeps.
- `reflex deploy` off a TTY with no token runs the whole `reflex init` step (creates `.web/`)
  before discovering it has no credentials (`evidence/deploy_plain.out`). Same on 0.9.10.post2.
- every `reflex cloud` invocation makes a PyPI round trip (`check_version()`), and exits 1 if a
  newer reflex-hosting-cli is published. Measured cost is ~0.25 s, and ~0.44 s total per command
  with or without network, so no latency finding; worth knowing that a future stable release
  will start hard-failing every cloud command for anyone still on this alpha.

## What passed, in detail

**`--json` purity off a TTY (the headline claim).** 34 leaves x {`--json`, `--json --loglevel
debug`, `--json --no-interactive`, `--json --interactive`}: stdout is either empty or exactly one
`json.loads`-able document, in every single run; no human text ever reaches stdout in `--json`
mode. Commands missing a required argument exit 2 with the usage line on stderr; auth-required
commands exit 1 with `Token is required for non-interactive mode.` on stderr. The four commands
that do produce a document offline are `cloud config` (`{"generated": false, "path": null}`),
`cloud project selected` (`{"project_id": null, "name": null, "error": null}`), `cloud regions`
and `cloud vmtypes` (`[]`).

**The breaking default, against the baseline.** On reflex 0.9.10.post2 / hosting-cli 0.1.71,
`reflex cloud apps list` off a TTY printed the browser-login URL **to stdout** and sat at
`please hit 'Enter' ...` (`evidence/raw_base0910.cloud_apps_list__plain.out`); `--json` did not
exist on most commands (`evidence/raw_base0910.cloud_apps_logs__json.err`:
`Error: No such option '--json'.`). Both are fixed. `--follow` really did default to `True`
in 0.1.71 (`apps.py:653`) and `--interactive` to `default=True` in ~30 places.

**Under a pty.** Interactive is genuinely derived from the terminal: 18 leaves take the login
path and block (as a human would want), `--no-interactive` returns in 0.4 s for all of them, and
`cloud whoami` / `regions` / `vmtypes` / `config` / `project selected` return immediately either
way.

**`reserve_stdout()`.** With the reservation set, `console.print/info/success/warn/error/debug`,
`console.rule`, `console.print_table`, `rich.Prompt` (the login prompt, verified through the real
CLI under a pty) and stdlib log records from the `reflex` logger tree all render to stderr;
stdout receives zero bytes. Releasing it restores stdout for every one of them. `REFLEX_LOG_JSON=1`
combined with `--json` also behaves: JSON log records to stderr, the document alone on stdout
(`logs/logjson_env.txt`).

**#6963.** `scripts/version_probe.py` evaluates the shipped predicate
(`rx_version.release < (0, 7, 7)`, read out of `inspect.getsource(cli.deploy)`) and the pre-#6963
one (`rx_version <= version.parse("0.7.6")`) over 13 versions: the only rows that change are
`0.7.6.post1` and `0.7.6.post2`, which now correctly take the 6-argument `export_fn` path.
`0.7.7`, `0.7.7rc1`, `0.9.10.post2`, `0.9.11a1`, `1.0.0rc1` and `1.0.0` all take the 7-argument
path, unchanged. The group callback's gate (`MINIMUM 0.6.6.post1`, `RECOMMENDED 0.7.6`) emits no
deprecation warning for `0.7.6.post1`, `0.9.10.post2`, `0.9.11a1` or `1.0.0rc1`, and the real CLI
under reflex 0.9.11a1 prints nothing extra on stderr for any of the 204 sweep runs.
(`reflex 0.6.6` exactly is hard-rejected, since the minimum is `0.6.6.post1` — the error names
that version, so it is accurate, just a surprising boundary.)

**`reflex deploy`.** `--help` carries `-i, --interactive / --no-interactive` with the
terminal-derived wording. Off a TTY: bare `reflex deploy` and `--no-interactive` exit 1 with
`Token is required for non-interactive mode.` and never prompt; `--interactive` does prompt
(proving the override) and aborts on EOF; `--json` and `--json --loglevel debug` emit **strict
JSON-lines on both streams** (non-error records on stdout, error records on stderr) and exit 1.
`logs/deploy_matrix.txt`, `evidence/deploy_*`.

**`reflex init --json`** (3 records) and **`--json --loglevel debug`** (48 records): 100% of
stdout lines parse as JSON, stderr empty.

**The app itself.** `deployapp/` run with `reflex run --json --loglevel debug` on ports
5620/10020 served 200, `/ping` 200, and Chromium drove it clean — heading present, two clicks on
`#inc`, state reaching 2, zero console errors, zero failed requests
(`logs/drive_dev.json`, `shots/deployapp_dev.png`).

**`reflex run --json` is still not strict JSON-lines** — 4 plain-text granian lines
(`[INFO] Starting granian ...`) among 93 stdout lines in full dev mode
(`logs/run_json.granian_lines.txt`). Unchanged from the campaign's FINDING-016, which saw the
same 9 lines in `--backend-only`; recorded here only to confirm it also applies to a normal
`reflex run`, and that #6917's `reserve_stdout` treatment has not reached `reflex run`.

## Ports and cleanup

Only `reflex run --frontend-port 5620 --backend-port 10020` bound anything, for one dev-mode
session. Verified with `ps aux | grep -E 'reflex|granian|vite|bun|chrom|redis|node '` and
`ss -ltnp` that nothing of this cluster's is left running and both ports are free.

## VERIFICATION: A rejected cloud token ignores --no-interactive and hangs forever at the browser-login prompt

Independent adversarial re-check of ISSUE-1 by a second agent (2026-09-11). Own working dir
`$SB/apps/verify2_hosting_cli_json_0`, own scripts, claimant's processes not used.

**Verdict: CONFIRMED — genuine defect, NOT a regression (identical on 0.9.10.post2 + hosting-cli
0.1.71), not downstream-breaking, not an environment artifact.** Two corrections to the claim are
recorded below (the 403 in the claimant's evidence came from this sandbox's egress proxy, not from
Reflex Cloud; and the indefinite hang needs stdin to be an open never-written pipe — with
`</dev/null` or closed stdin the same command exits 1 in ~0.5 s while still ignoring
`--no-interactive`).

### 1. The claimant's written repro reproduces verbatim

```
cd $SB/apps/verify2_hosting_cli_json_0
./myrepro.sh $SB/envs/smoke/bin/reflex ./out/a1_env_nointeractive 45
# rc=124 elapsed=45.01s out_bytes=0 err_bytes=523
# stderr ends: "please hit 'Enter' or 'Return' after login on website complete:"
```
Evidence: `verification/badtoken_hang/evidence/a1_env_nointeractive.{out,err}`.

### 2. Refutation attempt: is the 403 an artifact of this sandbox's proxy? (partly yes — and it does not matter)

`build.reflex.dev` is **blocked by the agent egress proxy here**, and the proxy itself answers
`403 Forbidden`:

```
cd /tmp && curl -sS -D - -o /dev/null -X POST \
  "https://build.reflex.dev/api/v1/authenticate/me?source=reflex" -H "X-API-TOKEN: bogus-token-123"
# HTTP/1.1 403 Forbidden  + "[agent-proxy] ... connect_rejected (the egress proxy denied the CONNECT)"
```

So the claimant's `403 Forbidden (auth request id: ...)` lines are the proxy talking, not Reflex
Cloud. That does **not** rescue the behaviour: `validate_token_with_retries` collapses *every*
failure — 403, 500, timeout, DNS, connection refused — to `{}`
(`reflex_cli/utils/hosting.py:3276-3289`), so the code path is the same one a genuinely expired or
rotated token takes. To remove the sandbox from the picture entirely I ran the CLI against a
**local stand-in control plane** (`verification/badtoken_hang/fake_control_plane.py`, no external
network, no proxy) that answers `POST /api/v1/authenticate/me` with a real `403 {"detail":
"Invalid or expired token"}`:

```
cd /tmp && $SB/envs/driver/bin/python \
  /home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/hosting_cli_json/verification/badtoken_hang/fake_control_plane.py 10720 reject &
cd $SB/apps/verify2_hosting_cli_json_0
./local_repro.sh $SB/envs/smoke/bin/reflex 10720 ./out/local_a1_reject 30 cloud apps list --json --no-interactive
# rc=124 elapsed=30.0s out_bytes=0 err_bytes=355 -> hangs at the prompt
```

**Control (the decisive one):** the same binary, same flags, same stdin, against the same server
started in `accept` mode (port 10721, `200` + a user payload) returns normally:

```
./local_repro.sh $SB/envs/smoke/bin/reflex 10721 ./out/local_a1_accept 30 cloud apps list --json --no-interactive
# rc=0 elapsed=0.98s stdout "[]"  (stderr empty)
```

So the hang is caused specifically by the token being rejected, not by anything about this
environment. Evidence: `verification/badtoken_hang/evidence/local_a1_reject.*`,
`local_a1_accept.*`.

### 3. My own case matrix (local rejecting control plane, stdin = open pipe, 25 s cap)

`verification/badtoken_hang/case_matrix.sh`:

| case | 0.9.11a1 + 0.1.72a1 | 0.9.10.post2 + 0.1.71 |
|---|---|---|
| no token, `--json --no-interactive` | exit 1, 0.4 s, stderr 71 B | exit 1, 0.6 s |
| `--token bogus --json` | **hang** 25 s, stdout 0 B | **hang**, stdout 355 B |
| `--token bogus --json --no-interactive` | **hang**, stdout 0 B | **hang**, stdout 355 B |
| `REFLEX_ACCESS_TOKEN=bogus`, `--json --no-interactive` | **hang**, stdout 0 B | **hang**, stdout 355 B |
| `REFLEX_ACCESS_TOKEN=bogus`, plain | **hang**, stdout 355 B | **hang**, stdout 355 B |
| `REFLEX_ACCESS_TOKEN=bogus`, `cloud whoami --json` | exit 1, 0.5 s | exit 1, 0.7 s |
| `REFLEX_ACCESS_TOKEN=bogus`, `project list --json --no-interactive` | **hang** | **hang** |
| `REFLEX_ACCESS_TOKEN=bogus`, `secrets list --json --no-interactive` | **hang** | **hang** |

```
cd /tmp && <fake_control_plane.py 10720 reject> &
$SB/apps/verify2_hosting_cli_json_0/case_matrix.sh $SB/envs/smoke/bin/reflex    10720 a1local    25
$SB/apps/verify2_hosting_cli_json_0/case_matrix.sh $SB/envs/base0910/bin/reflex 10720 b0910local 25
```

Baseline reproduced **by me**, not taken on trust: 0.9.10.post2 + hosting-cli 0.1.71 hangs in
exactly the same five cases. **Pre-existing, not a regression of this train.** 0.1.72a1 is strictly
better in one respect — the prompt and login URL now go to stderr and stdout stays byte-empty in
`--json` mode, where 0.1.71 wrote all 355 bytes to stdout
(`evidence/b0910local_env_json_nointeractive.out`).

### 4. Mechanism (release branch `origin/r/pre-2026.09.10-34457666442`)

`packages/reflex-hosting-cli/src/reflex_cli/utils/hosting.py:327-335` — `interactive` is consulted
only on the no-token branch; a token that exists but does not validate falls straight into
`UnAuthenticatedClient.authenticate()`:

```python
env_token = get_existing_access_token() if not token else ""
if not token and not env_token and not interactive:      # only the *missing* token case
    logger.error("Token is required for non-interactive mode.")
    raise click.exceptions.Exit(1)

client = get_authentication_client(token)                 # validate -> {} on ANY failure
if isinstance(client, UnAuthenticatedClient):
    return client.authenticate()                          # webbrowser.open + console.ask, unconditional
```

- `hosting.py:3276-3289` `validate_token_with_retries` -> `{}` for 403 *and* for timeouts/5xx/DNS.
- `hosting.py:291-308` `get_authentication_client` -> `UnAuthenticatedClient()` when info is empty.
- `hosting.py:3239` `console.ask("please hit 'Enter' or 'Return' after login on website complete")`
  — `reflex_base.utils.console.ask` is a bare `rich.Prompt.ask` with no interactivity guard and no
  timeout, so with an open stdin it blocks indefinitely.
- 30 call sites pass `interactive=` into `get_authenticated_client` (all of `reflex_cli/v2/*.py`
  plus `cli.py:599` for `reflex deploy`), so every one of them inherits the gap.

The shipped help text this falsifies is
`packages/reflex-hosting-cli/src/reflex_cli/utils/output.py:94-103`: "Defaults to on when stdout is
a terminal and off otherwise, **so a pipe, a CI job or an agent is never left waiting at a
prompt.**" (`reflex cloud apps list --help`). Note the CHANGELOG entry
(`packages/reflex-hosting-cli/CHANGELOG.md:5`) narrows its worked example to "in CI **with no
token**", which does work; the help text carries no such qualifier.

### 5. Extra finding beyond the claim: `reflex deploy --json` also corrupts stdout while it hangs

`reflex deploy` calls `get_authenticated_client` first thing (`cli.py:599`), before any build work,
so a rejected token stalls a CI deploy too — and because `deploy --json` does not reserve stdout,
the prompt is appended to the JSON-lines stream as raw text:

```
cd $SB/apps/verify2_hosting_cli_json_0
./local_repro_cwd.sh $SB/envs/smoke/bin/reflex 10720 ./out/local_a1_deploy2 40 ./minapp deploy --json --no-interactive
# rc=124 elapsed=40.0s, stdout 2150 B: 5 JSON records + line 6 = "please hit 'Enter' or 'Return' after login on website complete: "
```
(1 of 6 stdout lines is not JSON.) Evidence: `verification/badtoken_hang/evidence/local_a1_deploy2.out`,
app source `verification/badtoken_hang/minapp/`.

### 6. Correction to the claim: the hang needs a never-closing stdin

The claim calls the pipe shape "the most likely CI configuration". Measured, on 0.9.11a1 against the
local rejecting plane:

| stdin | result |
|---|---|
| open pipe nobody writes to (agent `Popen(stdin=PIPE)`, `ssh host reflex ...`, `docker run -i`) | **hangs indefinitely**, stdout 0 B |
| `</dev/null` | exit 1 in 0.52 s |
| closed (`0<&-`) | exit 1 in 0.49 s |

Runners that hand steps `/dev/null` (GitHub Actions, and anything under `nohup`) therefore fail
fast — but they *still* ignore `--no-interactive`: the CLI opens a browser
(`webbrowser.open`, or warns it could not), writes the prompt, and then reports the misleading
`Unable to list deployments` instead of naming the rejected token. Evidence:
`evidence/stdin_devnull.err`, `evidence/stdin_closed.err`.

`reflex cloud whoami` stays immune (it validates and exits 1 with an accurate message); the
workaround for everything else is to redirect stdin from `/dev/null`.

### 7. Severity / regression judgement

- **confirmed: yes** — genuine defect, minimal repro is offline and 20 lines of server stub.
- **regression: no** — reproduced identically on 0.9.10.post2 + 0.1.71 by this verifier.
- **downstream: no** — CLI behaviour only; no framework API change, nothing downstream code breaks on.
- **severity: high** as a fix priority, with the caveat in §6. What is new in this train is the
  *guarantee* ("never left waiting at a prompt"), shipped by the very PR whose goal was agent
  usability, while the agent-shaped invocation (subprocess with a stdin pipe) is exactly the one
  that still hangs with zero bytes on stdout and no exit. Normal credential expiry — and any
  transient control-plane error — triggers it. By the campaign's own rule (both versions affected =>
  context, not a blocker) it is not a release blocker; the one-line fix is to apply the
  `not interactive` guard to the `UnAuthenticatedClient` fall-through as well.

### Ports / cleanup

Used only reserved backend ports 10720 (reject stub) and 10721 (accept stub); both python stubs
killed (`pkill -f fake_control_plane.py`), verified with `ps aux` and `ss -ltnp`. No reflex server,
browser or redis was started.

## VERIFICATION: --json does not imply non-interactive, so every cloud command hangs under a pseudo-terminal

Independent adversarial verification of ISSUE-2 by a second agent, reproduced from the written
repro alone in its own working dir
(`$SB/apps/verify2_hosting_cli_json_1`, shared venvs `$SB/envs/smoke` = reflex 0.9.11a1 /
reflex-hosting-cli 0.1.72a1 and `$SB/envs/base0910` = reflex 0.9.10.post2 / 0.1.71).

**VERDICT: CONFIRMED, but narrower and milder than claimed — severity LOW, not medium.**
The mechanism is real and I reproduced it; the title ("every cloud command hangs under a
pseudo-terminal") and the written repro command both overstate it. Not a regression: the
release is a *strict improvement* over 0.1.71 in every cell of the matrix. Recommend treating
it as a post-release polish item, not a release blocker.

### What reproduces

Consolidated minimal repro (mine, not the claimant's sweep):

```
cd $SB/apps/verify2_hosting_cli_json_1
$SB/envs/driver/bin/python verification/json_pty_interactive/verify_json_pty.py \
    $SB/envs/smoke/bin/reflex 12 /tmp/out_a1
$SB/envs/driver/bin/python verification/json_pty_interactive/verify_json_pty.py \
    $SB/envs/base0910/bin/reflex 12 /tmp/out_b0910
```

It runs `reflex cloud apps list` with stdout as a pty vs a pipe, crossed with
`--json` / `--no-interactive` / neither, and with stdin as a pty, an open pipe nobody writes to,
and `/dev/null`. No token is present (`REFLEX_ACCESS_TOKEN` unset, no `hosting_v1.json`).

| stdout | stdin | args | 0.9.11a1 (0.1.72a1) | 0.9.10.post2 (0.1.71) |
|---|---|---|---|---|
| pty  | pty        | `--json`           | **HANG**, stdout 0 B, prompt on stderr | **HANG**, prompt on **stdout** (448 B) |
| pty  | pty        | `--no-interactive` | rc=1 in 0.41 s | rc=1 in 0.63 s |
| pty  | pty        | (none)             | **HANG**, prompt on stdout | **HANG**, prompt on stdout |
| pipe | pty        | `--json`           | rc=1 in 0.39 s | **HANG**, prompt on **stdout** (414 B) |
| pipe | pty        | `--no-interactive` | rc=1 in 0.39 s | rc=1 in 0.58 s |
| pipe | pty        | (none)             | rc=1 in 0.44 s | **HANG** |
| pty  | pipe held open | `--json`       | **HANG** | **HANG** |
| pty  | `/dev/null`    | `--json`       | rc=1 in 0.40 s (EOF aborts the prompt) | rc=1 in 0.56 s |

Evidence: `verification/json_pty_interactive/summary_a1.json`,
`summary_base0910.json`, `evidence/a1.ptyout_json.{out,err}` (stdout byte-empty, prompt on
stderr — the reservation is correct), `evidence/base0910.pipeout_json.out` (0.1.71 writing the
login prompt into what `--json` promised was the document).

Breadth spot check, 12 leaves, stdout+stdin a pty, `--json` only, 9 s timeout
(`verification/json_pty_interactive/leaf_breadth.txt`): 7 hang (`apps list`, `apps history`,
`apps scale`, `apps start`, `project list`, `providers list`, `scan`); the 5 that return either
never authenticate (`whoami`, `regions`, `config`, `project selected`) or failed my invocation
(`secrets list`, exit 2 on a missing required option). Consistent with the claimant's 18/34.

### Corrections to the claim

1. **The written repro command does not hang as written.** Run verbatim from a normal
   non-interactive shell,
   `REFLEX_TELEMETRY_ENABLED=false script -qfc "$SB/envs/smoke/bin/reflex cloud apps list --json" /dev/null`
   **returns in 1 s** (`$SB/apps/verify2_hosting_cli_json_1/out/literal_pty_json.log`): `script`
   forwards its own already-at-EOF stdin, the prompt gets EOF and the command exits. It hangs
   only when stdin is *also* an open blocking stream:
   `... script -qfc "..." /dev/null < <(sleep 300)` → killed at 20 s.
   The hang therefore needs **three** conditions, not one: (a) stdout is a tty, (b) stdin is a
   pty or an open pipe nobody writes to, (c) no usable stored/env token. `docker run -t`
   *without* `-i` does not hang; `docker run -it`, tmux and pty-shell agent wrappers do.
2. **"the flag an agent uses" is doing a lot of work.** An agent that actually wants to *parse*
   the JSON has to capture stdout — a pipe or a file — and in both cases
   `stdout_is_tty()` is False and the command exits in 0.4 s. The failing population is
   narrower: harnesses that allocate a pty for the whole shell and scrape the terminal stream.
3. **Arguably the documented split.** `output.py`'s own module docstring assigns the two jobs
   explicitly: "`--json` answers the first [parseable output] ... `--interactive` answers the
   second [nothing waits for a keystroke] by defaulting to whether stdout is a terminal", and
   `--interactive`'s help repeats it. A human at a real terminal running `--json` who is happy
   to complete the browser login is served correctly today; making `--json` imply
   `--no-interactive` outright would take that away. What is *not* met is the changelog's own
   stated goal for the breaking change — "so a pipe, a CI job or **an agent** is refused with an
   error instead of waiting at a prompt that nobody answers" — for a pty-wrapped agent.

### Mechanism (file:line on the release branch)

`packages/reflex-hosting-cli/src/reflex_cli/utils/output.py:91` —
`_resolve_interactive` is
`return stdout_is_tty() if value is None else value`, and `stdout_is_tty()`
(`output.py:61-75`) reads `sys.stdout.isatty()` and nothing else. Neither the reservation state
nor the JSON flag is consulted. The prompt itself is
`reflex_cli/utils/hosting.py:3239` (`console.ask("please hit 'Enter' or 'Return' ...")`),
reached from `get_authenticated_client` → `UnAuthenticatedClient.authenticate()` →
`authenticate_on_browser()` (`hosting.py:311-333`, `:272-279`, `:3206`).

The information needed to close the gap is already present at that exact call site:
`json_option` is `is_eager=True` and its `_reserve_stdout` callback runs first, so by the time
`_resolve_interactive` executes the reservation is set. Proved by
`verification/json_pty_interactive/order_probe.py`, which wraps `_resolve_interactive` with a spy:

```
$SB/envs/driver/bin/python pty_probe.py 10 order_probe_pty out -- $SB/envs/smoke/bin/python order_probe.py --json
# stderr: {'reserved_at_resolve': True, 'json_requested': True, 'resolved': True}
```

i.e. under a pty the resolver *knows* stdout is reserved for a JSON document and still resolves
interactive to True. A one-line change —
`return (stdout_is_tty() and not log.is_stdout_reserved()) if value is None else value` — or a
warning on stderr when `--json` resolves interactive to on, closes it while leaving an explicit
`--interactive` working for the human case.

### Refutations checked and ruled out

- **Environment quirk / proxy / network:** no. The block is `console.ask` reading stdin, before
  any network wait; `webbrowser.open` failing only produces the extra warning line. Reproduces
  identically across pty and pipe stdin.
- **Flaky:** no. 8/8 matrix cells and all 12 leaf probes were deterministic across repeats.
- **Demo/example-app bug:** n/a, this is CLI code with no app involved.
- **Pre-existing on 0.9.10.post2:** yes — and *worse* there (hangs off-tty too, and writes the
  prompt into stdout under `--json`). **Not a regression.** 0.1.72a1 fixes the cases that
  matter most to real agents and CI.
- **Downstream breakage:** none. No existing invocation that worked on 0.9.10.post2 stops
  working on 0.9.11a1; the change only converts former hangs into fast `exit 1`s.

### Severity call

LOW (claimant said medium). Not a regression, the release strictly improves the behavior, the
escape hatch (`--no-interactive`, or simply having a token) is documented in the same feature's
help text, and the remaining failure needs a pty-on-stdout + blocking-stdin + no-token
combination. Worth a follow-up issue against
`packages/reflex-hosting-cli/src/reflex_cli/utils/output.py`, not worth holding the release.

Processes started by this verification: none left running (all probe children are killed via
`killpg` on timeout; verified with `ps -eo pid,args | grep -E "reflex cloud|script -qfc|sleep 300"`
→ empty). The `reflex run` on ports 5665/10065 seen during the run belongs to another cluster
and was left alone.
