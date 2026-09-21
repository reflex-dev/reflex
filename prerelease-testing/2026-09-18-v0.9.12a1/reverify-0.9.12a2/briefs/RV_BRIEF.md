# Phase 7 re-verification brief — reflex 0.9.12a2 + reflex-enterprise 0.9.6a1 (shared rules)

You are one of five parallel re-verification agents. The 0.9.12a1 pre-release campaign found four regressions and
one high-impact pre-existing bug; fixes were merged and republished as **reflex 0.9.12a2 / reflex-base 0.9.12a2**
(component packages unchanged: core 0.9.10a1, radix 0.9.10a1, code 0.9.6a1, dataeditor 0.9.3a1, gridjs 0.9.2a1,
markdown 0.9.4a1, plotly 0.9.7a1, recharts 0.9.4a1, sonner 0.9.4a1; lucide 1.0.4, moment 0.9.4, react-player 0.9.2)
plus an offline wheel of **reflex-enterprise 0.9.6a1**. Your job: re-run the ORIGINAL failing repros against the
published packages, re-exercise the surfaces those fixes touch as a user would, and report pass/fail with evidence.
The maintainers will decide "release 0.9.12 as final" from your results, so be exact and honest.

## Read first
1. `/home/user/reflex/.claude/skills/prerelease-test/references/agent-brief.md` — environment traps and known-benign
   console noise (binding).
2. `/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/AGENT_BRIEF.md` — the campaign's own brief (ports
   discipline, `ports.py`, no pattern kills).
3. `/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/FINDINGS.md` — the sections for the findings your brief
   names (grep `## FINDING-NNN`), and `RELEASE_PLAN.md` "Tracking issues".
4. Your per-agent brief in this directory, then the cluster `NOTES.md` files it points at (exact rerun commands live
   there, including each `## VERIFICATION` appendix).

## Environments (all PyPI-only; installed by the orchestrator; READ-ONLY — never `pip install` into them)
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
- `$SB/envs/a2`      reflex 0.9.12a2 + the component alphas above (Python 3.11). The tree under test.
- `$SB/envs/enta2`   the same plus `reflex-enterprise 0.9.6a1[mcp]` from the offline wheel. Enterprise tree under test.
- `$SB/envs/prev`    reflex 0.9.11.post1 (previous stable) — the baseline.
- `$SB/envs/shared`  reflex 0.9.12a1 (the alpha the campaign tested) — to show "failed before, passes now".
- `$SB/envs/ent`     0.9.12a1 + reflex-enterprise 0.9.5 (the broken pair); `$SB/envs/entprev` 0.9.11.post1 + rxe 0.9.5.
- `$SB/envs/driver`  playwright 1.63 + httpx + websockets; Chromium at /opt/pw-browsers/chromium.
- Wheels: `$SB/wheels/reflex_enterprise-0.9.6a1-py3-none-any.whl`, `$SB/wheels/reflex_enterprise-0.9.5-py3-none-any.whl`.
If you need anything else installed (redis client, reflex-local-auth, an example app's requirements), create your OWN
venv under `$SB/reverify/<your-name>/` with `uv venv` + `uv pip install --prerelease=allow` naming every reflex package
version explicitly (an exact `reflex==0.9.12a2` pin without the flag upgrades only reflex/reflex-base and leaves the
component packages at their stable releases — the campaign's "mixed-version trap"). Never install from any checkout:
`/home/user/reflex`, `/home/user/wt/*`, `/home/user/reflex-enterprise` are READ-ONLY sources of scripts, demos and
sample apps. Never run a venv's python with the cwd inside a checkout (it would import that checkout's `reflex/`).
Copy sample apps and scripts into `$SB/reverify/<your-name>/` before running or editing them; drop any
`assert "/envs/..." in reflex.__file__` guards or point them at your venv.

## Rules
- Ports: ONLY your reserved range (in your brief); always pass `--frontend-port/--backend-port`; prod uses one port.
  Redis, if you need it: `redis-server --port <your last backend port> --save ''`. Kill by pid (yours, or via
  `uv run --no-project python $SB/bin/ports.py`); NEVER `pkill -f "reflex run"` or any pattern kill.
- `REFLEX_TELEMETRY_ENABLED=false` on every server; `CI=true` for enterprise apps (dev login gate);
  `NO_PROXY=localhost,127.0.0.1` for clients. Foreground `sleep` is blocked — poll in python.
- Four channels on every run: server log, browser console (errors AND warnings), network (4xx/5xx/failed), rendered
  page. Capture them (the campaign drivers already do).
- A check PASSES only if the original failing repro now behaves like 0.9.11.post1 (or better) on the a2 tree. Where
  the campaign recorded a1 failing, re-run on `envs/shared` too when cheap, so the table reads "a1 FAIL → a2 PASS".
- A NEW issue needs: exact repro, the four channels, and a baseline on `envs/prev` AND on `envs/shared` so it can be
  classified (new in a2 / present since a1 / pre-existing). Do not report the campaign's known pre-existing findings
  as new (FINDING-018, -023, -024, -025, -015, -019 ...); just confirm "unchanged" if you happen to see them.
- Write `NOTES.md` in `/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1/reverify-0.9.12a2/<your-name>/`
  (that directory tree is the ONE place outside scratch you may write): what you ran, exact commands, per-check
  result, evidence paths; put logs/JSON/screenshots under `logs/`, `out/`, `shots/` there (trim large logs). If the
  harness refuses to write a markdown file, put the same content in your final response.
- Return the structured result the schema asks for: one row per check with `status` in {pass, fail, anomaly,
  skipped} and a one-line `evidence` pointer; `new_issues` only for things not in FINDINGS.md.
- Time box: aim for ~75 minutes of wall clock; prod builds take 3–4 min each — plan them.
