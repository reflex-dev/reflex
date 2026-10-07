# macOS lifecycle second pass (2026-10-07)

Status: complete. Tests used only published packages in the parent's prebuilt read-only environments at `/private/tmp/reflex-prerelease-macos-pass2/envs/{alpha2,alpha,stable,driver}`. All Python execution started from neutral scratch app directories. Import guards asserted the selected environment. No framework files were edited.

Plan: adapt the previous Linux F-007 repro's non-TTY isolated process group to macOS using `subprocess.Popen(start_new_session=True)`, compare npm single-PID SIGTERM across 0.10.0a2, 0.10.0a1 and 0.9.12, then bun control. Exercise browser events, Unicode input, page reload, hot reload, production, and app directories containing spaces and non-ASCII text. Every case records server logs, process trees, reserved-port listeners, console/network/websocket evidence, and screenshots. Cleanup targets only that case's process group, with bounded TERM then KILL.

Host: macOS 26.6.2 (25G83), arm64. PATH Node v26.8.1, npm 11.19.0, bun 1.3.14. Reflex actually selects its managed Bun 1.4.0 at `/Users/masen/Library/Application Support/reflex/bun/bin/bun`, as the server system-info logs record. Exact resolved Python/package metadata is included in each JSON report. Reserved frontend ports 3660–3679 and backend ports 8660–8679.

The handwritten fixture is an initialized Python package (`__init__.py` included). `REFLEX_TEST_ENV` is passed by the harness and used only by import guards. Runtime source edits for HMR are restored at the end of the case. No framework fixes are made.

## Results

All six complete runs passed real Chromium 153.0.8010.12 events (count 0→1 and `Café 日本語 🚀` input), page reload with session state preservation, and another increment 1→2. Four HMR runs changed both the heading and backend event implementation live: the next click produced 4. There were **zero browser warnings/errors, page errors, failed requests, or HTTP 4xx/5xx responses** in the six complete captures. Screenshots were inspected; Unicode output, count, and changed heading are visible.

| Evidence stem | Version | Path / mode | HMR | Startup seconds | CLI single-PID SIGTERM |
|---|---|---|---|---|---|
| `alpha2-npm-dev-1` | 0.10.0a2 | spaces + Unicode / dev / npm | pass | 17.43 | exits 0 in 0.288 s; ports/process group empty |
| `alpha-npm-dev-1` | 0.10.0a1 | spaces + Unicode / dev / npm | pass | 11.39 | exits 0 in 0.182 s; ports/process group empty |
| `stable-npm-dev-2` | 0.9.12 | spaces + Unicode / dev / npm | pass | 8.45 | still alive after 30.001 s; node still listening on 3662 |
| `alpha2-bun-dev-1` | 0.10.0a2 | spaces + Unicode / dev / bun | pass | 4.45 | exits 0 in 0.291 s; ports/process group empty |
| `alpha2-bun-prod-1` | 0.10.0a2 | spaces + Unicode / prod / bun | n/a | 5.22 | exits 0 in 0.181 s; ports/process group empty |
| `alpha2-npm-dev-2` | 0.10.0a2 | ASCII / dev / npm | n/a | 8.36 | exits 0 in 0.178 s; ports/process group empty |

Startup times are observations, not performance comparisons: package caches warmed during the sequence, and other campaign work ran concurrently on the machine.

### F-007 conclusion

**Changed / not reproduced on this Mac with either alpha**, not a claim that the original Linux finding is fixed. The earlier Linux repro (`../2026-10-06/pymatrix_install/scripts/npm_sigterm_repro.sh`) used `setsid`, sent TERM to only the Reflex CLI, waited 30 seconds, then inspected listeners and the process group. `run_case.py` preserves that test while replacing Linux-only `setsid` and `/proc` with Python `start_new_session=True` and macOS `ps`/`lsof`. The initialized, checked-in fixture replaces `reflex init` so the same exact browser workload runs on every version.

Stable 0.9.12 remained alive/listening in 2/2 observations, one with a fully persisted JSON report. In `stable-npm-dev-2.json`, PID 9031 is the Reflex CLI, npm PID 9130 remains its child, and node PID 9150 remains npm's child listening on 3662 after the 30-second wait. The backend was stopped. The original Linux F-007 had a dead npm process and orphaned node, so that precise orphan mechanism is **not** established here. Both Mac alphas had a direct npm→node process relationship and terminated that tree. Shell/runtime/OS differences are possible explanations; this experiment did not isolate which one.

The no-HMR ASCII alpha2 repeat also exits cleanly, so the passing alpha2 result does not depend on the HMR workload or Unicode path. The relevant published alpha2 implementation is `reflex/reflex.py:466–472`, which calls `process.terminate()` on the frontend process during shutdown; this observation is source context, not proof of the platform difference's cause.

