# Free-tier production/export guard exploration

Use only the installed PyPI Reflex 0.10.0a1 / enterprise 0.9.7a2 graph. Drive the
real public Click CLI with no CI or app-harness bypass and no patched tier or
guard functions. Route the official hosting SDK to a disposable loopback HTTP
account API through REFLEX_CLOUD_BACKEND_URL. Redirect only credential-file
configuration, including in backend workers, to temporary fixture files.
Install a Python audit hook that records/rejects non-loopback connections.

Test Free production with badge true and false, Free production/development
exports, an Enterprise badge-off control, and rejected-credential production
and export controls. PR241 explicitly enforces a Free badge-off request back
to true before the command check; therefore verify the warning and actual
badge inclusion rather than incorrectly expecting the public command to fail.
Observe actual production rendering/events and exported badge markup.

Use the already verified temporary Bun 1.4.2 as a configured custom runtime,
so no installer or shell-profile mutation is needed. App port 3131; production
frontend/backend share it and bind loopback. Credentials/API are local fake
fixtures; no real cloud accounts or deployments. Save commands, wire/audit
events, screenshots, export metadata, logs, and exact reproducible conclusions.
Stop every owned process and remove temporary credential data after the run.
