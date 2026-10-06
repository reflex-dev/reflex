# Enterprise a4 auth verification plan

Install only published PyPI wheels in a fresh isolated uv environment, retaining
the a3 alpha frozen graph with enterprise 0.9.7a3 replaced by 0.9.7a4. Record
any required dependency difference. Copy saved a3 app/driver/reference Python
sources into a fresh neutral /private/tmp tree, excluding generated files and
caches. All runtime execution uses uv --no-config --no-project with PYTHONPATH
unset, explicit official private Bun 1.4.2, and private Chromium 140.

Read PR #252/#253 descriptions and changed source as reference only. Test field
rendering, extra-scope metadata and public-CLI startup, 22 full auth browser
cases, default/extra-scope four-case matrices, focused async public navigation/
reload and iframe pending replay repeats, and MCP OAuth discovery/consent/PKCE,
protected reads, code/refresh reuse rejection and redaction. Preserve a3 evidence
and capture a4 provenance, exact graph, source hashes, diagnostics and screenshots.

Own ports 3132/8132 and mock provider 9131. No library fixes, source/editable
installs, uv sync, real account/cloud writes, issue comments or commits. Classify
remaining blockers only when newly introduced, critical, or demonstrably weak
security; retain other observations as nonblockers with their tested scope.
Stop every owned server/provider/browser at completion. Root publishes results;
the parallel core_state agent handles exceptional fail-closed/security probes.
