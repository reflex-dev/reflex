# Independent many-state frontend check

Use identical copies of the root lifecycle sample with published alpha 0.10.0a1
and stable 0.9.12 environments. Add 500, 1000, 1500 dormant state subclasses using
the sample's QA_EXTRA_STATES environment variable. Run production apps
sequentially on 3133/8133 (alpha self-hosted production server uses 3133).
Confirm HTTP HTML response, observe the rendered page in a real browser,
record page/console/network errors, and exercise a counter when hydration works.
Use CUA for independent visual observation at the failure and passing threshold.
No library fixes or source installations. Compare stable compilation and
frontend behavior rather than extrapolating from the server's SSR response.

Follow-up: verify the alpha's fresh default Bun installation under a neutral
`REFLEX_DIR=/private/tmp/reflex-pre-js-runtime-20261005`. The published wheel
declares Bun VERSION 1.4.2 and MIN_VERSION 1.4.0, so an existing 1.4.0 runtime is
accepted by design. Keep the global runtime untouched, log the official
download/install outcome, and rerun the 1,500-state case with the fresh runtime
if installation succeeds. Do not substitute source builds or patch the CLI.
