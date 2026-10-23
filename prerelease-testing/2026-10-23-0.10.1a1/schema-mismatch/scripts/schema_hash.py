"""Print the backend's frontend-schema hash for schemaapp under the current SCHEMA_VARIANT.

Run from an app dir (schemaapp/):
    SCHEMA_VARIANT=var REFLEX_TELEMETRY_ENABLED=false $SB/envs/shared/bin/python ../scripts/schema_hash.py

Note: this hashes the tree before pages are evaluated, so ComponentState substates
created by page functions (Tile) are missing and the value differs from the compiled
`stateSchema` (d29adae5...). It is still useful to see which variants change the hash.
"""
import os
import sys

import reflex

assert "/tmp/claude-0/-home-user-reflex/7eb9e30f-e96c-5de5-9b0e-4a12be91e0f3/scratchpad/prt/envs/" in reflex.__file__, reflex.__file__

sys.path.insert(0, os.getcwd())
import schemaapp.schemaapp as m  # noqa: E402

root = m.app._state or m.State
print(os.environ.get("SCHEMA_VARIANT", "") or "baseline", root._to_frontend_schema())