### Anomalies and methodology limitations

- Npm 11.19.0 emitted `fsevents@2.3.3` install-script approval warnings on stable and both alphas. Installs completed and macOS HMR passed. This is npm policy/runtime noise, not evidence of a Reflex regression.
- The minimal fixture emitted the expected default SitemapPlugin notice and implicit Radix Themes deprecation notice. No traceback or server error accompanied them. Bun dev shutdown logged `script "dev" exited with code 143`, followed by clean Reflex exit 0 and empty ports.
- `stable-npm-dev-1` is an exploratory run with server log and two screenshots only. After observing the 30-second shutdown failure, group TERM removed the server, then an unnecessary KILL of the now-empty/zombie process group raised macOS `EPERM` before JSON serialization. The harness now persists results before cleanup, checks the group, records cleanup errors, and verifies the final group/listeners. The complete stable rerun records a cleanup `EPERM` during the TERM/KILL race but verifies **zero remaining processes and zero listeners**. Neither error was a framework failure.
- There was a brief scheduling mistake: alpha2 bun startup overlapped the first stable run's post-SIGTERM wait, using separate reserved ports. The stable rerun was serial and reproduced the result. Other campaign items were also active, so no system-wide performance claim is made.
- Production tested alpha2/bun only. No Safari/WebKit, Intel macOS, alternate Node/npm versions, IPv6-only networking, Redis, TTY SIGINT, or frontend-only mode was tested. Linux F-007 remains outside this Mac result's scope.

## Reproduce from a clean scratch directory

The four `requirements-*.txt` files freeze the actual installed Python distributions, including all train sibling packages. Their exact versions also appear in each JSON's `metadata`. These commands create separate environments from PyPI; they do not install the checkout. Run from a neutral directory, never the checkout. Choose a **new** scratch root for each complete run: the harness intentionally refuses to overwrite an existing app directory.

```bash
REPO=/Users/masen/.codex/worktrees/3564/reflex
ART="$REPO/prerelease_testing/2026-10-07/macos_lifecycle"
SB=/private/tmp/reflex-macos-lifecycle-rerun
mkdir -p "$SB"
cd "$SB"
export UV_CACHE_DIR="$SB/uv-cache"
for envname in alpha2 alpha stable driver; do
  uv --no-config venv --python 3.12 "$SB/envs/$envname"
  uv --no-config pip install --index-url https://pypi.org/simple --prerelease=allow \
    --python "$SB/envs/$envname/bin/python" -r "$ART/requirements-$envname.txt"
done
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" \
  python -m playwright install chromium
run_case() {
  uv --no-config run --no-project --python "$SB/envs/driver/bin/python" \
    python "$ART/run_case.py" --sb "$SB" --out "$SB/results" "$@"
}
run_case --env alpha2 --manager npm --port 3660 --backend-port 8660 --unicode-path --hmr
run_case --env alpha --manager npm --port 3661 --backend-port 8661 --unicode-path --hmr
run_case --env stable --manager npm --port 3662 --backend-port 8662 --unicode-path --hmr --attempt 2
run_case --env alpha2 --manager bun --port 3663 --backend-port 8663 --unicode-path --hmr
run_case --env alpha2 --manager bun --port 3664 --backend-port 3664 --unicode-path --prod
run_case --env alpha2 --manager npm --port 3665 --backend-port 8665 --attempt 2
```

The tested host resolves PATH `node`, `npm`, and `bun` from `/opt/homebrew/bin`, but Reflex's selected Bun is the managed 1.4.0 above. Match Node v26.8.1, npm 11.19.0, managed Bun 1.4.0, and Python 3.12.14 for a close replication. Browser runtime downloads come from Playwright. The harness uses direct venv executables for subprocesses after the outer `uv run`; every import probe and app module asserts the selected published-package environment. It uses a proxy-free localhost HTTP opener, strips client-only `NO_PROXY` settings from the server environment, and sets `REFLEX_TELEMETRY_ENABLED=false` on every Reflex invocation. In sandboxed Codex, localhost/process/browser operations required authorized escalated execution; sandbox-only probes cannot be used to infer server failure.

## Evidence and cleanup

Each `evidence/<stem>.json` contains exact package/runtime metadata, command, app path, Chromium version, browser console/network/websocket captures, process trees before/after single-PID TERM, listener snapshots, and final cleanup verification. Each matching `.server.log` is the complete debug server log. `*-events.png` shows the first interaction; `*-hmr.png` shows the live changed UI and count 4. Websocket payloads are bounded to 1,600 characters and 120 frames per case.

All six complete JSON reports have empty `after_cleanup` and `listeners_after_cleanup`. The final independent `ps`/`lsof` check at `2026-10-07 07:05:30 UTC` found no process whose command contains `/apps/macos_lifecycle/` and no listener on reserved ports 3660–3679/8660–8679 (`evidence/final-cleanup.txt`; empty match output, lsof exit 1). Chromium was closed in each browser `finally` block and Playwright's context exited. No server or browser started by this item is intentionally left running.

