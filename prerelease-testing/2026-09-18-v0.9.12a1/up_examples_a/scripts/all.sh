#!/bin/bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
BASE=$SB/apps/up_examples_a
TAG=$1
declare -A DIRS=( [counter]=counter [todo]=todo [clock]=clock [upload]=upload [lorem-stream]=lorem-stream [snakegame]=snakegame )
for app in counter todo clock upload lorem-stream snakegame; do
  echo "##### $app / $TAG $(date -u +%H:%M:%S)"
  bash $BASE/scripts/run_app.sh $BASE/${DIRS[$app]} $app $TAG dev
  echo "##### $app / $TAG done rc=$? $(date -u +%H:%M:%S)"
done
