# Published component prerelease results

The final production dashboard passed 12 of 14 browser scenario groups. Both persistent failures reproduce with exact stable wheels. The two existing example upgrades found no new alpha regression, and the additional hosting CLI fixture passed 17 of 17 cases.

Source reference: `origin/r/pre-2026.10.05-37378928999`, SHA `59c675abbf6ddc973770c28f9aab22fdde675848`. All component changelogs and linked change descriptions were reviewed. Installed packages came exclusively from published PyPI wheels in temporary virtual environments; no checkout, branch or editable was installed. Every app ran from `/private/tmp` with `PYTHONPATH` unset and `uv run --no-project --python …`. [Provenance](provenance.json) records exact versions and imported `site-packages` paths; [frontend versions](evidence/frontend-versions.json) records resolved JavaScript upgrades.

| Package inventory | Installed dashboard version |
|---|---|
| core, code, gridjs, markdown, moment, plotly, radix, recharts | `0.10.0a1` |
| dataeditor, unchanged in release source | `0.9.3` |
| lucide, unchanged | `1.0.4` |
| react-player, unchanged | `0.9.2` |
| sonner, unchanged | `0.9.4` |

`reflex` and `reflex-base` were `0.10.0a1`. Dataeditor `0.9.3` is yanked for an incorrect base floor; the intentional exact source-inventory pin still ran its editable-grid flow. Other agents cover stock prerelease resolution selecting `0.9.3a1`. This dashboard used hosting CLI `0.1.72`; the separate upgrade/hosting fixtures used the full alpha graph, including hosting CLI `0.1.73a1`.

The release source's `reflex-components-internal` directory has no `CHANGELOG.md` and is absent from the announced alpha manifest; it was not installed for this component lane.

The combined app uses backend State, shared client state, memo components and two independent ComponentState inventory cards. Verified behaviors include:

