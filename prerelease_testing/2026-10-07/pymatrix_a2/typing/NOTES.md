# Published handler typing comparison

Completed on macOS using published `ty==0.0.84` and `pyright==1.1.414`, matching the previous campaign's tool versions. The original `handlers_0_5.py` fixture is copied verbatim so line references remain comparable. It is analyzed from a neutral scratch directory, never the checkout. Every target interpreter first imports Reflex with an environment-specific origin assertion; full metadata, freeze files, commands, stdout and stderr are retained.

The final comparison uses six targets: stable and alpha2 on Python 3.11.16; alpha2 on Python 3.13.15; stable, alpha1 and alpha2 on Python 3.14.7. Earlier stable/alpha1 Python 3.14.0 probes remain under `results/controls/`; they gave the same diagnostic sets, but final baseline comparisons use matching interpreters.

| Tool / release | Unexpected error lines in valid-use portion | Deliberate invalid calls |
| --- | --- | --- |
| ty, stable | 62, 68, 75–80, 88, 89 | Both 98/99 diagnosed |
| ty, alpha1 and alpha2 | 62, 68, 75, 80, 88, 89 | Both 98/99 diagnosed |
| pyright, all releases | 62, 68, 80, 88, 89 | Both 98/99 diagnosed |

Results are identical across tested interpreter versions for each release/tool. Fully applied five-argument handlers fail at literal and Var call sites, ordinary Callable assignment and component triggers. ty additionally rejects a zero-argument handler assigned to `Callable[[], Any]`. Both are the previously reported **F-016**, still present in alpha2 and not regressions versus stable. The alpha fixes the one-through-four-argument Callable assignments rejected by stable's stubs under ty. All other fixture positions, including partial application, have no reported error. This is static typing coverage, not a claim that all these event paths were browser-tested here.

The two deliberate errors pass an incompatible first argument and too many arguments. Every one of the twelve final checker invocations detects both, providing a positive check that the tools resolved and analyzed the fixture. Framework diagnostics and expected negative-control diagnostics remain separate in `results/final/results.json`. The replay runner returns **1** because valid-use positions still have diagnostics; it does not turn these findings into a passing exit status. It also fails on missing negative controls or an abnormal checker exit. No checker rules, types or imports are suppressed.

These results pin the checker versions for comparison; later ty/pyright releases were not tested. No framework or stub changes were made. `run.py` was formatted after measurement; the copied fixture and its diagnostic line numbers were preserved. Fatal lint checks cover the runner; the historical fixture is intentionally not reformatted.

## Clean replay

```sh
export ART=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/pymatrix_a2/typing
export SB=/private/tmp/reflex-typing-replay
bash "$ART/bootstrap.sh" "$SB"
cd "$SB"
export UV_CACHE_DIR="$SB/uv-cache"
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python "$ART/run.py" \
  --sb "$SB" --env pymatrix-stable-311 --env pymatrix-a2-311 --env pymatrix-a2-313 \
  --env pymatrix-stable-3147 --env pymatrix-a1-3147 --env pymatrix-a2-314 \
  --out "$SB/results/typing"
```

The bootstrap installs only frozen PyPI packages into new virtual environments and pins the interpreter versions. Node must be available for pyright (the recorded run used Node 26.8.1). The driver uses only the Python standard library; it starts no web server or browser. Existing campaign environments were read-only; the final alpha2 graphs were supplied by the sibling browser subtask. The stable controls are fresh public `reflex==0.9.12` installs with Pydantic 2.13.5, while alpha1 recreates the earlier frozen graph. Per-target metadata identifies actual distributions rather than relying on environment names.
