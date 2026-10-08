# Validation of reflex-dev/reflex#7505 (A3-11 / A3-12 fix, branch `claude/a3-11-storage-echo`)

Runs the campaign's own reproductions against the PR branch (worktree `/home/user/wt-a3-11`, reflex and reflex-base editable from it,
venv symlinked as `$SB/envs/a311fix`), with the published 0.10.0a3 (`$SB/envs/a3`) as the control. The apps are copies of
`a3_hydration/src/{bootecho,syncstamp}` and `a3_hydration/verification/src/vhsync` whose venv guard is changed to the worktree path.

| scenario | published 0.10.0a3 | PR branch |
|---|---|---|
| explorer storm (`sync_race.py` Part S: tab0 changes a synced var 5x while 6 tabs load), dev | 3/4 storm (48k–61k frames, never converge) | 0/11 storm, all converge on s5 (65–81 frames) |
| same, prod | 2/5 (campaign) | 0/7 storm, all converge |
| explorer `stamp_storm.py /stamp 6` (A3-12), dev | 4/4 storm (330k–478k frames) | 0/6 storm, 6/6 converge |
| same, 3 tabs, dev | storms (campaign) | 0/6 storm, 6/6 converge |
| same, 6 tabs, prod | — | 0/4 storm, 4/4 converge |
| verifier raw CDP, 3 restored background tabs, one click, 100 ms RTT | 3/3 storm (verifier) | 0/3 storm; race triggered 3/3 (`vtrigger.txt`) |
| verifier restore 7 tabs + click, 100 ms RTT | storm whenever triggered | 0/4 storm; race triggered 4/4 |
| verifier 6 restored background tabs on stamping pages (A3-12) | 2/2 storm | 0/2 |
| verifier 4 stamping tabs + dev backend reload (A3-12) | 2/2 storm | 0/2 |

Rerun: `scripts/matrix.sh` (explorer drivers, ports 3150/3151, 8150/8151) and `scripts/vh_matrix.sh` (verifier drivers, 100 ms RTT
proxy, ports 3660/8660/8661). Results: `results/final_matrix.txt`, `results/fix_*.json`, `results/vtrigger.txt`.

The table above is for the first design (398d4b97a / d14c025bd: skip every recognised echo, resync a crossed synced var).

## Revisions after review, and the final commit

| commit | echo rule | result |
|---|---|---|
| 5994b9141 | retire the oldest pending value on any unmatched reply (Greptile: a replaced echo hid a later handler write) | **storm regression**: verifier dev-reload scenario stormed 2/6 — rejected |
| ff23ef3b9 | skip an echo only if a counter of other tabs' `storage` events grew since it was sent | stamp matrix 16/16 converge; Greptile then showed the socket reply can arrive before the `storage` event (the tab writes the old value over the new one) — confirmed by `test_synced_storage_echo_crossed_by_another_tab_is_not_written[False]`, which fails on it |
| **d03ddb107 (final)** | write an echo only if the value stored now is one this tab wrote after sending it; storage map back to synced vars only | below |

Final commit d03ddb107 (`results/d03ddb107/`):

| scenario | result |
|---|---|
| explorer storm, dev / prod | 0/5, 0/3 storm; all converge, 67–95 frames, 0 in the quiet window |
| explorer stamp 6 tabs dev / 3 tabs dev / 6 tabs prod (A3-12) | 6/6, 6/6, 4/4 converge, no storm (37–159 frames) |
| verifier raw CDP 3 tabs, one click, 100 ms RTT | 0/3 storm, converge; race fired 3/3 (`vtrigger.txt`) |
| verifier restore 7 + click, 100 ms RTT | 0/4 storm, converge; race fired 4/4 |
| verifier 6 background stamping tabs | 0/2 storm |
| verifier 4 stamping tabs + dev backend reload (the scenario that caught 5994b9141) | 0/4 storm |

Plus: `test_hydration_storage.py` 22/22 (dev+prod), Selenium client_storage/upload/connection_banner/call_script 23/23, state.js
unit test, pre-commit. Rerun as above after `rm -rf` of the `.web` dirs in `stamp-fix`, `run-fix` and `vh-fix-dev` (template
changes only reach `.web` on a reflex version change).
