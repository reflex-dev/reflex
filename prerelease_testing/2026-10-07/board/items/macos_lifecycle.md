# item: macos_lifecycle
ports: frontend 3660-3679 / backend 8660-8679
status: open
artifacts: prerelease_testing/2026-10-07/macos_lifecycle/
covers: Native macOS arm64 published-package startup, paths with spaces, browser event smoke, reload, and graceful SIGTERM under npm (F-007), compared with 0.9.12 and 0.10.0a1.

Follow COORDINATION.md and AGENT_BRIEF.md. Keep all environments outside the checkout and use published packages only. Record exact commands, process trees, cleanup status, logs, browser console/network and screenshots. Parent session handles commits and board updates. Do not fix framework code.
