# cloud_cli — reflex-hosting-cli 0.2.1a1 / reflex-release 0.2.1a1 / reflex-build-sdk 0.1.1a1 (2026-10-23)

Everything here ran against PUBLISHED PyPI packages only, from neutral working directories, with NO Reflex
Cloud credentials and no contact with the real control plane: the CLI is pointed at a local stub
(`fake_cp.py`, in this directory) through `REFLEX_CLOUD_BACKEND_URL`.

## Setup (rerun from scratch)

```bash
SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa   # any scratch root works
cd $SB
uv --no-config venv --python 3.12 $SB/envs/cloud_cli-new
uv --no-config pip install --python $SB/envs/cloud_cli-new/bin/python --prerelease=allow 'reflex[db]==0.10.1a1' 'pydantic<2.15'
#   -> reflex 0.10.1a1, reflex-hosting-cli 0.2.1a1, reflex-build-sdk 0.1.1a1 (verified with uv pip list)
uv --no-config venv --python 3.12 $SB/envs/cloud_cli-prev
uv --no-config pip install --python $SB/envs/cloud_cli-prev/bin/python 'reflex[db]==0.10.0' 'reflex-hosting-cli==0.2.0' 'pydantic<2.15'
#   -> reflex 0.10.0, reflex-hosting-cli 0.2.0, reflex-build-sdk 0.1.0
uv --no-config venv --python 3.12 $SB/envs/cloud_cli-release-new;  uv --no-config pip install --python $SB/envs/cloud_cli-release-new/bin/python --prerelease=allow 'reflex-release==0.2.1a1'   # towncrier 26.9.0
uv --no-config venv --python 3.12 $SB/envs/cloud_cli-release-prev; uv --no-config pip install --python $SB/envs/cloud_cli-release-prev/bin/python 'reflex-release==0.2.0'                     # towncrier 25.8.0
uv --no-config venv --python 3.12 $SB/envs/cloud_cli-sdk-new;      uv --no-config pip install --python $SB/envs/cloud_cli-sdk-new/bin/python --prerelease=allow 'reflex-build-sdk[httpx]==0.1.1a1'
uv --no-config venv --python 3.12 $SB/envs/cloud_cli-sdk-prev;     uv --no-config pip install --python $SB/envs/cloud_cli-sdk-prev/bin/python 'reflex-build-sdk[httpx]==0.1.0'
```

Note on dependency resolution: the published `reflex==0.10.1a1` wheel requires `reflex-hosting-cli!=0.1.73a1,>=0.2.0`
(not `>=0.2.1a1`), so a plain `pip install reflex==0.10.1a1` (no `--pre`) resolves hosting-cli 0.2.0, not 0.2.1a1.
`--prerelease=allow` (uv) / `--pre` (pip) is needed to get the CLI under test. Expected for an alpha train; recorded here.
PyPI `info.version` for reflex-hosting-cli is 0.2.0, so the CLI's own `check_version()` (exit 1 when the installed
version is older than PyPI's latest) passes on both venvs.

Fake control plane: `fake_cp.py` (stdlib only). Start one per venv so request logs do not mix:
```bash
$SB/envs/driver/bin/python -I fake_cp.py --port 8260 --state-dir $SB/apps/cloud_cli/state       # for new
$SB/envs/driver/bin/python -I fake_cp.py --port 8261 --state-dir $SB/apps/cloud_cli/state-prev  # for prev
```
`run_cli.sh <new|prev> <label> [VAR=val ...] -- <reflex args>` resets the stub (optionally with `SCENARIO='{json}'`),
runs the venv's `reflex` with `REFLEX_CLOUD_BACKEND_URL=http://127.0.0.1:$CP_PORT$CP_PREFIX`, an isolated
`XDG_DATA_HOME` (so the real `~/.local/share/reflex/hosting_v1.json` is never touched), `REFLEX_TELEMETRY_ENABLED=false`,
and saves `logs/<label>.<venv>.{out,err,rc,requests.json}`. Every run first asserts that `reflex_cli`/`reflex` import
from the named venv.

