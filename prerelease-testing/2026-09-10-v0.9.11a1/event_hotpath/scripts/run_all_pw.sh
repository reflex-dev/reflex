#!/bin/bash
# Full sequential end-to-end pass (one server at a time, ports 3180-3199/8180-8199). ~20 min.
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/event_hotpath
S=$A/scripts
export LOGDIR=logs3
t() { echo; echo "##### $(date +%T) $*"; }
t hotpath smoke py3.11 dev;        $S/run_pw.sh smoke hotpath_app 3180 8180 smoke
t hotpath 0.9.11a1 py3.13 dev;     $S/run_pw.sh hp313 hotpath_app_313 3181 8181 hp313
t hotpath 0.9.10.post2 py3.11 dev; $S/run_pw.sh base0910 hotpath_app_base 3182 8182 base
t hotpath 0.9.10.post2 py3.13 dev; $S/run_pw.sh hp313_base hotpath_app_313_base 3183 8183 base313
t hotpath py3.13 + custom task factory;  HP_TASK_FACTORY=1 $S/run_pw.sh hp313 hotpath_app_313 3184 8184 hp313_factory --only ordering,hier,slow,hammer
t hotpath smoke + backend var _get_was_touched; HP_GWT=1 $S/run_pw.sh smoke hotpath_app 3185 8185 smoke_gwt --only backend
t routes smoke dev;                $S/run_routes.sh smoke routes_app 3186 8186 smoke_dev ''
t routes smoke dev frontend_path=/app; $S/run_routes.sh smoke routes_app 3187 8187 smoke_dev_fp /app
t routes base dev frontend_path=/app;  $S/run_routes.sh base0910 routes_app_base 3188 8188 base_dev_fp /app
t socket hp313;                    $S/run_socket.sh hp313 hotpath_app_313 hp313
t socket base313;                  $S/run_socket.sh hp313_base hotpath_app_313_base base313
t socket smoke;                    $S/run_socket.sh smoke hotpath_app smoke
echo; echo "ALL PW DONE $(date +%T)"
