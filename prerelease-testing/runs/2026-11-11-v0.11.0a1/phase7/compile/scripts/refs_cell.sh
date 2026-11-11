#!/usr/bin/env bash
# refs_cell.sh <label> <venv> <appdir> <dev|prod> <AM true|false> <RC true|false>
set -u
W=$OLDSB/p7/work/cm; OLDSB=$OLDSB
label=$1; venv=$2; app=$3; mode=$4; am=$5; rc=$6
if [ $mode = prod ]; then bp=3300; else bp=8300; fi
EXPECT_VENV=$venv bash $W/scripts/srv.sh start $label $venv $mode $app 3300 $bp REFLEX_AUTO_MEMOIZE=$am REFLEX_REACT_COMPILER=$rc || { bash $W/scripts/srv.sh stop $label; exit 1; }
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $OLDSB/p7/envs/driver/bin/python -I $W/scripts/drive_refs.py http://localhost:3300 $W/results/shots/$label > $W/results/$label.json 2>&1
bash $W/scripts/srv.sh stop $label
python3 -I -c "import json,sys; d=json.load(open(sys.argv[1])); print(sys.argv[2], {k:v for k,v in d.items() if k in ('raw_handler_value','call_function_log','hook_value','memo_value','decl_value')}, 'fnmemo=', d.get('memo_text','')[:60], 'errors=', d['errors'][:4])" $W/results/$label.json $label
