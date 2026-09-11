import sys
assert "/envs/smoke/" in sys.executable, sys.executable
import click
from reflex_cli.utils import log, output

seen = {}
_orig = output._resolve_interactive
def spy(ctx, param, value):
    seen["reserved_at_resolve"] = log.is_stdout_reserved()
    seen["json_requested"] = output.json_requested(sys.argv[1:])
    r = _orig(ctx, param, value)
    seen["resolved"] = r
    return r

@click.command()
@output.json_option
@click.option("--interactive/--no-interactive", "-i/", "interactive", default=None,
              callback=spy)
def cmd(as_json, interactive):
    print(seen, file=sys.stderr)

cmd(standalone_mode=False)