## VERIFICATION — independent F-007 reproduction

A second agent read this document and ran the unmodified `run_case.py` sequentially
on stable and alpha2, on frontend 3668/backend 8668, with `--manager npm
--unicode-path` and **without HMR**. The same read-only published environments and
host runtimes were used. `--attempt independent` created fresh app directories
without overwriting the original explorer's experiments. No server remained
between the two cases.

| Evidence under `verification/` | CLI SIGTERM observation | Browser / cleanup |
| --- | --- | --- |
| `stable-npm-dev-independent.json` | Alive after 30.012 seconds; CLI PID 13815, npm PID 13912, child node PID 13932; node still listening on 3668 | Events, Unicode input, reload pass; final group/listeners empty |
| `alpha2-npm-dev-independent.json` | Exit 0 in 0.189 seconds; group and listeners empty immediately after wait | Events, Unicode input, reload pass; final group/listeners empty |

Both browser captures have zero console warnings/errors, page errors, failed
requests, or HTTP errors. Screenshots confirm the Unicode state update. Stable's
backend log does contain the nonfatal warning `Error transforming event payload
for handler State.rename`, referring to the Unicode string and its `str` type
annotation; the value nevertheless reaches state and renders correctly. The same
warning is present in the original explorer's two stable logs and absent in the
independent alpha2 log. It does not explain away the observed process tree.

Stable cleanup again records an `EPERM` during the process-group TERM/KILL race;
the persisted final process/listener checks are empty. This occurs after the
30-second shutdown observation. A final external `ps`/`lsof` audit also found no
owned independent-case process or listener on 3668/8668.

Verdict: **corroborated on this Mac**. HMR is not required to reproduce stable's
hang or alpha2's clean exit. Stable retains a live npm parent and node child; this
does not verify the earlier Linux dead-npm/orphaned-node mechanism, nor establish
a Linux fix. The evidence supports the report's `changed` classification rather
than a cross-platform fixed claim.

Exact commands, run from `/private/tmp`, using the existing environments:

```sh
ART=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/macos_lifecycle
SB=/private/tmp/reflex-prerelease-macos-pass2
export UV_CACHE_DIR="$SB/uv-cache"
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run_case.py" --sb "$SB" --out "$ART/verification" --env stable --manager npm --port 3668 --backend-port 8668 --unicode-path --attempt independent
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run_case.py" --sb "$SB" --out "$ART/verification" --env alpha2 --manager npm --port 3668 --backend-port 8668 --unicode-path --attempt independent
```

For another run, select a new attempt suffix or fresh scratch root because the
harness deliberately rejects existing app paths. This verification did not rerun
alpha1, production, HMR, or Linux.

## Harness exit-policy validation

After review strengthened the runner's exit status, two additional serial npm/ASCII/no-HMR runs on 3667/8667 confirmed the shell status: stable returned **1** after its CLI/frontend remained alive for 30.009 seconds; alpha2 returned **0** after clean shutdown in 0.198 seconds. Browser events, Unicode input, and reload passed in both. Compact evidence is in `exitpolicy/`; full JSON, server logs, and screenshots remain at `/private/tmp/reflex-prerelease-macos-pass2/results/lifecycle-exitpolicy/`. `observed_harness_exitcode` records the actual outer command result; compact copies omit only websocket frames.

The final predicate also rejects post-SIGTERM process-group survivors or listeners, even if forced cleanup eventually succeeds. That addition landed while stable was running: stable exercised the preceding predicate, whose CLI-still-alive condition already returns 1, and alpha2 exercised the final predicate. Both recorded post-SIGTERM states support the same results under the final policy. Final cleanup for both was empty; an independent `ps`/`lsof` audit at 2026-10-07 07:19:54 UTC found no members of groups 17015/17196 and no listeners on 3667/8667. Stable retained the previously documented nonfatal rename warning and cleanup EPERM race.

Commands, from neutral scratch cwd with existing isolated environments:

```sh
SB=/private/tmp/reflex-prerelease-macos-pass2
ART=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/macos_lifecycle
cd "$SB"
export UV_CACHE_DIR="$SB/uv-cache"
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run_case.py" --sb "$SB" --env stable --manager npm --port 3667 --backend-port 8667 --out "$SB/results/lifecycle-exitpolicy" --attempt exitpolicy
# Expected exit 1; then run the next command explicitly (do not join with &&).
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run_case.py" --sb "$SB" --env alpha2 --manager npm --port 3667 --backend-port 8667 --out "$SB/results/lifecycle-exitpolicy" --attempt exitpolicy
```

For a new replay, change the attempt suffix or use a fresh scratch root.
