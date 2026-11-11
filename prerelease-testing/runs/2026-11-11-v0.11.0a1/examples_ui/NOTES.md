# examples_ui — non-DB reflex-examples, in-place upgrade 0.10.1 -> 0.11.0a1

## Status / resume here
- [x] staged: `$SB/apps/examples_ui` = copy of `prerelease-testing/fixtures/upgrade` (bin/stage.sh --no-fetch) + apps
  copied from `$SB/downloads/reflex-examples` @ ebe19ff into `$W/up/apps/<app>` (github-stats + upload QA patches applied,
  rxconfig venv guard `QA_EXPECT_VENV`). Env: `. $SB/apps/examples_ui/env_eu.sh`.
- [x] base venvs `$SB/envs/examples_ui-<app>` = `reflex==0.10.1` + requirements.txt, `-c $W/prev_constraints.txt`
  (freeze of `$SB/envs/prev`), no --prerelease. Freezes in `$W/up/freeze/<app>-base.txt`.
- [ ] per-app sequences (see sections below)
- [ ] fresh-install matrix
