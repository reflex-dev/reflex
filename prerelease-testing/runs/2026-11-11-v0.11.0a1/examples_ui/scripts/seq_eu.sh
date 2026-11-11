#!/usr/bin/env bash
# examples_ui in-place upgrade sequence for one reflex-examples app (0.10.1 -> 0.11.0a1), reusing the staged
# upgrade fixtures ($W/up/bin/run_app.sh, stop_app.sh, web_pkg.sh, $W/up/scripts/drive_*.py).
# Usage: seq_eu.sh <app> <phase>...     phases: base upgrade up prod cold   (run in that order; any subset)
#   base     dev on the 0.10.1 venv, fresh .web/reflex.lock, fresh browser profile where the driver takes one
#   upgrade  uv pip install --prerelease=allow 'reflex==0.11.0a1' (NO -U) in the same venv; freeze diff + pip check
#   up       dev again, same dir/.web/reflex.lock/profile
#   prod     --env prod, single port $PP + REFLEX_API_URL
#   cold     rm -rf .web, dev
# Ports: FP/BP (3420/8420) dev, PP (default = FP, same origin for storage) prod, STUBP (8438) github stub.  Env: . $SB/apps/examples_ui/env_eu.sh
set -u
. "$(dirname "$0")/../env_eu.sh"
. "$W/up/bin/common.sh"   # U=$W/up, venv_of, pkgsnap, pkgdiff, logscan, summ, uvq
APP=$1; shift
A=$U/apps/$APP; V=$SB/envs/examples_ui-$APP
FP=${FP:-3420}; BP=${BP:-8420}; PP=${PP:-$FP}; STUBP=${STUBP:-8438}
L=$W/logs/$APP; S=$W/shots/$APP; PROF=$W/profiles/$APP; mkdir -p "$L" "$S" "$W/profiles"
UP_SPEC=${UP_SPEC:-reflex==0.11.0a1}
STUBPID=
cleanup() { [ -n "$STUBPID" ] && kill "$STUBPID" 2>/dev/null; }
trap cleanup EXIT
case $APP in
  github-stats)
    export QA_GITHUB_GRAPHQL_URL=http://127.0.0.1:$STUBP/graphql GITHUB_API_TOKEN=qa-dummy-token
    "$DPY" "$U/scripts/github_stub.py" "$STUBP" > "$L/stub.log" 2>&1 & STUBPID=$!; sleep 1 ;;
  upload) export QA_UPLOAD_EXTRAS=1; mkdir -p "$W/run/upload-fixtures" ;;
esac
drive() { # drive <url> <tag> <mode fresh|persist> [profile dir, default $PROF]
  local url=$1 tag=$2 mode=$3 prof=${4:-$PROF}
  case $APP in
    counter) $DRV "$U/scripts/drive_misc.py" counter "$url" "$S" "$tag" ;;
    github-stats) $DRV "$U/scripts/drive_github_stats.py" "$url" "$S" "$tag" "$mode" "$prof" "http://127.0.0.1:$STUBP" ;;
    reflexle) $DRV "$U/scripts/drive_reflexle.py" "$url" "$S" "$tag" ;;
    upload) $DRV "$U/scripts/drive_upload.py" "$url" "$S" "$tag" "$A/uploaded_files" "$W/run/upload-fixtures" ;;
    clock) $DRV "$U/scripts/drive_clock.py" "$url" "$S" "$tag" ;;
    quiz) $DRV "$U/scripts/drive_quiz.py" "$url" "$S" "$tag" ;;
    snakegame) $DRV "$U/scripts/drive_snakegame.py" "$url" "$S" "$tag" ;;
    lorem-stream) $DRV "$U/scripts/drive_lorem.py" "$url" "$S" "$tag" ;;
    overkey) $DRV "$W/eu/drive_overkey.py" "$url" "$S" "$tag" "$prof" ;;
    *) echo "no driver for $APP"; return 2 ;;
  esac > "$L/$tag.drive.txt" 2>&1
  echo "drive $tag rc=$?"; summ < "$L/$tag.drive.txt"
}
for ph in "$@"; do
  echo "### $APP $ph $(date +%T)"
  case $ph in
    base)
      rm -rf "$A/.web" "$A/reflex.lock" "$A/.states" "$PROF"
      "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$L/base.server.log" || exit 1
      drive http://localhost:$FP/ $APP-base fresh; pkgsnap "$A" $APP-base; "$U/bin/stop_app.sh" "$A" $FP $BP ;;
    upgrade)
      (cd "$SB" && uv --no-config pip install --python "$V/bin/python" --prerelease=allow "$UP_SPEC" ${UP_EXTRA:-}) > "$L/upgrade.install.log" 2>&1
      grep -E '^ [-+~] ' "$L/upgrade.install.log"
      (cd "$SB" && uv --no-config pip freeze --python "$V/bin/python" 2>/dev/null) > "$U/freeze/$APP-up.txt"
      diff "$U/freeze/$APP-base.txt" "$U/freeze/$APP-up.txt" > "$U/freeze/$APP-base-to-up.diff"
      (cd "$SB" && uv --no-config pip check --python "$V/bin/python" 2>&1 | grep -v UV_NATIVE | tail -3) ;;
    up)
      "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$L/up.server.log" || exit 1
      pkgsnap "$A" $APP-up; pkgdiff $APP-base $APP-up | cut -c1-300; "$DPY" -I "$W/eu/pkgjson_cmp.py" "$U/pkg/$APP-base.web.package.json" "$U/pkg/$APP-up.web.package.json"
      drive http://localhost:$FP/ $APP-up persist; "$U/bin/stop_app.sh" "$A" $FP $BP ;;
    prod)
      REFLEX_API_URL=http://localhost:$PP "$U/bin/run_app.sh" "$A" "$V" $PP $PP "$L/prod.server.log" --env prod || exit 1
      drive http://localhost:$PP/ $APP-prod persist; "$U/bin/stop_app.sh" "$A" $PP ;;
    baseprod)
      REFLEX_API_URL=http://localhost:$PP "$U/bin/run_app.sh" "$A" "$V" $PP $PP "$L/baseprod.server.log" --env prod || exit 1
      drive http://localhost:$PP/ $APP-baseprod persist; "$U/bin/stop_app.sh" "$A" $PP ;;
    cold)
      cp "$A/.web/package.json" "$L/pre-cold.package.json" 2>/dev/null; rm -rf "$A/.web"
      "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$L/cold.server.log" || exit 1
      pkgsnap "$A" $APP-cold; pkgdiff $APP-up $APP-cold | cut -c1-300; "$DPY" -I "$W/eu/pkgjson_cmp.py" "$U/pkg/$APP-up.web.package.json" "$U/pkg/$APP-cold.web.package.json"
      rm -rf "$PROF-cold"; drive http://localhost:$FP/ $APP-cold fresh "$PROF-cold"; "$U/bin/stop_app.sh" "$A" $FP $BP ;;
    *) echo "unknown phase $ph"; exit 2 ;;
  esac
done
for t in base baseprod up prod cold; do [ -f "$L/$t.server.log" ] && { echo "--- $APP-$t server-log warnings:"; logscan "$L/$t.server.log"; }; done
echo "### $APP done $(date +%T)"
