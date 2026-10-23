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
