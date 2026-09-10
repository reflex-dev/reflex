# Reporting

## FINDINGS.md

The audience is a maintainer deciding what blocks the release, and fix agents who will get handed
one finding and nothing else. Write for both: a summary that supports a go/no-go call, and findings
self-contained enough to act on in isolation.

```markdown
# Findings — reflex <version> pre-release testing (<date>)

<One paragraph on method: PyPI-only isolated venvs, end-to-end browser runs, previous-stable
baselines, independent adversarial verification of every claimed issue. Agent count.>

## Versions under test
<Every package and version, noting which are new in this train and that each is published.>
<Environment: OS, CPU/RAM, node/bun, python versions, browser.>

## Executive summary
<What works — name the headline changelog items verified.>
<What blocks — the short list, with severity.>
<Severity histogram, and the count of refuted claims.>

Index:
- FINDING-001: <title> (SEVERITY)
- ...

## FINDING-00N: <title> (SEVERITY)

- Cluster: `<cluster>` | Regression vs <prev stable>: yes/no | Verifier: CONFIRMED
- Repro: <exact commands/steps, self-contained>
- Evidence: <log excerpt, console error, screenshot path>
- Root cause (verifier analysis): <file:line and mechanism, when known>
- Verification notes: <what the independent reproducer found>

## Refuted / reclassified claims
- **<title>** (`<cluster>`): <why it is not an actionable defect for this release>

## Cluster summaries
### `<cluster>` (pass:N, anomaly:N, fail:N)
<2-4 sentences: what was built, what was verified, what was found.>
```

Two things carry disproportionate weight and are easy to skip:

- **The refuted list.** It shows the findings were filtered, which is why a maintainer can trust the
  ones that remain. Never quietly drop a refuted claim.
- **Regression status on every finding.** "Broken in both versions" and "newly broken" lead to
  opposite decisions, and the reader cannot recover that from the description.

## RELEASE_PLAN.md

```markdown
# Release plan — what blocks <version> vs what gets filed

## Already in flight
| PR | Covers | Gap check |
<For each open PR, which findings it addresses and — importantly — what it does NOT cover.>

## Fix before release
### Security
### Confirmed regressions
### High impact and/or trivially small
<Each item: finding ref, one-line rationale tied to the rubric, and the shape of the fix.>

## File as issues, fix after release
### <this repo>
### <downstream repo>

## Decisions needed from a maintainer
<Behavior changes that are either bugs or missing changelog entries — their call, not yours.>

## Suggested sequencing
<Order of PRs, noting which can land in parallel and which touch the same files.>
```

The rubric (confirmed regression / security / significant-impact-or-trivial) is in `SKILL.md`.
Apply it visibly: each entry should say which arm of the rubric put it there, so the maintainer can
disagree with a specific judgment rather than the whole list.

## Filing issues

For post-release items: search for duplicates first (2–3 keyword variants, open *and* closed), then
file with a self-contained repro, observed vs expected, environment, a note that it came from
`<version>` pre-release testing, and a pointer to the artifacts branch and cluster directory.
Mirror `.github/ISSUE_TEMPLATE/bug_report.md` where it fits.

## If the user asks for the fixes afterwards

That is a separate engagement. What worked well:

- **One PR per finding**, branched from current `main`, in its own git worktree so parallel fix
  agents never collide.
- **Regression test first**: write it, show it failing against unfixed `main`, then fix, then show
  it passing. Report both states in the PR body — a reviewer should not have to take it on faith.
- **News fragment** under the right package's `news/` directory. The changelog CI gate checks per
  package: a fix touching `packages/reflex-base/` needs a fragment in
  `packages/reflex-base/news/`, and a root-only fragment will fail the gate.
- **Adversarial review of each PR** before handing it over: an independent agent re-runs the
  regression test against unfixed source to confirm it actually pins the bug, and checks repo
  conventions. This catches PRs whose test passes either way.
- PR body: cite the FINDING number and that it came from pre-release testing, describe the defect
  mechanism, the fix, and the test plan including the failing-before evidence.
- Watch CI after opening (`subscribe_pr_activity`) and drive each PR to green.
