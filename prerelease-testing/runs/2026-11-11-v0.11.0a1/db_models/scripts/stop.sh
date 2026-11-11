#!/bin/bash
APP=$1
PG=$(cat $APP/.pgid 2>/dev/null) || exit 0
kill -INT -- -$PG 2>/dev/null; sleep 4; kill -9 -- -$PG 2>/dev/null; rm -f $APP/.pgid; echo stopped $PG