Control-plane URL discovery (from installed source): `reflex_cli/constants/hosting.py` reads
`REFLEX_CLOUD_BACKEND_URL` (fallback `CP_BACKEND_URL`, default `https://build.reflex.dev`); the SDK (`reflex_build_sdk/_base.py`)
reads `REFLEX_BUILD_BACKEND_URL` first, then `REFLEX_CLOUD_BACKEND_URL`. Requests go to `<base>/api/v1/<path>` with
`X-API-TOKEN` and `X-Request-ID` headers. Payload shapes come from `reflex_build_sdk/types.py` (strict decoder:
unknown keys ignored, missing required keys -> APIResponseValidationError).

## Results

### #7340 `reflex cloud project list` tier column — PASS (fixed vs prev)
- `run_cli.sh new project-list REFLEX_ACCESS_TOKEN=good-token -- cloud project list --no-interactive`
- new: `tier` column shows `Pro` / `Free`. prev (0.2.0): the column shows the JSON object
  `{"name": "Pro", "cpu_quota": 4.0, ...}` wrapped over 8 lines (logs/project-list.prev.out).
- `--json`: both versions emit the full tier object `{"name","cpu_quota","ram_quota","deployment_quota"}`; byte-identical
  documents between new and prev (logs/project-list-json.*.out).

### #7390 `reflex cloud apps logs` formatting — PASS (fixed vs prev)
Stub returns 10 records (see `log_records()` in fake_cp.py): plain, with details, no optional fields, dict message,
unicode (accents/CJK/emoji/RTL), multi-line, control chars (`\x1b[31m`, `\x07`, `\r`, `\x00`, tab), rich markup +
`:rocket:`, a 20 kB line, an empty message with `log_level: null`.
- new (`logs/logs.new.out`): every record prints as `2026-10-23T12:00:10+00:00 [INFO] plain info line`; details and
  further message lines are indented by two spaces; missing/null level -> `[INFO]`; dict message -> compact JSON
  (`{"event": "structured", ...}`, non-ASCII kept); control chars printed as `\x1b`, `\x07`, `\x00` escapes; tab kept;
  rich markup printed literally (`[bold]not bold[/bold]`, `:rocket:` NOT turned into an emoji); the 20 kB line is one
  physical line (soft_wrap). Note: `\r` (and the other `str.splitlines()` separators `\x0b`, `\x0c`, `\x1c-\x1e`,
  `\x85`, U+2028/9) is not escaped but turned into an indented continuation line — harmless, recorded as observation.
- prev (`logs/logs.prev.out`): each record is `Info: {'ns': ..., 'message': ...}` Python dict repr wrapped at 80 cols,
  `:rocket:` rendered as an emoji, 20 kB line wrapped over 250 lines.
- `--loglevel error`: new still prints all 10 lines (logs/logs-lvl-error.new.out); prev prints NOTHING
  (logs/logs-lvl-error.prev.out is empty) — the bug the changelog describes, fixed.
- `--loglevel debug`: both print `Debug: Using REFLEX_ACCESS_TOKEN from environment` first, then the records.
- `--json`: identical documents new vs prev (`{"app_id","entries":[...11 fields each...],"cursor":null,"error":null}`),
  all 10 entries, dict message preserved as an object, control characters preserved verbatim.
- `--pretty true`: new prints pprint dicts without the `Info:` prefix; prev with it. Otherwise identical.

### #7434 / #7546 token rejection and validation-failure guidance — PASS (fixed vs prev)
Scenarios (`run_cli.sh`, stub scripted on `POST authenticate/me`; the stub's `detail` deliberately contains the token
string `good-token-SECRET` to check it is never echoed). Exit code 1 in every failure case on both versions; with
`--json` stdout stays empty (0 bytes) and the message goes to stderr. Request ids match the stub's `X-Request-ID`.

