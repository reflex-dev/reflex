# Resolve the challenged logout release classification

The maintainer has clarified that cross-minor mixed workers/downgrades are
unsupported; retain their diagnostic evidence and remove finding16 from the
release gate. Reassess finding15 rather than relying on the issue's old opening
text or an earlier source checkout.

Verify current PyPI versions, fetch the published a4 wheel and compare its
package bytes with a completely fresh exact104-pin installation. Inspect the
actual restoration try/except boundaries in that wheel. Run the ordinary logout
control and the existing application factory-failure cases again in a neutral
app, with no browser cookie clearing before the subsequent normal login. This
strengthens the earlier conditional test without modifying framework code.

Use owned fictional OIDC identities, existing Bun1.4.2/Chromium140 and ports
3152/8152/9151 only after closed-port checks. Keep current evidence separate;
stop owned services, correct aggregate reports according to observations and
the clarified support policy, commit/publish artifacts. No fixes, external
issue/comment or checkout installation.
