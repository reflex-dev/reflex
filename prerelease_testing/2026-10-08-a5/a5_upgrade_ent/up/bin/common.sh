# sourced by the seq_*.sh scripts
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_upgrade_ent/up
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 900 $SB/envs/driver/bin/python"
summ() { grep -E '^\[(FAIL|ANOMALY)|^== |UNEXPECTED|PAGE ERROR|BAD REQ|verdict|VERDICT|restored|kept|no_writes' | cut -c1-260; }
upgrade() { # upgrade <venv-key> <tag> [reqs...]
  local V=$SB/envs/a5_upgrade_ent-$1; shift; local tag=$1; shift
  (cd $SB && uv --no-config pip install --python $V/bin/python --prerelease=allow -U "$@" 2>&1 | grep -v UV_NATIVE > $W/logs/$tag-upgrade.install.log)
  (cd $SB && uv --no-config pip freeze --python $V/bin/python 2>/dev/null > $W/freeze/$tag-up.txt)
  diff $W/freeze/$tag-base.txt $W/freeze/$tag-up.txt > $W/freeze/$tag-base-to-up.diff
  echo "freeze diff $tag: $(grep -E '^[<>]' $W/freeze/$tag-base-to-up.diff | tr '\n' ' ')"
  (cd $SB && uv --no-config pip check --python $V/bin/python 2>&1 | grep -v UV_NATIVE | tail -2)
}
pkgsnap() { # pkgsnap <appdir> <label>
  cp $1/.web/package.json $W/pkg/$2.web.package.json
  (cd $1 && find .web -path .web/node_modules -prune -o -type f -print | grep -v -E '\.web/(build|\.react-router|backend)/' | sort) > $W/pkg/$2.web.files
  (ls -la --time-style=+%T $1/reflex.lock 2>/dev/null; sha256sum $1/reflex.lock/* 2>/dev/null) > $W/pkg/$2.reflex.lock.ls
}
logscan() { grep -iE 'warn|error|traceback|exception|deprecat|mismatch|does not match' $1 | grep -v -E 'incorrect peer|redis_lock_warning|react-error-boundary|errorBoundaries|SitemapPlugin|npmmirror' | sed -E 's/[0-9a-f]{8}-[0-9a-f-]{27}/<tok>/g' | cut -c1-200 | sort | uniq -c | sort -rn | head -12; }
