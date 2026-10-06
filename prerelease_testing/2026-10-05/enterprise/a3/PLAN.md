# Published enterprise 0.9.7a3 rerun

Use fresh isolated virtual environments that install published PyPI packages
only. Retain the exact a2 dependency graphs, replacing enterprise with a3;
record any dependency changes required by published metadata. App/driver copies
run from neutral temporary directories with `PYTHONPATH` absent and workspace
resolution disabled. Preserve the a2 evidence and make no framework fixes.

1. Audit the a3 wheel/sdist publication, PyPI hashes and archive contents.
2. Alpha auth lane: field descriptors, extra scopes, full upstream auth app,
   browser login/protection/logout/relogin/refresh/iframe/pending events, and
   OAuth MCP consent/PKCE/token rotation/redaction. Ports3132/8132/9131.
3. Component lane: all15 grid cases, maps/storage/fonts and anonymous MCP;
   dev and prod browser diagnostics. Ports3131/8131.
4. Stable lane: same a3 wheel with Reflex0.9.12; field/scope checks and full
   auth browser cases. Independent ports3152/8152/9151.
5. Root Free-tier lane: public production/export badge and rejected-credential
   matrix, CI/harness bypasses absent, only local fake account API. Port3144.
6. Review raw diagnostics and compare the three a2 blockers; document residual
   limits without inferring fixes from PR source. Stop owned processes,
   validate artifacts and publish on the existing testing branch.

The existing team retains the user-requested Sol6.1 Extra High configuration.
No live cloud account, provider credentials or external issue comments are used.

Exploration added a production cookie app to exercise a3's descriptor/cookie
compatibility: paired HTTP-only writes, inherited cached vars through `rx.memo`,
burst updates, reload, browser-to-server sync and deletion, with the identical
app on stable. Residual auth/MCP failures prompted small alpha/stable or a2/a3
controls, preserving the otherwise frozen graphs and failed original evidence.
