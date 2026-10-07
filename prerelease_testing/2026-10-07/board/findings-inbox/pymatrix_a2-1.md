ITEM: pymatrix_a2
KIND: reverify
REF: F-016
TITLE: Zero-argument Callable and five-argument handler typing gaps persist
SEVERITY: low
STATUS: still-broken
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: Follow pymatrix_a2/typing/NOTES.md clean bootstrap and run.py invocation. Published ty0.0.84 rejects valid zero-argument handler assignment to Callable[[], Any], and both ty/pyright1.1.414 reject fully applied five-argument handlers. Compare stable/alpha1/alpha2 on matching Python3.14.7 and stable/alpha2 on3.11.16; alpha2 3.13.15 agrees. Both deliberately invalid calls must also be diagnosed.
EVIDENCE: prerelease_testing/2026-10-07/pymatrix_a2/typing/results/final/results.json, per-target metadata/freezes, complete stdout/stderr; original unchanged source/handlers_0_5.py lines62/68/75/80/88/89. All twelve final checker invocations detect both negative controls. Stable additionally fails one-through-four-argument Callable assignments under ty; both alphas fix those.
ROOT_CAUSE_GUESS: Published EventCallback overload coverage for zero/five-argument use remains incomplete for the recorded checkers. Same diagnostic sets as the previous campaign; no new alpha2 typing regression. Later checker versions and browser execution of these particular handlers are outside this static test.
