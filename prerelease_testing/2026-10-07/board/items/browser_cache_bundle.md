# item: browser_cache_bundle
ports: frontend 3700-3739 / backend 8700-8739
status: open
artifacts: prerelease_testing/2026-10-07/browser_cache_bundle/
covers: macOS Chromium/WebKit production bundle and actual browser payload comparisons; warm/cold navigation; memo/package cache invalidation on reload/rebuild; realistic computed/nested state mutation and session isolation across 0.9.12, 0.10.0a1, 0.10.0a2

Plan: use only published isolated environments. Separate static raw/gzip bundle bytes from observed network transfer bytes. Exercise the same realistic app and controls across versions, test functional behavior alongside size, record console/network/websocket evidence, and independently verify serious findings. No timing performance claims under concurrent load. High severity requires a realistic application workflow. Parent owns Git; subagents own disjoint subdirectories and port slices.
