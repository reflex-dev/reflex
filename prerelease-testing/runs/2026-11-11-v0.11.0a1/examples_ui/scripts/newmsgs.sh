#!/usr/bin/env bash
# newmsgs.sh <logdir>: user-relevant server-log lines new after the upgrade (up vs base, prod vs baseprod, cold vs base)
D=$(cd "$(dirname "$0")" && pwd)
F='^Debug: \+ |packages installed|Running command|Spawning|Starting granian|PID|Reflex 0.1|Config: Config|accentColor|vite\]|Received response|Project hash|_flush_write_queue|\[<t>\] done|bun install v|Copying .*bun.lock|Installing base|build/|Debug: (- |✓|vite v|rendering|computing|transforming|Prerender|Using|Checking|Fullstack|Overriding|Creating|The slowest|Additional|See https|2 callbacks|Setting project hash|\[timing\])|PLUGIN_TIMINGS|App running|Listening at|^\[|react-router build'
cd "$1"; for t in up prod cold; do b=base; [ $t = prod ] && b=baseprod; [ -f $t.server.log ] && [ -f $b.server.log ] && { echo "--- new in $t vs $b:"; "$D/logdiff.sh" $b.server.log $t.server.log | grep -vE "$F" | cut -c1-400; }; done
