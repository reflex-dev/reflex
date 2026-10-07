# macOS Python compatibility follow-up

Owner: `codex-macos-pass2-01a11520`. Status: claimed, preparation only until the ongoing state-manager performance measurements finish.

Plan: create isolated published-PyPI environments for Python 3.11, 3.13 and 3.14; copy the previous campaign's state-annotation app into neutral scratch; exercise its actual page, mutations, computed values, dataclass/model values and background events in development and production Chromium. Check current alpha2 support boundaries, including clean Python 3.10 refusal, and rerun the handlers 0–5 argument typing fixture using published tools. Compare any failure with stable 0.9.12 and alpha1 before assigning regression status. New assertions will extend the existing app where practical.

Reserved ports: frontend 3540–3559, backend 8540–8559. Production uses equal frontend/backend ports. Only one server per worker; timing tests elsewhere must be finished before installations or runtime work begin. All Python and uv operations run from a neutral scratch directory, with package-origin assertions and no checkout installation. Shared environments remain read-only. Capture frozen distributions, exact commands, browser/server/network diagnostics, screenshots and complete cleanup evidence. Final scope, measurements and limitations will replace this plan.
