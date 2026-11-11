# Sourced by the up/bin seq_*.sh scripts (in-place upgrades of reflex-examples apps).
# U = this sub-area's root ($W/up when staged); per-app scratch venvs $SB/envs/$VENV_PREFIX-<key>.
U=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
. "$U/../bin/env.sh"
mkdir -p "$U/logs" "$U/freeze" "$U/pkg" "$U/shots" "$U/ctl" "$U/run" "$U/profiles"
venv_of() { echo "$SB/envs/$VENV_PREFIX-$1"; }
summ() { grep -E '^\[(FAIL|ANOMALY)|^== |UNEXPECTED|PAGE ERROR|BAD REQ|verdict|VERDICT|restored|kept|no_writes' | cut -c1-260; }
upgrade() { # upgrade <venv-key> <tag> [reqs...]: in-place upgrade of the app's venv, freeze + diff + pip check
  local V; V=$(venv_of "$1"); shift; local tag=$1; shift
  uvq pip install --python "$V/bin/python" --prerelease=allow -U "$@" > "$U/logs/$tag-upgrade.install.log"
  uvq pip freeze --python "$V/bin/python" > "$U/freeze/$tag-up.txt"
  diff "$U/freeze/$tag-base.txt" "$U/freeze/$tag-up.txt" > "$U/freeze/$tag-base-to-up.diff"
  echo "freeze diff $tag: $(grep -E '^[<>]' "$U/freeze/$tag-base-to-up.diff" | tr '\n' ' ')"
  uvq pip check --python "$V/bin/python" | tail -2
}
pkgsnap() { "$U/../bin/web_pkg.sh" snap "$1" "$U/pkg/$2"; }          # pkgsnap <appdir> <label>
pkgdiff() { "$U/../bin/web_pkg.sh" diff "$U/pkg/$1" "$U/pkg/$2"; }  # pkgdiff <label-a> <label-b>
logscan() { grep -iE 'warn|error|traceback|exception|deprecat|mismatch|does not match' "$1" | grep -v -E 'incorrect peer|redis_lock_warning|react-error-boundary|errorBoundaries|SitemapPlugin|npmmirror' | sed -E 's/[0-9a-f]{8}-[0-9a-f-]{27}/<tok>/g' | cut -c1-200 | sort | uniq -c | sort -rn | head -12; }
