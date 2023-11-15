#!/usr/bin/env bash

set -ex

echo "Preparing test project dir"
mkdir hello
python3 -m venv ~/hello/venv
source ~/hello/venv/bin/activate

echo "Installing nextpy from local repo code"
cd /nextpy-repo
poetry install
echo "Running nextpy init in test project dir"
export TELEMETRY_ENABLED=false
poetry run /bin/bash -c "cd ~/hello && nextpy init --template blank && rm -rf ~/.nextpy .web && nextpy export --backend-only"