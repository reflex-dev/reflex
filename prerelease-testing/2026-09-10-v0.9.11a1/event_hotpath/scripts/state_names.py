"""Print the full event names of the hotpath app's handlers as JSON (run with cwd = hotpath_app dir)."""
import json
import sys

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__
sys.path.insert(0, ".")
from hotpath_app.hotpath_app import CounterState, SlowState  # noqa: E402

print(json.dumps({
    "version": rx.constants.Reflex.VERSION,
    "counter": CounterState.get_full_name(),
    "increment": f"{CounterState.get_full_name()}.increment",
    "reset_count": f"{CounterState.get_full_name()}.reset_count",
    "slow_state": SlowState.get_full_name(),
    "slow": f"{SlowState.get_full_name()}.slow",
    "fast": f"{SlowState.get_full_name()}.fast",
    "boom": f"{SlowState.get_full_name()}.boom",
}))
