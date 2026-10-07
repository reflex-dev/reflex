# Item `verify_upgrade` — independently verify A3-07 and A3-08 (a3_upgrade inbox 4 and 3), and A3-06's claim

Ports: frontend 3640-3659, backend 8640-8659. Work dir $SB/apps/verify_upgrade/. Append `## VERIFICATION` to a3_upgrade/NOTES.md
(append only); probes under a3_upgrade/verification/; one `KIND: verify` inbox file per finding. Venvs: $SB/envs/a3, $SB/envs/alpha2,
$SB/envs/stable (read-only). Read ../AGENT_BRIEF.md, ../COORDINATION.md §4, FINDINGS.md A3-06..A3-08 and the inbox files.
Write your own minimal repro first (a blank app, your own slow JSON-lines reader), then re-run the explorer's scripts. Try to refute.
- A3-07: `reflex run --json` ignores a SIGINT sent to its pid only (a3, a2, 0.9.12). Is that how process managers (systemd KillSignal=SIGINT,
  docker stop with STOPSIGNAL SIGINT, supervisord) would stop it? Does `reflex run` without --json exit? Code location in reflex-base a3.
- A3-08: #7428's 30 s drain cap ends the stream mid-record (truncated last line). Reproduce with a slow reader; does the truncation happen
  only at the cap? Is the record split by reflex or by the pipe/buffering of the reader? Compare a2.
- A3-06: does writing an inherited var outside `async with self` in a background task raise on a3 and succeed on 0.9.12 exactly as
  claimed, and does the upgrade guide (`git -C /home/user/reflex show 555b667c1:docs/changelog/upgrading/upgrading-to-0-10.md`) or the
  a1/a3 changelog mention it anywhere?
