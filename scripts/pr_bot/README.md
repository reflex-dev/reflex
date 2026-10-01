# PR bot

Automation that keeps open pull requests from getting lost. Four workflows, all
driven by `python -m scripts.pr_bot`:

| Workflow | What it does |
| --- | --- |
| `pr_triage.yml` | Labels every open pull request with whose turn it is and how complex it is, and keeps one comment explaining both. |
| `pr_review_relay.yml` | Relays reviews on fork pull requests to `pr-triage` (see [Triggers](#triggers)). |
| `pr_overlap.yml` | When a pull request opens, finds open pull requests it conflicts with or that solve the same problem. |
| `pr_on_deck.yml` | Merges `main` into pull requests labeled `on deck` whenever they conflict, with Claude resolving the conflicts. |

## Status

Each open pull request carries exactly one of these labels; the bot recomputes it
on every event and overwrites a hand-set one. The rules are in
[`status.py`](status.py) and read only GitHub's own records, so a pull request
always gets the same answer.

- **`status: waiting on submitter`**: the next move is plainly the author's. Any of:
  - it is a draft;
  - it has merge conflicts with its base branch;
  - a required check fails (the checks in
    [`main-required-checks.json`](../../.github/rulesets/main-required-checks.json));
  - a reviewer requested changes and the author has not pushed or replied since;
  - an unresolved review thread on current code has a last comment by someone else,
    newer than the author's last commit. AI reviewers' threads (Greptile, cubic)
    count like people's;
  - a maintainer's comment since the author's last move asks them for something.
    Claude reads those comments, because "thanks, looking now" and "please add a
    test" look the same to a rule.
- **`status: ready to merge`**: approved, every required check passed, no
  conflicts, no commits since the latest approval, no thread the author replied
  to after it, and GitHub itself would allow the merge.
- **`status: waiting on maintainer`**: everything else: it needs a first review, a
  re-review after the author responded, a look at new commits, or required checks
  are still running.

"The author's last move" is their latest non-merge commit, comment, review or
thread reply. Merging `main` in is not new work, so it neither answers feedback
nor needs re-review.

## Complexity

Claude reads the description, file list and diff (lockfiles and generated stubs
left out, about 150 KB at most) and labels the pull request `complexity: low`,
`medium` or `high`, by what a careful reviewer has to understand rather than by
line count. The estimate is made once, when the pull request is ready for review,
and again only if it at least doubles in size. To overrule it, set a different
`complexity:` label; the bot leaves labels it did not set alone. To get a fresh
estimate, remove the label.

## The triage comment

One comment per pull request (drafts get none) lists the reasons behind the status
and the complexity rationale. The bot edits it in place, which notifies nobody,
and keeps its own state in a hidden part of it: the complexity estimate and
Claude's reading of maintainers' comments, so neither is paid for twice.

## Overlap

When a pull request opens, reopens or leaves draft, the bot compares it with
every open pull request into the same base branch, except the author's own and
the ones it already links to:

- **conflicts**: both are merged onto the base branch in memory and then into each
  other, so a conflict is between the two changes rather than with drift on the
  base branch (lockfiles and stubs don't count);
- **linked issues**: both close or mention the same issue;
- **purpose**: Claude compares the descriptions and the new diff with the other
  open pull requests and reports duplicates, alternative fixes for the same
  problem, and changes that interact.

It comments only when it finds something. Mentioning the other pull requests
links them back, so their authors see it too.

## On deck

Label a pull request `on deck` to keep it mergeable. Whenever `main` moves (and
when the label is added, and every six hours), the bot checks each on-deck pull
request; for each one that conflicts it:

1. merges `main` into the pull request's head in a scratch worktree;
2. has Claude Code resolve the conflicted files, with both sides' diffs and the
   pull request's description as context;
3. checks the result has no conflict markers and changes nothing but the
   conflicted files, against a merge it computes again in a separate job;
4. pushes the merge commit to the pull request's branch as the GitHub App, so CI
   runs on it, and comments with how each file was resolved.

Until the merge lands, a conflicting on-deck pull request shows as waiting on its
submitter, like any other conflicting pull request.

If Claude can't resolve a conflict with confidence (incompatible designs, binary
files, a file one side deleted), the bot says so on the pull request and waits:
it tries again after the next push to the branch, or when someone re-adds the
label or runs the workflow for that pull request. Pull requests from forks need
"Allow edits by maintainers" for the bot to push.

The bot resolves textual conflicts only. It does not run the pull request's code,
so `pyi_hashes.json` and `uv.lock` conflicts are merged by content, and CI says
when they need regenerating.

## Setup

1. **Anthropic API key**: add a repository secret `ANTHROPIC_API_KEY`. Without
   it, triage still labels status but skips complexity and comment reading, and
   overlap skips the comparison by purpose.
2. **GitHub App** for on deck: create an app (no webhook) with these repository
   permissions, install it on this repository only, and add its client ID as the
   variable `PR_BOT_CLIENT_ID` and a private key as the secret
   `PR_BOT_PRIVATE_KEY`.
   - Contents: read and write (push the merge)
   - Pull requests: read and write
   - Issues: read and write (comments)
   - Workflows: read and write (a merge from `main` can carry workflow changes)

   `GITHUB_TOKEN` won't do: its pushes start no workflows, so CI would never run on
   the merge, and it cannot push to forks.
3. Optional variables: `PR_BOT_MODEL` (default `claude-opus-5-5`; also takes
   `claude-sonnet-5-5`) and `PR_BOT_RESOLVE_BUDGET_USD` (default `10`, the most
   one conflict resolution may spend).

The labels are created on first use.

## Triggers

`pr-triage` runs on pull request events, on comments, after reviews, and every 30
minutes over all open pull requests. Review events on fork pull requests only get
a read-only token, so `pr-review-relay` does nothing but finish, and `pr-triage`
listens for that with `workflow_run`, which runs with this repository's token.
The sweep covers what no event reports, such as CI finishing or a thread being
resolved.

## Security

All of these workflows run in this repository's context, with secrets, on pull
requests from anyone, so none of them checks out pull request code to run it:

- triage and overlap read pull requests through the API and handle commits only
  with `git merge-tree` and `git commit-tree`, which run nothing;
- Claude's answers are data: status labels come from the rules, complexity and
  overlap answers must be values from a fixed list, and text Claude writes into a
  comment is flattened to plain text that cannot mention anyone or embed HTML;
- the on-deck resolve job holds the Anthropic key but no write access. Claude
  Code runs with `--bare` (nothing from the pull request's `.claude/` or
  `CLAUDE.md` is loaded) and `--restricted` with only file tools, confined to the
  worktree;
- the on-deck push job holds the app token but runs no pull request code and no
  model. It accepts the merge only if it differs from its own merge in nothing
  but the conflicted files.

## Cost

Claude is asked only when there is something new to judge: one complexity
estimate per pull request (again if it doubles), one comparison per opened pull
request, and one short reading of each maintainer comment that lands after the
author's last move. Answers are kept in the triage comment, so the half-hourly
sweep repeats none of them. A conflict resolution is capped at
`PR_BOT_RESOLVE_BUDGET_USD`, and one Claude could not finish is not retried until
the branch changes.

## Running it locally

```bash
export GITHUB_TOKEN=... GITHUB_REPOSITORY=reflex-dev/reflex ANTHROPIC_API_KEY=...
uv run python -m scripts.pr_bot triage --pr 1234 --dry-run
uv run python -m scripts.pr_bot overlap --pr 1234 --dry-run
```

`--dry-run` prints what would change and changes nothing (Claude is still asked).
The triage, overlap and on-deck workflows can also be run by hand, with the same
option.
