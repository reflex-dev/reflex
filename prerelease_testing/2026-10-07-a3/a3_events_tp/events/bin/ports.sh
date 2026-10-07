#!/bin/bash
# Usage: ports.sh -- list listeners in the cluster's reserved ranges (3460-3479, 8460-8479); `ss` is not installed here.
lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -E ':(34[67][0-9]|84[67][0-9]) ' || echo "ports clear"
