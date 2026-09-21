# rv_devserver_badge — smoke, FINDING-017 (dev supervisor socket), FINDING-012 (badge/portal), dev-server surface
Ports: frontend 3220-3239 / backend 8220-8239. Scratch: $SB/reverify/rv_devserver_badge/. Notes dir: reverify-0.9.12a2/rv_devserver_badge/.

Checks (on `$SB/envs/a2`; a1 = `envs/shared`, prev = `envs/prev`):
1. Smoke (Phase 1 of the skill): `reflex init --template blank` in scratch with the a2 venv, `reflex run` dev, drive it
   with `/home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py` (run it with `$SB/envs/driver/bin/python`),
   then `reflex run --env prod` on one port and drive again: zero console errors / failed requests / server tracebacks.
   Diff the generated `.web/package.json` against the campaign's `smoke/` copy (the `"mergician": "v2.0.2"` leading-`v`
   nit is known; anything else changed is an anomaly).
2. FINDING-017 / #7213 — `dev_server_cli/verification/scripts/break_reload_probe.py <venv> <appdir> <fp> <bp> <label> <logdir>`
   with a copy of `dev_server_cli/dsc` as appdir: a2 → `CONNECTION_REFUSED` (fast) at +10 s and +24 s and `200` after the
   file is restored; a1 → `TIMEOUT_NO_REPLY_6s` (record once); prev → `CONNECTION_REFUSED`. Then the 20 Hz ping loop
   across two harmless hot reloads on a2 (`dev_server_cli/scripts/`, see NOTES.md) → 0 refused, 0 errors (#7114
   intact). Then `dev_server_cli/scripts/sigterm_port_probe.py` on a2 → `CONNECTION_REFUSED` at +8 s/+18 s like prev
   (FINDING-018, `reflex run` ignoring SIGTERM to its own pid, is pre-existing — just note unchanged). Also confirm a
   normal dev session shuts down on SIGINT to the process group and leaves no listener (ports.py).
3. FINDING-012 / #6143 — `components_bumps/verification/vapp` copied to scratch, `reflex run --env prod` on one port
   with the default badge setting on a2, driven with `components_bumps/verification/editor_probe.py` / `vdrive.py`:
   `document.getElementById("portal")` exists, the "Built with Reflex" badge is rendered, clicking an image cell opens
   the overlay/carousel, no "portal not found" console error; a1 fails the same probe (record). Then the campaign's
   `components_bumps/gallery` app in prod on a2 for the wider data_editor / recharts / plotly / sonner surface
   (its NOTES.md lists the drivers): no new console errors or failed requests.
4. Dev-server surface touched by #7217: with a2 in dev, verify the hot-reload flow end to end (edit a page → browser
   updates, backend keeps answering), `reflex run --backend-only` + `--frontend-only` pairing still works, JSON logs
   (#7193) still emitted with `REFLEX_LOG_FORMAT=json` if the campaign used it (see `dev_server_cli/NOTES.md`), and a
   syntax error saved mid-run recovers to 200 once fixed.
Write the pass/fail table in NOTES.md and return it in the structured result.
