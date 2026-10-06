# Adversarial review of the a3 artifacts

Observed package behavior and residual findings are numbered separately in the
[report](REPORT.md) and central findings 12–14. Test source/runtime origins,
unchanged dependency controls and raw diagnostics were inspected. No framework
fixes or changes to reviewed drivers were made after identifying these limits.

1. **P2 — Cookie request failures are recorded but not acceptance-gated.**
   `cookies/browser.py` rejects page, HTTP and console errors, but does not reject
   `requestfailed`. Both runs have 15 sync HTTP 200 responses and 15 aborted
   requests. The visible cookie/header assertions pass; future automation must
   classify failures explicitly rather than trust the boolean alone.

2. **P2 — Free-tier browser diagnostics remain incomplete.** Its inherited
   helper records console messages but rejects only page exceptions; it has no
   HTTP/request-failure recording. Current raw evidence was reviewed, including
   three expected WebSocket failures in the frontend-only development export.
   This lane's success must not be described as wholly clean network/console
   acceptance. The Python socket audit excludes browser and Bun traffic.

3. **P2 — Denied production startup lacks an independent listener assertion.**
   The inherited Free-tier branch checks denial text and absent exports, but
   does not probe for a transient production listener. Current denied CLI logs
   show no startup. Reuse should strengthen this before treating the driver as
   sufficient proof for arbitrary future guard implementations.

4. **P2 — Observation-driver exit status is not acceptance.** Alpha auth reload/
   iframe repeat scripts intentionally preserve failing JSON observations while
   returning zero if observation/setup completes. The principal full/minimal
   matrices return nonzero on a failed scenario. Read the observation fields;
   do not infer success from the process status. The OAuth helper also records
   browser errors without acceptance-gating them; current errors were manually
   inspected and are absent.
   The small control's reusable driver now asserts restoration after saving
   observations, but that final variant was not browser-run. Its executed
   predecessor and source comparison are preserved. The tested app/config
   source is identical across the actual alpha/stable runs.

5. **P3 — Some visible controls have narrower tested behavior.** Cookie Reset
   State is rendered but not exercised. Map fly-to commands are invoked and
   checked for browser errors, without asserting the exact final center.
   Reports explicitly retain these gaps rather than count them as acceptance.

6. **P3 — Cookie burst clicks do not prove request overlap.** The driver sends
   five sequential Playwright clicks and verifies the final paired values.
   This exercises repeated updates but does not capture request timestamps or
   establish that sync requests would have overlapped without the new chain.
   Treat it as functional burst coverage, not proof of all race conditions.

7. **P2 — Cookie cleanup can still lose partial diagnostics.** The driver's
   `finally` block takes a screenshot and reads the body before writing JSON.
   A closed/crashed page or screenshot failure can prevent evidence persistence.
   Current runs completed and saved all evidence. No helper fix followed review.

The original [campaign review](../../REVIEW.md), including the unchanged lexical
Free-tier credential-path helper limitation, still applies. This a3 Free-tier
run removes the historical app-directory exception: all app execution occurs
in neutral copies. Cookie, auth and component servers/fixtures are disposable,
with fictional values. Real entitlement, external IdPs, secure/partitioned
cookies, multi-worker/Redis enterprise auth and sustained production load were
not validated.
