"""Read duration settings repeatedly from ordinary and generated user code."""

import argparse
import json
import os
import sys

import reflex as rx
from reflex_base import environment

assert f"/envs/{os.environ['REFLEX_TEST_ENV']}/" in rx.__file__, rx.__file__


def main():
    """Evaluate duration settings without starting a server.

    Returns:
        Zero on accepted configuration or one on a configuration error.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--setting", choices=("debounce", "cooldown"), default="debounce"
    )
    parser.add_argument("--generated", action="store_true")
    args = parser.parse_args()
    helper = getattr(
        environment,
        "state_manager_disk_debounce"
        if args.setting == "debounce"
        else "auto_reload_cooldown",
        None,
    )
    result = {
        "reflex_file": rx.__file__,
        "python": sys.version,
        "pid": os.getpid(),
        "setting": args.setting,
        "generated": args.generated,
    }
    try:
        if helper is None:
            result["legacy_seconds"] = (
                environment.environment.REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS.get()
            )
        else:
            values = []
            for _ in range(3):
                if args.generated:
                    namespace = {"helper": helper}
                    exec(compile("result = helper()", "<string>", "exec"), namespace)
                    value = namespace["result"]
                else:
                    value = helper()
                values.append(value.total_seconds())
            result["seconds"] = values
        if args.setting == "debounce":
            app = rx.App()
            result["manager"] = type(app.state_manager).__name__
            result["manager_debounce_seconds"] = (
                app.state_manager._write_debounce_seconds
            )
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    print("QA_DURATION_RESULT=" + json.dumps(result), flush=True)
    return int("error" in result)


if __name__ == "__main__":
    sys.exit(main())
