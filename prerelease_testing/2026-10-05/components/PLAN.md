# Published component prerelease testing

Test source reference: `origin/r/pre-2026.10.05-37378928999`.

1. Read the latest alpha changelog entries and linked PR descriptions for every component package; record unchanged package versions.
2. Install exact published PyPI wheels into `/private/tmp/reflex-prerelease-components-20261005/venv`, with an isolated uv cache. Run only from a temporary app directory with `PYTHONPATH` unset and verify module provenance.
3. Build a dashboard combining State, client state, memo components and two independent ComponentState inventory cards. Exercise form ID filtering, match conditions, Plotly title normalization, Recharts function formatters, Shiki, Radix slider/progress, upload, Moment and the unchanged table/icon/toast/media packages.
4. Use the published Playwright package against the real server. Capture console, page errors, failed requests, HTTP failures, server logs, screenshots and assertion results. Repeat relevant failures against exact stable wheels where feasible.
5. Preserve reusable sources and evidence here; report framework failures without changing the framework.

Changed packages: core, code, gridjs, markdown, moment, plotly, radix and recharts (`0.10.0a1`). Unchanged packages in this source release: dataeditor `0.9.3`, lucide `1.0.4`, react-player `0.9.2`, sonner `0.9.4`.

The dataeditor stable pin is yanked on PyPI with reason "incorrect minimum reflex-base requirement"; it remains the source-inventory compatibility baseline. The changelog's base-floor reference #7238 resolves to an unrelated documentation PR. The match changelog references issue #6675, which closes through PR #6676.
