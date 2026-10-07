ITEM: macos_lifecycle
KIND: reverify
REF: F-007
TITLE: npm single-PID SIGTERM passes on macOS with a1/a2; stable frontend remains running
SEVERITY: medium
STATUS: changed
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: Follow macos_lifecycle/NOTES.md's clean-PyPI-environment commands, then run run_case.py with --env alpha2 --manager npm --port 3660 --backend-port 8660 --unicode-path --hmr; compare --env alpha --port 3661 --backend-port 8661 and --env stable --port 3662 --backend-port 8662 --attempt 2. The script launches the actual CLI in an isolated non-TTY process group, performs browser events/reload/HMR, sends SIGTERM only to the CLI, waits 30 seconds, records processes/listeners, then explicitly cleans the group.
EVIDENCE: prerelease_testing/2026-10-07/macos_lifecycle/evidence/{alpha2-npm-dev-1,alpha2-npm-dev-2,alpha-npm-dev-1,stable-npm-dev-2}.json and matching .server.log files. Alpha2 npm exits 0 in 0.288/0.178 seconds and alpha1 in 0.182 seconds with empty listener/group snapshots. Stable retains CLI PID9031, npm PID9130, node PID9150 and frontend port3662 after30 seconds; cleanup snapshots are empty.
ROOT_CAUSE_GUESS: unknown. Published alpha2 reflex/reflex.py:466–472 terminates the frontend subprocess. This Mac process topology has npm directly parenting node, whereas the original Linux report had an intermediate shell, dead npm, and orphaned node. OS/shell/runtime sensitivity is not isolated. Do not label the Linux finding fixed based on this Mac-only run.
