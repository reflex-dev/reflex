# Required status checks

`main-required-checks.json` is the ruleset that makes CI block a merge. Import it
under **Settings → Rules → Rulesets → New ruleset → Import a ruleset**, or push it
with `POST /repos/reflex-dev/reflex/rulesets`. It carries only the
`required_status_checks` rule: pull request reviews, linear history and the rest
stay where they are. The required checks themselves belong here and nowhere else
— see [Moving off branch protection](#moving-off-branch-protection).

## Why the list is what it is

A required status check is matched by check-run name, literally — no wildcards,
no conditionals. That rules out naming CI jobs directly:

- **A path-filtered workflow never reports.** `on.paths`/`on.paths-ignore` skip
  the whole run, and a required check that never reports leaves the pull request
  on *"Expected — Waiting for status to be reported"* forever. A job skipped by
  `if:` is the opposite: it reports `skipped`, which counts as a pass.
- **Matrix job names move.** `unit-tests` alone expands to 12 check names, and
  `build` and `check-min-deps` discover their matrices at run time from
  `packages/*/`, so their names change whenever a package is added. That is how
  `build (reflex-build-sdk, …)` and `build (reflex-otel, …)` went missing from
  the hand-kept list this replaces.

So each required workflow ends in a `*-gate` job that always runs, depends on
every other job in the workflow, and fails unless each of them ended in `success`
or `skipped` (`.github/actions/ci_gate`). The gate name is fixed, and it is the
only name from that workflow in the list. The three workflows with a single job
whose name cannot drift — `pre-commit`, `dependency-review`, `changelog` — are
required directly.

The path filters those workflows used to carry on their `pull_request` trigger
now sit on a `changes` job instead (`.github/actions/changed_paths`), which
evaluates the same patterns against the pull request's files — both names of a
renamed file, so a code file renamed to `*.md` still runs the tests. `push`
triggers keep their filters: nothing gates a merge there.

Each context is pinned to the app that posts it, so no other integration can
satisfy it with a same-named check: `15368` is GitHub Actions. `Greptile Review`
(`867647`) and `cubic · AI code reviewer` (`1082092`) are required by name,
because no gate can cover another app's check; both were required before this
ruleset and stay so.

## Moving off branch protection

Until this ruleset, the required checks lived in the classic branch protection
rule for `main`: 69 names, most of them one per matrix leg. Both lists apply at
once, so any name left there still has to report — and a matrix job that `if:`
skips reports a single check under its bare job name, not one per leg. A
leftover `unit-tests (ubuntu-latest, 3.10)` therefore brings the Markdown-only
deadlock straight back. In order:

1. Merge the change that adds the gate jobs. Pull request runs use the workflows
   of their merge with `main`, so until `main` has the gates no run reports them,
   and requiring them any earlier blocks every open pull request.
2. Import this ruleset. With both lists active, a pull request that changes code
   satisfies both, so nothing loosens in between.
3. Remove every required status check from the classic `main` rule, leaving its
   other settings alone. This is the step that unblocks Markdown-only pull
   requests.

An open pull request whose checks last ran before step 1 needs one new push, or
`main` merged in, before its gates report. Re-running its old checks is not
enough: a re-run replays the merge commit it started from.

## Adding a workflow

A new workflow that should block merges needs a gate job, and its name added
here. See the CI section of `CLAUDE.md` for the job to copy.

## Deliberate omissions

- **Python 3.15 legs** run under `continue-on-error`. It is a pre-release and its
  legs were never required; a failed `continue-on-error` leg counts as a success
  in the gate's `needs`, so they report without blocking. Drop the
  `continue-on-error` once 3.15 is final.
- **`docs whitelist check` is advisory.** It keeps its trigger-level `paths`
  filter and blocks no merge, which is the trade the filter ban exists to force:
  a workflow either reports on every pull request and can be required, or filters
  its trigger and cannot. Requiring it would mean spending a `changes` job and a
  gate job on every pull request in the repo to guard one assertion.
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
