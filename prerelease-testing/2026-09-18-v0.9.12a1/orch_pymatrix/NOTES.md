# orch_pymatrix — the published 0.9.12a1 train on Python 3.10, 3.14 and 3.15.0rc2 (orchestrator, 2026-09-19)

Closes the gap the `vars_typing` cluster left (it only ran 3.11). `run_pymatrix.sh`: per interpreter, a fresh
uv venv (`uv python install 3.15` fetched 3.15.0rc2), `uv pip install --prerelease=allow` of the train with every
component alpha named, an import/lazy-loader probe, `reflex init --template blank`, `reflex run` (dev, ports
3053-3055 / 8053-8055) and a Chromium page load through `drive_app.py` with console/network capture.

| Python | install | `_NATIVE_LAZY_IMPORTS` (PEP 810 path) | `rx.text` first access / 1e6 repeats | dev server 200 | browser | `/ping` |
|---|---|---|---|---|---|---|
| 3.10.20 | OK (prints "Reflex support for Python 3.10 is deprecated…") | False | 273 ms / 0.042 s | 2 s | clean | pong |
| 3.14.7 | OK | False | 378 ms / 0.045 s | 3 s | clean | pong |
| 3.15.0rc2 | OK (granian 2.8.3 wheel available) | **True** | 396 ms / 0.030 s | 3 s | clean | pong |

All three: State subclass with a computed var constructs, `reflex init` exit 0, page renders "Welcome to Reflex" with
0 console messages / page errors / failed requests (`logs/drive_<py>.json`), no tracebacks in the dev logs
(`logs/dev_<py>.log`). The resolved sets are identical apart from interpreter-specific wheels (`logs/resolved_<py>.txt`).

Verdict: the changelog's "Python 3.15 has provisional support" (#6930) holds for install + import + dev run + browser
on the published packages, and the native lazy-import delegation is active there; 3.10 still works with the
deprecation notice; 3.14 is clean. Not exercised on 3.15: redis + dill (the changelog itself lists dill-based
function serialization as an upstream limitation).
