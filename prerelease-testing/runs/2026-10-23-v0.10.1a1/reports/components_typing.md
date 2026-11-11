# components_typing — agent report (summary)

No behavioural regression. Every targeted fix reproduces as broken on a strict-0.10.0 baseline and works on 0.10.1a1
(dev + prod); pyright 1.1.414 / ty 0.0.91 on a realistic user module: 2 / 10 errors on new vs 12 / 34 on 0.10.0.
Findings:
- CT-3 (= UP-1, medium as explored, low per verify_up) sdist-built wheels lose 6 stubs and reformat the rest. New
  detail: uv reuses a cached sdist build for later ordinary installs of the same version ("Registry requirement already
  cached"), so one `--no-binary` build on a machine taints later installs; 4 campaign venvs got sdist-built packages
  (components_typing-new, -repro, -sdist, enterprise-ctrl-a2; runtime unaffected). On such an install pyright rejects
  `rx.form.FormData[str, str]` and types `rx.form(...)` wrongly.
- CT-1 (low) `rx.radio_cards.root/item(as_child=...)` silently accepted after #7593 and emitted as css `{asChild: true}`
  (0.10.0 crashed the page) — no error or deprecation for existing code.
- CT-2 (low) `rx.moment(filter=/settings=/form_at=)` still silently become CSS; the PR's "actionable errors" are not in
  the published package.
- CT-4 (low) a `moment_provider(format=...)` overrides a child's `from_now` (react-moment precedence); docs say child
  props override the provider.
- CT-5 (low) typing gaps that pre-date 0.10.1a1 (ty `rx.Field[rx.Model | None]`, `auto_complete=True`,
  `data_editor(columns=["A"])` rejected, `VarData(position=)` deprecation invisible to checkers, ty rejects
  `rx.EventHandler[spec]`).
- CT-6 (low, unverified) FormData handler receives `"<id>": [null]` for an `id=` checkbox_group/cards root with nothing
  checked (0.10.0 dict handler omitted the key).
Passed: #7345, #7593, #7418, #7438, #7629, #7645 (one copy of each radix primitive), #7591, #7607, #7604, #7437, typing
#7419/#7403/#7401/#7402/#7406/#7413, FormData annotations; prod 13 pages clean.
Re-verified: CMP-11, CMP-31, CMP-41, CMP-13, CMP-29 fixed; CMP-15 changed; CMP-14, CMP-39 still broken (unchanged);
CMP-48 not reproduced; CMP-44 unchanged.
