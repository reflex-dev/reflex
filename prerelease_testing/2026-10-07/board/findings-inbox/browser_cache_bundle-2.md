ITEM: browser_cache_bundle
KIND: new
REF: -
TITLE: npm source-only hot reload still reinstalls packages because an empty devDependencies object is absent after npm
SEVERITY: low
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a1: no
REPRO: Follow browser_cache_bundle/reload_cache/NOTES.md; run npm_minimal.py with --sb <published-env-scratch> --env alpha2 (also stable/alpha). A heading/counter app changes only an imported label A→B. npm install count goes1→2 although both lockfile semantic hashes are unchanged. Current .web/package.json lacks devDependencies; the next rendered manifest has devDependencies:{} and this is the sole semantic difference. Add only that empty object before label B→C: alpha2/alpha1 counts remain2, while stable's byte comparison reaches3. All18 minimal browser checks pass.
EVIDENCE: browser_cache_bundle/reload_cache/minimal_results/{alpha2,alpha,stable}-minimal-1/results.json, server.log.gz and screenshots; minimal_app/ and npm_minimal.py. Full Bun/npm HMR comparison and exact commands in NOTES.md. Source-only and formatting-only edits skip installs on both alphas with Bun, but still install with npm.
ROOT_CAUSE_GUESS: Published reflex/utils/frontend_skeleton.py sync_root_package_json_to_web / _compile_package_json compare parsed objects with absent vs empty devDependencies; reflex/utils/js_runtimes.py invalidates the frontend install cache on that difference.
SCOPE: Existing npm cache-efficiency gap in the optimization's coverage, not a browser correctness regression or a timing claim. No framework fix applied.
