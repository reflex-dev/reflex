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
