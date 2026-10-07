# Published tooling CLI/SDK verification

Completed on macOS 26.6.2 arm64, Python 3.12.14, using fresh task-owned PyPI
environments. Final results: **41 hosting CLI/SDK cases, 11 release/docgen cases,
and 10 old/new release comparisons pass**. No new package defect was found in
these contracts. `report.json` is the compact structured result.

The independent final review reproduced counts from raw records and checked source/workflow provenance. Parent Ruff formatting afterward preserved all seven tested source ASTs (`parent-format-review.json`); exact executed bytes remain in `tested-source.json.gz`. No package command was rerun merely for formatting.

The tested graph includes Reflex/base/docgen 0.10.0a2, hosting CLI 0.2.0a1,
build SDK 0.1.0a1, and release 0.2.0a1. The release comparison separately installs
the prior campaign's published release 0.1.2a1. Complete inventories are
`freeze-a2.txt` and `freeze-release-old.txt`. No shared environment was changed.

## Coverage and observations

The owned HTTP fixture binds only `127.0.0.1:8580`. Before the full sweep,
`preflight-a2.json` checked a fixture health marker, actual SDK authentication,
the SDK base URL, a public CLI start command, and rejection of a nonlocal socket
before connection. Final-run request records capture the actual SDK
`X-API-TOKEN` header, not just the unused standard Authorization header. They
assert explicit SDK tokens, CLI environment-token precedence, and redirected
stored-token fallback. Missing SDK credentials fail before any HTTP request.

`REFLEX_DIR` and both hosting credential constants point inside each disposable
fixture before the public CLI import. An audit hook rejects nonfixture credential
file opens and all socket connections except the owned fixture port. HOME is never
overridden. All recorded tokens and secret values are synthetic fixture strings;
the user credential files are never opened. Stored fixture credentials remain
unchanged after commands.

The final hosting sweep (`hosting-a2-run3.json`) contains 66 recorded local
requests and complete command argv, stdout, stderr, exit status, JSON output,
request bodies, and fixture responses. It covers:

- Start/stop JSON and refusal exits; missing deletion remains structured
  `deleted:false` with a nonzero exit. Regions and VM types reach their actual
  listing endpoints and fail on 403.
- Initial and post-authentication 401 behavior, environment/stored-token
  precedence, preserved credentials, and missing SDK credentials.
- Full, nullable, and empty history; inspect UUIDs and nested wire aliases;
  server-selected token names/expiry; invalid duration rejected before HTTP.
- Secret update JSON contains only sorted names; empty values and embedded `=`
  survive; an envfile overrides CLI values and omits bare keys. Neither debug nor
  human output contains fixture secret values. Null permissions become `[]`.
- CLI, synchronous SDK, and asynchronous SDK pagination. A cursor containing
  spaces, `+`, `/`, `=`, `?`, and `&` round-trips intact; Unicode search text is
  encoded correctly. An empty page terminates CLI pagination despite a cursor.
- Typed SDK errors for 400/401/403/404/409/422/429/500, with retries disabled;
  malformed JSON and model responses raise `APIResponseValidationError`.

All stdout/stderr streams were inspected. Successful JSON commands emit clean
JSON; expected errors remain nonzero with the documented output distinctions.
The neutral `uv --no-project` notice, explicit debug token-source notice, and
intentional envfile override warning remain visible in the raw records.

Initial rejected authentication still omits the `reflex login` hint, whereas a
401 after successful authentication includes it. This matches the prior
hosting CLI 0.1.73a1 evidence, copied with its provenance into
`prior-auth-baseline.json`. This is the already recorded guidance gap, not a new
regression; the old hosting package was not reinstalled in this sweep.

## Release workflows and docgen

`release-docgen-a2-run2.json` records real `init`, `sync`, and `sync --check`
commands for 19, 20, 24, and 25 packages. Parsed workflow inputs remain within
GitHub's limit; per-package booleans switch to text at 25 packages. Deliberate
generated-file drift makes `sync --check` fail, and `sync` repairs it. Eight actual
generated workflow YAML files are retained under `generated-workflows/`.

