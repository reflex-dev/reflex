# upgrade_packaging — agent report (summary)

Findings:
- UP-1 (medium, REGRESSION vs 0.10.0 sdists) Wheels built from the 0.10.1a1 sdists of reflex-components-core (32/36
  .pyi), -dataeditor (0/1), -radix (64/65) silently lose stubs: the reflex-pyi build hook lists `reflex-base` unpinned,
  the isolated build env resolves reflex-base 0.10.0, and hatch-reflex-pyi regenerates against it. Non-isolated builds
  with base a1 keep all stubs. Scripts: upgrade_packaging/bin/sdist_matrix.sh, sdist_pyi_control.sh.
- UP-2 (low, alpha-train specific) uv cannot build the `reflex` 0.10.1a1 sdist: build env refuses pre-release sibling
  floors (`require-runtime-dependencies = true`); pip builds it.
- UP-3 (low, PKG-05 pattern) `pip install reflex==0.10.1a1` (no --pre) and `pip install -U reflex` keep
  components-code / -dataeditor 0.10.0, lucide 1.1.0, hosting-cli 0.2.0 (reflex floors are `>=0.10.0`), so #7437 and
  #7607 are not delivered: a state-backed data_editor column without `type` still crashes the page (#7596) and the
  compile warns "format_data_editor_column has been deprecated ... Upgrade reflex-components-dataeditor".
Passed: install matrix 3.11–3.15 pip + uv, greenlet, fresh-DB migrations; #7440; Bun 1.4.4 download / replace / new
warning; #7556; in-place upgrades form-designer, twitter + Redis (+ rollback, pickled sessions survive), github-stats,
upload — identical flows; package.json diffs only the expected bumps; #7566 migrates npm devDependencies, 0 reinstalls
per hot reload (0.10.0 reinstalled every reload with npm); third-party sweep 22/22; auth demos unchanged; #7646 docs;
mixed sibling graphs run (reverse graph too).
Re-verified: PKG-09, PKG-08, PKG-13, F-006 fixed; PKG-05 changed (see UP-3); PKG-04 changed (see UP-2); #7304 fixed;
F-019 unchanged.
Context (both versions): 4 glide-data-grid TypeErrors at page load in the mixed app.
Not covered: nba example (CSV blocked), remote templates, non-Redis rollback.
