# Fix brief — reflex 0.9.12a1 release blockers (shared rules for every fix agent)

You are one of five parallel fix agents. Each agent owns exactly one finding from the 0.9.12a1 pre-release
campaign and works in its own git worktree. Read this file first, then your per-finding brief.

## Where things are

- Campaign artifacts (READ-ONLY for you): `/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/`
  - `FINDINGS.md` — read ONLY the section for your finding (`grep -n "## FINDING-NNN"`) and its index line.
  - `RELEASE_PLAN.md` — the "Fix before release" entry for your finding.
  - The cluster directory named in your brief: `NOTES.md` (incl. its `## VERIFICATION` appendix), `scripts/`,
    `verification/`, sample apps.
- Your worktree: `/home/user/wt/<name>` (given in your brief), already checked out on your branch, created from
  `origin/main`, with `uv sync` done (`.venv/`). It is a git worktree of `/home/user/reflex` — treat
  `/home/user/reflex` itself as READ-ONLY: never run git commands there, never edit files there, never touch the
  other worktrees under `/home/user/wt/`.
- Scratch space: `/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad/fixes/<name>/`
  (create it) for copies of sample apps, edited copies of campaign scripts, logs, throwaway venvs.
- Helper: `uv run --no-project python /tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad/bin/ports.py`
  lists listening ports → pids → cmdline (there is no `ss` in this container).
- Read-only venvs you may RUN but must never install into:
  - previous stable, reflex 0.9.11.post1: `/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad/envs/prev`
  - published alphas, reflex 0.9.12a1 + component alphas: `.../scratchpad/envs/shared`
  - Playwright driver (playwright 1.63, httpx, websockets; Chromium at `/opt/pw-browsers/chromium`): `.../scratchpad/envs/driver`
  - reflex-enterprise 0.9.5 offline wheel: `.../scratchpad/wheels/reflex_enterprise-0.9.5-py3-none-any.whl`
- Ports: use ONLY the range in your brief. Kill servers by pid (the pid you started, or from `ports.py`);
  NEVER `pkill -f "reflex run"` or any other pattern kill — other agents run servers on this box.
- Every server you start: `REFLEX_TELEMETRY_ENABLED=false`. Clients talking to localhost: `NO_PROXY=localhost,127.0.0.1`.
  Foreground `sleep` is blocked in this harness — poll with `python -c` / `until` loops, not `sleep`.
- Never run your worktree venv's python with the cwd set to `/home/user/reflex` or another worktree: `python -c` and
  `python -m` put the cwd first on `sys.path`, so you would silently import THAT checkout's `reflex/` package. Run from
  your worktree root, from an app directory, or from scratch.
- The worktree's dynamic version is `0.0.0.post50.dev0+<sha>` (no tags reachable), so anything that requires
  `reflex>=X` will make `uv pip install` try to REPLACE your editable reflex with a PyPI release. Install third-party
  wheels into the worktree venv with `--no-deps` and add their dependencies explicitly.

## Workflow (the repository's CLAUDE.md applies in full; these are the points that matter most here)

1. Understand the finding from the campaign material and from the code. Confirm the root cause yourself.
2. Regression test FIRST, in the `tests/units/` module that mirrors the source you change. Run it on the unfixed
   tree — it must FAIL — and keep the output for REPORT.md.
3. Minimal fix. No drive-by refactors or unrelated changes. Handle edge cases without over-defensiveness.
   Google-style docstrings on new functions. No block comments.
4. News fragment(s): `news/+<slug>.bugfix.md` at the repo root for `reflex`; additionally
   `packages/<pkg>/news/+<slug>.bugfix.md` for every workspace package whose source you touch (reflex-base,
   a components package). One or two sentences for downstream users; no narrative. Use `.breaking.md` only
   where your brief says so.
5. Checks, from the worktree root: `uv run ruff check .` and `uv run ruff format .` (clean);
   `uv run pyright reflex tests` (if the full run is too slow, at least the modules you touched — say which in
   REPORT.md); `uv run pytest tests/units/<the modules you touched or that cover the changed code>`.
   If you change a component's `create` signature or props: `uv run python scripts/make_pyi.py` and commit
   `pyi_hashes.json` (never the `.pyi` files).
6. End-to-end verification with the campaign's own repro, run against YOUR worktree's venv
   (`/home/user/wt/<name>/.venv/bin/reflex`, `.venv/bin/python`). Copy any campaign script into scratch before
   editing it (e.g. to drop an `assert "/envs/" in rx.__file__` guard). Show the repro failing on the published
   0.9.12a1 (`envs/shared`) or the unfixed tree, and passing on your fixed tree.
7. Adversarial self-review of your diff against CLAUDE.md before committing.
8. Commit on your branch. One cherry-pickable commit per logical change (one is ideal). Message:
   `fix: <what>` + a body with root cause and fix + `Fixes #<issue>`, ending with exactly these trailer lines:
   ```
   Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
   Claude-Session: https://claude.ai/code/session_01NeyxWsuC9hqSKq8YcEwZyY
   ```
   Commit with `git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit ...`.
   NEVER push. NEVER open a PR. NEVER rebase, reset or check out anything other than your own branch.
9. Write `/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/fixes/<name>/REPORT.md` — the ONE place
   outside your worktree and scratch you may write: root cause (file:line), the fix and why this shape,
   alternatives considered and rejected, the regression test with its before/after output, e2e evidence
   (commands + key output), the checks you ran and their results, risks / behaviour changes, open questions for
   the maintainers. Put logs and JSON results under `fixes/<name>/evidence/`.
10. Return the structured result the schema asks for. `e2e_verified` may be true only if step 6 passed on the
    fixed tree AND failed on the unfixed/published one.

If the fix needs a decision you cannot make (e.g. a public API change), implement the most conservative option
that fixes the defect and list the decision under "open questions". If you cannot fix it at all, still commit
the regression test (marked `xfail` with a reason) and explain in REPORT.md.
