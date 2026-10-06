# Published a4 security review

1. Install a fresh 104-package alpha environment from the a3 lock, changing only published enterprise a3 to a4, then assert import origins and exact pins.
2. Read issue245, current fixes and installed auth/OAuth/MCP code. Exercise ordinary app-level frontend/backend default-factory failures during real OIDC logout.
3. Measure provider-cookie clearing, same-token identity, protected-action mutations, forced anonymous behavior and Bob's subsequent access to Alice's prior private records. Compare suspicious results on the published a3 baseline.
4. Check invalid bearer/forged session claims and protected MCP events/resources with real HTTP/SDK requests; check separate authenticated/anonymous identities where practical.
5. Preserve source, redacted browser/wire logs, exact package provenance and a bounded severity assessment. Stop owned ports and exclude generated artifacts. No library patches, source installs, external issues/comments or commits.