The lockstep fixture checks generated publish-last dependencies and its explicit
`always()`/successful-detect/success-or-skipped-publish condition. Actual `detect`
commands check both members due, only the late member due after the early tag,
independent early releases, and a late member whose matching early version does
not exist. `pin-lockstep` writes an exact sibling requirement. An all-members
publish-last configuration is rejected.

The independent old/new comparison in `release-direction-baseline.json` verifies
the intended #7464 directionality: release 0.1.2a1 rejects an early member at
1.1.0 while the late member remains at 1.0.0; 0.2.0a1 accepts it. Both versions
accept a late member whose matching early tag already exists. Both reject an
unmet late-member dependency and a mismatched symmetric group without
publish-last. These commands use disposable local Git repositories with empty
fixture commits and tags, no remotes. They do not execute generated Actions,
upload distributions, publish, or push anything.

Five docgen variants combine ordinary LF, UTF-8 BOM, leading spaces/tabs/blank
lines, and CRLF. Unicode metadata is extracted while headings, inline `---`, and
YAML-looking fenced code remain body content. A negative control with a body
heading before a YAML-looking block correctly has no frontmatter.

## Retained harness corrections

- The first venv attempt omitted `UV_CACHE_DIR`; uv refused the inaccessible
  default cache. The retry used the task scratch cache. `bootstrap-errors.txt`
  retains the error description; no package test ran in that failed attempt.
- `release-docgen-a2-run1.json` retains two failed assertions. The release oracle
  initially assumed symmetric lockstep rules for an early publish-last member;
  the published #7464 behavior is intentionally directional. The docgen negative
  oracle initially dereferenced optional frontmatter when it was correctly None.
  Only the harness changed. The corrected second run and old-version comparison
  pass.
- Hosting runs 1 and 2 passed. The final run strengthens start/stop/log JSON
  assertions, records the real `X-API-TOKEN` header, and adds stored-token and
  missing-token checks. Earlier raw records are retained, not substituted.

## Exact replay

Use a new scratch path; release fixture directories must not already exist. The
tooling environment names below are required by the import guards. All packages
come from PyPI. The commands need permission to bind the local fixture port, which
must be free. They do not need credentials or a cloud account.

```sh
export ART=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/tooling_a2/cli
export SB=/private/tmp/reflex-tooling-cli-replay
export UV_CACHE_DIR="$SB/uv-cache"
mkdir -p "$SB/envs" "$SB/results"
cd "$SB"
uv --no-config venv --python 3.12.14 "$SB/envs/tooling-cli-a2"
uv --no-config pip sync --python "$SB/envs/tooling-cli-a2/bin/python" --prerelease=allow "$ART/freeze-a2.txt"
uv --no-config venv --python 3.12.14 "$SB/envs/tooling-cli-release-old"
uv --no-config pip sync --python "$SB/envs/tooling-cli-release-old/bin/python" --prerelease=allow "$ART/freeze-release-old.txt"
uv --no-config run --no-project --python "$SB/envs/tooling-cli-a2/bin/python" python "$ART/hosting.py" --scratch "$SB/preflight" --output "$SB/results/preflight.json" --preflight-only
uv --no-config run --no-project --python "$SB/envs/tooling-cli-a2/bin/python" python "$ART/hosting.py" --scratch "$SB/hosting" --output "$SB/results/hosting.json"
uv --no-config run --no-project --python "$SB/envs/tooling-cli-a2/bin/python" python "$ART/release_docgen.py" --scratch "$SB/release-docgen" --output "$SB/results/release-docgen.json"
uv --no-config run --no-project --python "$SB/envs/tooling-cli-a2/bin/python" python "$ART/release_baseline.py" --sb "$SB" --scratch "$SB/release-baseline" --output "$SB/results/release-baseline.json"
```

`fixtures.py` reuses realistic wire models and assertions from the 2026-10-05
hosting campaign; `prior-cases.json` retains its 15 nondeployment command cases.
The two old project deploy-refusal cases were not rerun. No `deploy` command is
invoked. SDK retry/backoff, streaming watches, real cloud authorization policy,
actual hosted deployment, and GitHub Actions execution remain outside this sweep.
Every fixture server closes in `finally`; `cleanup.json` records the final port
and process audit. No framework source, shared board, or checkout Git was changed.
