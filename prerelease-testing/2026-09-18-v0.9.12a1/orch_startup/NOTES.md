# orch_startup — #7049 relative baseline: backend-only startup on 0.9.11.post1 vs 0.9.12a1 (orchestrator, 2026-09-19)

Closes the gap `dev_server_cli` left (it had only absolute 0.9.12a1 numbers). `run_startup.sh` copies the
`dev_server_cli/dsc` probe app (0.9.12a1) and `dsc_prev` (0.9.11.post1), and for each venv: measures `import reflex`
(time, `len(sys.modules)`, presence of heavy modules), then three cold `reflex run --backend-only` starts, timing the
first `/ping` 200 and summing RSS of the reflex processes bound to the port 3 s later.

| | 0.9.11.post1 (`$SB/envs/prev`) | 0.9.12a1 (`$SB/envs/shared`) |
|---|---|---|
| `import reflex` | 2 ms, 57 modules, no heavy modules | 2 ms, 57 modules, no heavy modules |
| time to `/ping` 200 (3 cold starts) | 0.67 / 0.45 / 0.46 s | 0.67 / 0.45 / 0.46 s |
| RSS, supervisor + worker, 3 s after ready | 123 / 109 / 109 MB | 121 / 108 / 109 MB |

Verdict: for a small app in backend-only mode there is **no measurable difference** between the two versions in
startup time or resident memory; `import reflex` is equally lazy on both. The #7049 changelog line ("Reduce
development startup and reload time and memory by deferring unused database, admin, and compiler imports in the
backend launcher and state mutation tracking, and by avoiding redundant app preloads in spawned Granian
supervisors") is therefore neither confirmed nor contradicted by this probe — its effect, if any, is below the noise
of this scenario. The dev-mode reload path and larger apps were not measured (`logs/`).
