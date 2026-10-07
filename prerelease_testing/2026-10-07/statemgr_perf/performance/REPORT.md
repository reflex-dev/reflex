CLUSTER: statemgr_perf / performance (macOS, published 0.9.12 versus 0.10.0a2)

SUMMARY: No performance regression or functional defect found in this workload. All 600 measured browser clicks and 60 warm-up clicks passed; the 12 measured browser runs had no console warnings/errors, pageerrors, failed requests, HTTP 4xx/5xx responses, or cancellations. Alpha2 reduced handler CPU by about 35%, accelerated isolated scalar reads/writes, and modestly reduced full compiler and production export duration. This compares complete published dependency graphs, not a single commit.

TESTS:
- Four final-source production smoke cases: stable/alpha2 × unused SharedState absent/present. Each checked actual sorted output and weighted-rank checksum, all 2,000 conditional values across ten memo components, all 2,000 foreach values, two ordinary actions, and all 50 updated state fields in websocket deltas.
- Twelve production browser runs: three independently restarted server/browser repetitions per case, five excluded warm-up clicks and 50 measured clicks each. An independent browser context repeats the semantic preflight before each run.
- Three fresh-process repetitions of 100,000 scalar reads/writes per version in dev and prod; three fresh-process repetitions of 2,000 Var expressions per version. Generated JS is evaluated independently against Python arithmetic outside the timed region.
- Three production exports and three initialized dry Python compiles per version, after unmeasured setup. Version order alternates; all commands exit zero.
- Timing gate, process cleanup, import guards, client-only proxy handling, browser diagnostic classification, and parser/source checks passed. Final cleanup verified all 20 owned server groups and reserved ports empty at 08:34:38 UTC.

ISSUES: None. No alpha2 median was over 20% slower, so no regression investigation/repetition was needed. No finding inbox entry is proposed.

## Measurements

Numbers are medians of three independent repetitions. Browser rows are medians of the three within-run 50-click medians, not pooled observations. Every individual sample remains in `runs/*.json.gz`; `comparison.json` retains repeat values and ranges.

| Measurement | 0.9.12 | 0.10.0a2 | Alpha2 change |
|---|---:|---:|---:|
| Isolated scalar read, dev | 895.6 ns/op | 205.4 ns/op | 4.36× faster |
| Isolated scalar write, dev | 9,041 ns/op | 1,042 ns/op | 8.68× faster |
| Isolated scalar read, prod | 960.1 ns/op | 203.5 ns/op | 4.72× faster |
| Isolated scalar write, prod | 9,353 ns/op | 859.2 ns/op | 10.89× faster |
| Construct 2,000 Var expressions | 245.95 ms | 174.44 ms | 29.1% less time |
| Full Python compile, CLI internal timer | 0.726 s | 0.640 s | 11.8% less time |
| Dry compile, complete process wall | 1.183 s | 1.096 s | 7.4% less time |
| Compile-pages subphase | 0.42 s | 0.34 s | 19.0% less time |
| Production export, complete process wall | 2.905 s | 2.774 s | 4.5% less time |
| Handler CPU, no unused SharedState | 32.954 ms | 21.180 ms | 35.7% less CPU |
| Handler wall, no unused SharedState | 33.085 ms | 21.201 ms | 35.9% less time |
| WS application-frame RTT, no unused SharedState | 35.176 ms | 22.655 ms | 35.6% less time |
| Native click → DOM update, no unused SharedState | 35.60 ms | 23.05 ms | 35.3% less time |
| Handler CPU, unused SharedState defined | 32.192 ms | 21.074 ms | 34.5% less CPU |
| WS application-frame RTT, unused SharedState defined | 34.166 ms | 22.648 ms | 33.7% less time |
| Native click → DOM update, unused SharedState defined | 34.60 ms | 23.20 ms | 32.9% less time |

The no-SharedState handler CPU repeat medians were 32.447/33.429/32.954 ms on stable and 21.180/20.992/21.365 ms on alpha2. The separation is larger than the observed repeat variation. Alpha2's click-to-DOM median with the unused SharedState was only 0.15 ms higher than without it; this heavy workload does not isolate the tiny fan-out dispatch optimization.

The scalar-read result supports the direction and approximate magnitude of the advertised read improvement. This particular write probe measured 10.89× in production, below the cited approximately 15×; that is a workload-dependent magnitude observation, not a functional failure. Var construction measured 1.41× here; an “up to 2×” claim does not promise 2× on every expression mix. Full Python compilation includes memo module emission, but this experiment does not separately attribute gains to memo-body reuse.

## Interpretation and controls

The host was an Apple M1 Pro MacBookPro18,3 with ten physical/logical cores and 16 GiB RAM, macOS 26.6.2, Python 3.12.14, Chromium 153.0.8010.12 via Playwright 1.63.0, Node 26.8.1, and Bun 1.4.0. The coordinator paused all other campaign runtimes before the run; ordinary host applications remained open. This is a local controlled comparison, not an idle isolated laboratory. Host load snapshots, alternating order, individual measurements, and exact package inventories are retained.

The published graphs differ in dependencies as well as Reflex code. For example, wrapt is 2.3.0 versus 2.5.0; frontend React is 19.2.8 versus 19.3.0, and Vite is 8.2.2 versus 8.3.2. Therefore, app/export gains should not be assigned entirely to one Reflex change. Stable invoked Bun's unchanged-install check on all measured exports (reported install phase 0.07/0.08/0.08 s); alpha2 skipped it (0.00 s each). The 0.131 s total-export difference includes this cache behavior. The separate initialized dry compiler measurement excludes the frontend build/install phase and includes memo emission; the `Compile pages` subphase ends earlier.

The 5,000 dataclass rows are sorted and summed server-side but not rendered. This measures a backend-heavy event with a small DOM update. Handler CPU/wall measurements exclude transport, serialization, shared-state dispatch, and DOM rendering; websocket RTT and native click-to-DOM measurements include more of the application path. Scalar probes include loop/checksum arithmetic overhead. Results do not establish production throughput, Redis performance, Safari latency, or tail latency under concurrency.

An initial untimed fixture passed but exposed stable's existing Boolean event-argument conversion warning. Before measurements, both public events became zero-argument wrappers around the same private workload helper. Final-source preflights passed again and the warning disappeared. The initial evidence is retained and excluded from measurements. Final server logs retain only the expected implicit Radix-theme deprecation; no framework code was changed.

## Evidence

- `NOTES.md`: exact clean bootstrap, preflight, run, and summary commands; method boundaries.
- `comparison.json`: every repeated scalar/compiler/browser summary and ratio.
- `logs/*-freeze.txt`, `frontend-dependency-inventory.json`, host metadata, and measured source archive/hashes.
- `logs/measured-orchestration.log`: complete serial run and verified per-server cleanup.
- `runs/*browser-[0-2].json.gz`: complete frames, checks, diagnostics, and individual browser samples; matching `.summary.json` and screenshots.
- `logs/final-cleanup.json`: no surviving owned server groups or reserved-port listeners.
