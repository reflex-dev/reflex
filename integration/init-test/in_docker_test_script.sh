#!/usr/bin/env bash

set -ex

echo "Preparing test project dir"
mkdir hello
python3 -m venv ~/hello/venv
source ~/hello/venv/bin/activate

echo "Installing reflex from local repo code"
cd /reflex-repo
poetry install
echo "Running reflex init in test project dir"
poetry run /bin/bash -c "cd ~/hello && reflex init"