| case | new 0.2.1a1 message (stderr) | prev 0.2.0 message |
|---|---|---|
| whoami, env token, 401 | `The access token from the REFLEX_ACCESS_TOKEN environment variable was rejected: access denied (auth request id: …). Replace REFLEX_ACCESS_TOKEN with a valid token, or unset it and run `reflex login` to authenticate.` | same first sentence, no recovery guidance |
| whoami, `--token`, 403 | `… from the --token option was rejected: access denied (…). Replace the --token value with a valid token, or omit --token and run `reflex login` to authenticate.` | no guidance |
| whoami, stored (config file) token, 401 | `… from the config file was rejected: access denied (…). Run `reflex login` to authenticate.` — stored token NOT deleted by whoami | no guidance; not deleted either |
| `project list --no-interactive`, stored token, 401 | same message; the stored `access_token` IS removed from hosting_v1.json (`project` key kept) | same removal |
| `project list --no-interactive`, env/--token rejected while a different token is stored | stored token preserved (#7321 still holds) | same |
| whoami / project list, 429 (`Retry-After: 1`) | `Unable to validate the access token from the …: HTTP 429 (auth request id: …). Please try again later.` — 3 attempts seen by the stub (SDK retries 408/429) | whoami: `… was rejected: server error (…)` (claims rejection); project list: `Unable to validate …: server error` with no retry advice; also 3 attempts |
| 500 / 503 (503 with an HTML body) | `… HTTP 500 … Please try again later.` / `HTTP 503`, 1 attempt | `server error`, 1 attempt |
| 408 | `HTTP 408 … Please try again later.`, 3 attempts | `server error`, 3 attempts |
| 400 / 404 | `Unable to validate …: HTTP 400 (auth request id: …).` — NO retry advice (permanent) | `server error` (whoami says "rejected") |
| stored token, 500 | `HTTP 500 … Please try again later.`; stored token kept | kept |
| server closes the connection without a response | `… POST http://127.0.0.1:8260/api/v1/authenticate/me failed: Server disconnected without sending a response. (auth request id: …). Please try again later.` | whoami: "was rejected: POST … failed: Server disconnected…" |
| connection refused (port with no listener) | `… failed: [Errno 111] Connection refused (…). Please try again later.` (SDK retried twice, ~2 s) | whoami: "was rejected: … Connection refused" |
| read timeout (stub sleeps 65 s; transport read timeout is 60 s) | `… failed: timed out (auth request id: …). Please try again later.` after 61 s, 1 attempt | whoami: "was rejected: … timed out" |
| `project list --interactive`, stored token 401, stdin = newlines | `Access denied (auth request id: …)` then the browser login flow starts (prints the login URL, "Unable to automatically open the browser", prompts for Enter, polls `GET cli/token` 5 times, exits 1); stored token removed | identical |

The token string never appears in any output (grep for `SECRET` over all logs: none). Status 503 with a non-JSON body
is reported as `HTTP 503` without the body. Observation (not a bug): the "rejected" wording for 401/403 still says
`access denied`, as the changelog describes.

### reflex-build-sdk 0.1.1a1 — PASS
`sdk_api_dump.py` (run in `cloud_cli-sdk-new` / `-prev`, httpx extra only) dumps every public module's `__all__`,
dataclass fields/json names, resource methods and signatures, then diffs the two. The ONLY difference between 0.1.0
and 0.1.1a1 is the addition of `reflex_build_sdk.transports.default_transport` (`() -> 'Transport'`, listed in
`transports.__all__`, documented in the README). Probe: it returns a fresh `HttpxTransport` each call (httpx2 absent),
the same type `ReflexBuild()` picks for itself, has `send`/`close`, and a wrapper transport built on it carries a
client request end to end (the hosting CLI's `_DeploymentRetryTransport` does exactly this). `async_default_transport`
exists in `transports._defaults` but is not exported — same in 0.1.0, not a regression. `Transport` is a non
runtime-checkable Protocol in both versions (an `isinstance` check raises TypeError; recorded, pre-existing).
The installed CLI wheel diff `logs/diff-build_sdk-0.1.0-vs-0.1.1a1.txt` confirms the only source change is the export.

### reflex-release 0.2.1a1 (towncrier 26) — PASS, output identical to 0.2.0 (towncrier 25)
- `pip install reflex-release==0.2.1a1` resolves towncrier 26.9.0 (`Requires-Dist: towncrier<27,>=24.8.0`); 0.2.0
  resolves 25.8.0 (`<26`).
- Repo copy: `git -C /home/user/wt-testing archive v0.10.1a1 | tar -x -C $SB/apps/cloud_cli/repo`, `git init`, one
  commit, tag `v0.10.1a1`; `release_matrix.sh <new|prev>` then tags every package at its changelog version, adds four
  news fragments (orphan `+slug` and PR-numbered, with a fenced code block, bullets, emphasis, unicode) in a commit
  titled `QA fragments (#4242)`, and runs `detect`, `plan --action continued-prerelease`, `materialize` with
  `GITHUB_REF_NAME=r/pre-2026.10.23-40018338326`, `GITHUB_OUTPUT`, `GITHUB_STEP_SUMMARY` set.
- Read-only commands, both versions identical: `packages` (21 packages), `detect` (every package "already tagged";
  without `--ref-name` the branch reads as `''` and everything is skipped with a notice), `check-dev-pins` exits 1
  listing the two expected `.dev0` floors (`reflex: reflex-base >= 0.10.1.dev0`, `reflex-components-internal: reflex >=
  0.10.1.dev0` — the lockstep pin-exact rewrite covers the first at build time, as the published wheel's
  `reflex-base==0.10.1a1` shows), `sync --check` ("All 5 scaffolded workflows are up to date." for BOTH versions, i.e.
  the published 0.2.1a1 templates match the workflows in the tag), `check-headings`, `changelog-check`,
  `extract-notes` (byte-identical notes), `plan --action new-prerelease-patch` correctly refused ("would abandon the
  in-progress 0.2.1a1 train").
- `plan` (continued-prerelease) → `0.2.1a1 -> 0.2.1a2` for both packages; `materialize` renames the orphan fragments
  to `4242.*.md` from the commit subject, runs towncrier, stages the changelogs and deletes the fragments. The staged
  diff (`logs/release-materialize.{new,prev}.diff`), the rendered CHANGELOG.md files, towncrier's stdout and the step
  summary are byte-identical between towncrier 26.9.0 and 25.8.0. Multi-line fragment rendering (indented code block
  and bullets, link placed on its own indented line after the block) is the same on both.

### #7450 deploy archive creation — PASS (identity exclusion parity; pre-compressed sidecars now STORED)
Real `reflex deploy --no-interactive --app-id … --token good-token` against the stub (new on :8262, prev on :8263;
`logs/deploy-real.*`, archives captured by the stub's PUT handler into `archives/{new,prev}`), app = blank template +
the fixture tree in `app/README.md`, `frontend_compression_formats=["gzip","brotli"]`.
- Both versions complete the whole flow: authenticate/me → GET apps/{id} → validate_cli → apps/reserve → export →
  deployments/reserve → 2 PUTs (sizes match the reserve body) → POST deployments (form: `reflex_hosting_cli_version=
  0.1.71`, `reflex_build_sdk_version`, `stored_build_id`, `app_id`, `reflex_version`, `python_version`) → status →
  failure report → "deployment completed successfully", exit 0.
- `compare_archives.py archives/new archives/prev` (`logs/compare_archives.txt`): backend.zip 20 entries both, every
  entry DEFLATED in both (the user-supplied `assets/sub/repetitive.txt.gz` stays DEFLATED in the backend, as the PR
  says); frontend.zip 63 entries both; all 40 `.gz`/`.br` sidecars are STORED in new and DEFLATED in prev; no other
  method change; frontend.zip 1,865,948 B (new) vs 1,857,075 B (prev), +0.48 %; no `.gz.gz`/`.br.br` double sidecars.
- Exclusions honored identically (`--exclude-from-backend big_excluded --exclude-from-backend hardlink_source.py`,
  `archives/{new,prev}-excl`): `big_excluded/**` gone, the directory symlink `link_to_excluded` (same inode) gone, and
  BOTH `hardlink_source.py` and its hard-link alias `hardlink_alias.py` gone — identity-based in prev (`samefile`) too,
  so #7450 keeps behavior. Also excluded in both: `.hidden_dir`, `.env.local`, `.gitignore`, `reflex.db`, `fakevenv/`
  (has pyvenv.cfg); kept: `notvenv/keep.py`, `assets/**`, `reflex.lock/*`.
- Timing (`zip_timing.py`, 7 iterations, median, same built `.web/_static`): frontend.zip 0.085 s new vs 0.115 s prev
  (−26 %); backend.zip 42 ms vs 40 ms (noise); with two exclusions 27 ms vs 32 ms. Real deploy wall time with a warm
  `.web`: 11.9 s both.
- Pre-existing (both versions, NOT a regression): a directory symlink inside the app (`link_to_excluded -> big_excluded`)
  that is NOT excluded makes `_zip` walk it with `followlinks=True`, resolve the path back to `big_excluded/...` and
  write every file twice — Python warns `UserWarning: Duplicate name: 'big_excluded/marker.txt'` and the zip holds
  duplicate entries (`compare_archives.py` flags them). See ISSUES.