- Literal-subject `rx.match` with a State Var only in a condition, including memo and foreach contexts; inventory cards update independently ([PR #6676](https://github.com/reflex-dev/reflex/pull/6676)).
- Native form submission includes ID-backed controls, empty values and a custom `_is_form_control` input, while excluding labels, wrappers, messages and submit/copy buttons. Prism and Shiki copy actions do not submit; actual clipboard text is correct ([PR #7227](https://github.com/reflex-dev/reflex/pull/7227)).
- Plotly static string title, object title/font, and memoized State layout/data updates render correctly ([PR #7226](https://github.com/reflex-dev/reflex/pull/7226)).
- Recharts FunctionVar formatter carrying State metadata updates ticks from dollars to euros with the live dataset; exact stable construction rejects this newly accepted formatter ([PR #7366](https://github.com/reflex-dev/reflex/pull/7366)).
- Markdown tables/text; static and dynamic Lucide icons; explicit Shiki transformer highlighting; dynamic Prism style; Radix Themes and primitive slider events; Themes progress and primitive visual transform; independent Moment English/French locales, timezone and duration; two-file dropzone upload with backend byte counts; Sonner action callback; Grid.js filtering plus actual Dataeditor editing; local React Player audio and backend play event.

The actual frontend graph includes Shiki/transformers `4.5.0`, Moment `2.31.0`, timezone `0.6.5`, duration-format `2.3.2`, Radix slider `1.4.7`/progress `1.1.16`, dropzone `17.0.0`, error boundary `6.1.6`, React `19.3.0` and Vite `8.3.2` ([PR #7424](https://github.com/reflex-dev/reflex/pull/7424)). [Final results, screenshots and server log](evidence/prod-final/browser-results.json) preserve real browser and server evidence. The final rerun has no console errors, page errors, failed requests or HTTP failures.

## Findings

1. **Existing Shiki convenience-transformer defect.** `rx._x.code_block("print('x') # [!code highlight]", language="python", use_transformers=True)` produces no highlighted line. The reconstructed default transformer has `library=''` and `fns=[]`, so its render emits `transformers={[]}`. Both stable code `0.9.6` and alpha code `0.10.0a1` reproduce this construction. Supplying `create_transformer("@shikijs/transformers@4.5.0", ["transformerNotationHighlight"])` passes in the actual alpha browser. See the stable/alpha `shiki` entries in [construction probes](evidence/probe-stable-venv.json) and [alpha probe](evidence/probe-venv.json), plus the `shiki-default-transformer` browser failure.
2. **Existing primitive Progress accessibility defect.** `reflex_components_radix.primitives.progress.progress(value=State.amount, max=100)` forwards `value`/`max` to its Indicator but leaves its Root without them. The visual bar updates while the Root stays `data-state="indeterminate"` and omits `aria-valuenow`. Exact stable radix `0.9.10.post1` and alpha radix `0.10.0a1` have the same construction. Themes progress correctly exposes the value. See the `primitive_progress` probe entries and `radix-primitive-progress-accessibility` browser failure.
3. **Existing Overkey reset defect.** Both stable and alpha finish a real timer/scoring round, but Reset leaves the shared client input populated. This blocks the subsequent language-switch assertion. The unchanged upstream source and exact graph comparisons are in the [upgrade report](upgrades/REPORT.md).
4. **Unreproduced Grid.js console observation.** An initial full production run logged two `Cannot read properties of undefined (reading 'length')` messages while visible table assertions passed. The final full rerun and minimal mutable-table stable dev, stable prod and alpha prod runs were clean. The [initial observation](evidence/gridjs-initial-observation.json) and comparison JSON/logs remain recorded; evidence does not establish a regression.

The changelog base-floor link #7238 resolves to an unrelated documentation PR. The match link #6675 is an issue closed by PR #6676. These reference mismatches are inventory observations rather than runtime failures. FormData is not on the tested release source; the app correctly uses its announced dictionary payload API.

## Reuse and limits

`prepare.py` copies the reusable dashboard sources into a neutral app and verifies imports. Run it with the exact installed component environment, then start the app from that temporary directory:

```sh
uv pip install --python /private/tmp/ENV/bin/python --index-url https://pypi.org/simple -r /absolute/path/components/dashboard-requirements.txt
env -u PYTHONPATH uv run --no-project --python /private/tmp/ENV/bin/python python /absolute/path/components/prepare.py /absolute/path/components /private/tmp/dashboard-app
cd /private/tmp/dashboard-app
env -u PYTHONPATH COMPONENT_API_URL=http://localhost:3121 uv run --no-project --python /private/tmp/ENV/bin/python reflex run --env prod --frontend-port 3121 --backend-port 3121 --loglevel debug
env -u PYTHONPATH uv run --no-project --python /private/tmp/ENV/bin/python python /absolute/path/components/browser_checks.py http://localhost:3121 /absolute/path/components/evidence/prod-final
```

`browser_checks.py` continues independent scenario groups after a failure and exits nonzero for failed assertions. `component_probe.py` supplies a small stable comparison. `gridjs_repro.py`/`gridjs_browser.py` preserve the clean targeted table reproduction. See [existing application upgrades](upgrades/REPORT.md) and [hosting JSON integration](hosting/REPORT.md) for their own commands and complete evidence.

No framework fixes were made. Authored harness files pass Ruff check and format; original upstream example files were preserved unchanged and excluded from harness lint. Browser coverage used Chromium `143.0.7499.4`, local media/fixtures, development and production builds; other browser engines, real cloud deployment, OAuth and third-party hotkey libraries were not exercised. Duration ENV handling and broader packaging checks belong to the other release-test lanes.

Cleanup confirmed no listeners on owned ports `3121`, `3122`, `8121` or `8122`. The fresh Bun installer appended a `BUN_INSTALL`/PATH block for this temporary runtime to the user's global `.zshrc` despite the neutral `REFLEX_DIR`. Exactly that campaign-owned block was removed, preserving the remaining shell configuration. Temporary apps/environments remain for reruns.
