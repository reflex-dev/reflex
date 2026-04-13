#!/usr/bin/env bash
# Source this file to route npm/bun through Socket.dev Firewall (sfw).
# Usage: source scripts/sfw-shims/activate.sh
SHIM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-${(%):-%x}}")" && pwd)"
export PATH="$SHIM_DIR:$PATH"
export REFLEX_USE_SYSTEM_BUN=1
echo "sfw shims activated (npm=$(which npm), bun=$(which bun))"
