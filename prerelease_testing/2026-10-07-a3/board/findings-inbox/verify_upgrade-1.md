ITEM: verify_upgrade
KIND: verify
REF: A3-07 (a3_upgrade-4)
TITLE: CONFIRMED: `reflex run --json` swallows a SIGINT sent to its pid (signal caught, never forwarded); under supervisord `stopsignal=INT` the escalation SIGKILL then orphans a live server and the restart goes FATAL on "port already in use"; GNU `timeout -s INT` is NOT affected (explorer's example wrong)
SEVERITY: low
STATUS: confirmed
REGRESSION_VS_0.9.12: no for "does not exit" (0.9.12 dev ignores pid-only SIGINT and SIGTERM too, leaving the frontend up); partly for the end state under supervisord stopsignal=INT (0.9.12: 10 s + SIGKILL, nothing survives, restart OK; a3/a2 --json: orphaned server keeps 3640/8640, restart FATAL)
REGRESSION_VS_0.10.0a2: no (identical, log.py:487-493 on a2)
REPRO: Own blank app (`reflex init --template blank`, a3/a2/0.9.12) + own reader `prerelease_testing/2026-10-07-a3/a3_upgrade/verification/probes/vu_reader.py`:
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python vu_reader.py --venv a3 --app <blank app> --fp 3640 --bp 8640 --json --sig INT --target pid --max-wait 40 --out out/a3-json-INT-pid.json
  a3 --json SIGINT->pid: still running at 40 s (3 runs), /ping 200, both ports bound; SIGINT->group 0.27 s; SIGINT->every pid (systemd KillMode=control-group) 0.25 s;
  SIGINT->inner child 0.29 s; SIGTERM->pid 0.29 s; plain `reflex run` SIGINT->pid 0.18 s rc 0 (a2 0.24 s). 0.9.12: pid-only SIGINT/SIGTERM never exit (backend dies, frontend stays).
  Not an environment SIG_IGN quirk: /proc status shows SIGINT caught in the supervisor; strace: SIGINT received, 0.25 s WNOHANG polling (Popen.wait grace), blocking wait4 again, no kill() to the child.
  Process managers: real supervisord 4.3.0 (`probes/vu_supervisord.sh <venv> <app> <out>`, `vu_supervisord_restart.sh`): stopsignal=INT -> stop takes 10.2 s, SIGKILL to the pid only,
  inner reflex+worker+bun+node orphaned (ppid 1) and still serving 30 s later; `supervisorctl start` -> "Frontend port: 3640 is already in use" x4 -> FATAL. stopasgroup=true 0.42 s; default TERM 0.59 s.
  docker-like PID 1 (`--pidns`, unshare): SIGINT hung 15 s (docker would SIGKILL at 10 s -> exit 137, namespace teardown), SIGTERM 0.25 s.
  GNU `timeout -s INT 12 -k 30 reflex run --json` (`probes/vu_timeout.sh`): exits at 12.26 s, clean (timeout also signals its process group); only `--foreground` hangs (42 s, orphans).
  Explorer rerun (json_drain.py INT-pid 100000, QA_CHATTY_OFF=1 QA_EOF_CAP=40 QA_WAIT_CAP=20, ports 3641/8641): TIMEOUT, 5 processes left. Reproduced.
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_upgrade/verification/out/{a3,a2,s912}-*-pid*.json, a3-json-INT-{group,tree,child,pidns}.json, a3-json-INT-pid-2.json (sig_dispositions), a3-json-INT-pid-strace.strace, sup/{a3,stable,alpha2,a3-restart,s912-restart}/, timeout_matrix.txt, explorer_rerun/a3fast-INT-pid-r100000.json; NOTES.md "## VERIFICATION" A3-07
ROOT_CAUSE_GUESS: reflex-base 0.10.0a3 reflex_base/utils/log.py:519 forwards only SIGTERM (`signal.signal(signal.SIGTERM, lambda *_: proc.terminate())`); :520-526 `except KeyboardInterrupt: continue` assumes the child got the same (group) SIGINT. Entry reflex/reflex.py:774-779. Contradicts the a1 #7328 changelog line "stops ... on SIGTERM and SIGINT without a TTY" for --json mode. Affects: proc.send_signal(SIGINT)/kill -INT <pid>, supervisord stopsignal=INT, systemd KillMode=mixed|process + KillSignal=SIGINT, docker STOPSIGNAL SIGINT / tini.
