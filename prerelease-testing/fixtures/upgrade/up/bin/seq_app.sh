#!/usr/bin/env bash
# Generic in-place upgrade sequence for the smaller reflex-examples apps: BASE_VERSION baseline -> upgrade -> up -> cold,
# same driver each time. Usage: seq_app.sh <app>   (venv: build_base_venvs.sh <app>:<app>; ports FP/BP, default 3504/8504)
#   counter | traversal | json-tree -> drive_misc.py <app>     reflexle -> drive_reflexle.py      lorem-stream -> drive_lorem.py
#   local-component -> drive_local_component.py                 quiz -> drive_quiz.py              snakegame -> drive_snakegame.py
#   nba -> drive_nba.py (server env QA_NBA_EXTRAS=1, patch nba-qa-stub-and-extras.diff)
#   todo -> drive_examples_legacy.py todo (0.9.12a1 driver; not re-run since)
#   upload -> drive_upload.py <upload_dir> <fixtures_dir> (server env QA_UPLOAD_EXTRAS=1, patch upload-qa-extras.diff)
set -u; . "$(dirname "$0")/common.sh"
APP=$1; A=$U/apps/$APP; V=$(venv_of "$APP"); FP=${FP:-3504}; BP=${BP:-8504}; S=$U/shots/$APP; mkdir -p "$S"
case $APP in
  counter|traversal|json-tree) DRIVE=(drive_misc.py "$APP") ;;
  reflexle) DRIVE=(drive_reflexle.py) ;; lorem-stream) DRIVE=(drive_lorem.py) ;; local-component) DRIVE=(drive_local_component.py) ;;
  quiz) DRIVE=(drive_quiz.py) ;; snakegame) DRIVE=(drive_snakegame.py) ;; nba) DRIVE=(drive_nba.py); export QA_NBA_EXTRAS=1 ;;
  upload) DRIVE=(drive_upload.py); export QA_UPLOAD_EXTRAS=1; mkdir -p "$U/run/upload-fixtures"; EXTRA=("$A/uploaded_files" "$U/run/upload-fixtures") ;;
  todo) DRIVE=(drive_examples_legacy.py todo) ;;
  *) echo "unknown app $APP"; exit 2 ;;
esac
drive() { # drive <tag>
  local first=${DRIVE[0]} rest=("${DRIVE[@]:1}")
  if [ "$first" = drive_misc.py ]; then (cd "$U" && $DRV "$U/scripts/$first" "${rest[@]}" http://localhost:$FP/ "$S" "$1" | summ)
  elif [ "$first" = drive_examples_legacy.py ]; then (cd "$U" && $DRV "$U/scripts/$first" "${rest[@]}" http://localhost:$FP/ "$1" "$S" | tail -5)
  else (cd "$U" && $DRV "$U/scripts/$first" http://localhost:$FP/ "$S" "$1" ${EXTRA[@]+"${EXTRA[@]}"} | summ); fi
}
rm -rf "$A/.web" "$A/reflex.lock" "$A/.states"
echo "### $APP base $BASE_VERSION"; "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/$APP-base.server.log" || exit 1
drive $APP-base; pkgsnap "$A" $APP-base; "$U/bin/stop_app.sh" "$A" $FP $BP
echo "### $APP upgrade -> $NEW_VERSION"; upgrade "$APP" "$APP" "reflex==$NEW_VERSION" ${UP_EXTRA:-}
echo "### $APP up"; "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/$APP-up.server.log" || exit 1
pkgsnap "$A" $APP-up; pkgdiff $APP-base $APP-up; drive $APP-up; "$U/bin/stop_app.sh" "$A" $FP $BP
echo "### $APP cold"; rm -rf "$A/.web"; "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/$APP-cold.server.log" || exit 1
pkgsnap "$A" $APP-cold; pkgdiff $APP-up $APP-cold; drive $APP-cold; "$U/bin/stop_app.sh" "$A" $FP $BP
for t in base up cold; do echo "--- $APP-$t server-log warnings:"; logscan "$U/logs/$APP-$t.server.log"; done
