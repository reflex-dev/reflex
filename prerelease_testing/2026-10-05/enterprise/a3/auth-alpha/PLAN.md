# Enterprise a3 auth validation plan

Create a fresh CPython 3.12.1 uv environment under
`/private/tmp/reflex-enterprise-a3-20261005-alpha`. Install the retained frozen
PyPI graph with exactly one requested change: enterprise 0.9.7a2 to 0.9.7a3.
Record resolver failures or required graph differences rather than installing
repository/editable sources. Verify versions and import origins.

Copy retained Python app, driver, and reference sources to the neutral directory
`/private/tmp/reflex-enterprise-a3-20261005-auth-alpha`; exclude generated .web,
state, caches, locks, and environments. Run from that tree with PYTHONPATH unset
and uv --no-config --no-project. Set the custom Bun path to the already verified
official private Bun 1.4.2. Keep ports 3132/8132 and provider 9131.

Run the four field-render variants and OIDC extra-scope metadata check. Start
the formerly failing full upstream auth app through the public CLI and run all
22 retained non-custom browser cases. Test independent auth_min default and
extra-scope configurations, clean logout/reprotection/relogin as Bob, pending
event replay and iframe popup behavior. Exercise MCP session authentication,
isolation/redaction, OAuth discovery/consent/PKCE, single-use codes, refresh
rotation/replay, and protected state tools.

Capture exact commands, package provenance, stdout/backend/browser/network
diagnostics, screenshots and explicit pass/failure counts. Preserve a2 evidence.
Do not patch tested packages, write real cloud accounts, or publish issues.
Copy only reusable source and concise evidence back to this artifact directory.
Stop all owned servers/provider/browser contexts after the checks. Root handles
archive auditing, Free-tier validation, central reports and commits.
