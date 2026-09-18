# Required status checks

`main-required-checks.json` is the ruleset that makes CI block a merge. Import it
under **Settings → Rules → Rulesets → New ruleset → Import a ruleset**, or push it
with `POST /repos/reflex-dev/reflex/rulesets`. It carries only the
`required_status_checks` rule, so it sits alongside whatever else already guards
the branch instead of replacing it.

## Why the list is what it is

A required status check is matched by check-run name, literally — no wildcards,
no conditionals. That rules out naming CI jobs directly:

- **A path-filtered workflow never reports.** `on.paths`/`on.paths-ignore` skip
  the whole run, and a required check that never reports leaves the pull request
  on *"Expected — Waiting for status to be reported"* forever. A job skipped by
  `if:` is the opposite: it reports `skipped`, which counts as a pass.
- **Matrix job names move.** `unit-tests` alone expands to 12 check names, and
  `check-min-deps`' matrix is discovered at run time from `packages/*/`, so the
  names change whenever a package is added.

So each workflow ends in a `*-gate` job that always runs, depends on every other
job in the workflow, and fails unless each of them ended in `success` or
`skipped` (`.github/actions/ci_gate`). The gate name is fixed, and it is the only
name from that workflow in the list. The three workflows with a single job whose
name cannot drift — `pre-commit`, `dependency-review`, `changelog` — are required
directly.

The path filters those workflows used to carry on their `pull_request` trigger
now sit on a `changes` job instead (`.github/actions/changed_paths`), which
evaluates the same patterns against the pull request's files. `push` triggers
keep their filters: nothing gates a merge there.

`integration_id: 15368` pins each context to the GitHub Actions app, so another
integration cannot satisfy a required check by posting a same-named one.

## Adding a workflow

A new workflow that should block merges needs a gate job, and its name added
here. See the CI section of `CLAUDE.md` for the job to copy.

## Deliberate omissions

- **The ruleset targets `~DEFAULT_BRANCH` only.** Most of these workflows trigger
  on `pull_request: branches: ["main"]`, so requiring them on `r/pre-**` or
  `r/hotfix/**` would reintroduce exactly the never-reports deadlock this
  replaces. Only `changelog` runs on the release branches.
- **`CodSpeed Performance Analysis`** is posted by the CodSpeed app
  (`integration_id: 257293`), not by Actions, and is advisory. Add it as its own
  context if it should start blocking merges.
- **`strict_required_status_checks_policy` is `false`.** Turning it on requires
  every pull request to be up to date with `main` before merging, which on a repo
  this busy means a re-run of the whole suite per merge.
