# components_typing — reflex 0.10.1a1 (2026-10-24)

Item: radix (#7345 #7593 #7418 #7438 #7629 #7645), moment (#7591), data_editor (#7607), lucide (#7604),
code (#7437), typing (#7406 #7413 #7419 #7403 #7401, `rx.form.FormData`, `VarData(position=)`), CMP-11, CMP-31.
Status: IN PROGRESS — this file is updated incrementally; the structured report is in the final message.

## Environment

- `SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa`
- `envs/new` = reflex 0.10.1a1 (radix/moment/dataeditor/code 0.10.1a1, lucide 1.1.1a1, core 0.10.1a1);
  `envs/components_typing-prev` = reflex[db]==0.10.0 strictly (radix/moment/dataeditor/code/core 0.10.0,
  lucide 1.1.0) + pyright 1.1.414 + ty 0.0.91. NOTE: the orchestrator's `envs/prev` carries moment/lucide/code at
  0.10.1a1 (reflex 0.10.0 only floors them at >=0.10.0), so it is NOT a baseline for those packages.
- `envs/components_typing-new-whl` = reflex[db]==0.10.1a1 + pyright + ty installed with `--only-binary :all:`
  (122 stubs, identical to `envs/new`). `envs/components_typing-new` (first attempt, same command without
  `--only-binary`) got every reflex package BUILT FROM THE SDIST by uv (`uv_build.json` in 9 dist-infos) and is
  missing 6 stubs — see ISSUE CT-3. Typing results below are from the wheels-only venv unless stated.
- Ports: dev 3240/8240, prod 3241 (single port). Browser: Playwright Chromium, context timezone America/New_York.

## Files (this directory)

- `ctapp/` — the app (13 pages, guarded with `NEW = hasattr(rx, "moment_provider")` so it also runs on 0.10.0).
- `probes/probe_compile.py`, `probes/probe_detail.py` — compile-time probes, run on new and prev.
- `typing/typing_user.py`, `typing/typing_new_api.py`, `typing/fd_probe.py`, `typing/fd_probe2.py`,
  `typing/run_typing.sh`, `typing/run_probes.sh` — pyright + ty modules and runners.
- `drive_ct.py` — Playwright driver (per-page checks + console/pageerror/request capture), `run_prod.sh`.
- `results/` — JSON/TXT outputs; `logs/` — trimmed server/driver/typing logs; `shots/` — evidence screenshots.

## Rerun

```
SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa
cd $SB/apps/components_typing
EXPECT_VENV=new $SB/envs/new/bin/python probes/probe_compile.py > results/probe_compile_new.json
EXPECT_VENV=components_typing-prev $SB/envs/components_typing-prev/bin/python probes/probe_compile.py > results/probe_compile_components_typing-prev.json
NEW_ENV=components_typing-new-whl bash typing/run_typing.sh            # pyright + ty, new and prev
bash typing/run_probes.sh components_typing-new-whl                    # fd_probe*.py
cd ctapp && EXPECT_VENV=new REFLEX_TELEMETRY_ENABLED=false $SB/envs/new/bin/reflex run --frontend-port 3240 --backend-port 8240 --loglevel debug
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_ct.py --base http://localhost:3240 --out results/drive_dev_new.json --shots shots/dev_new
# prod: ./run_prod.sh (stops dev, starts --env prod on 3241, drives all pages)
# prev baseline: same with EXPECT_VENV=components_typing-prev and $SB/envs/components_typing-prev/bin/reflex on 3242/8242
```

## Results so far

(see the sections appended below as each run completes)
