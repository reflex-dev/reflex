#!/usr/bin/env bash

set -euxo pipefail

export TELEMETRY_ENABLED=false

function do_export () {
    template=$1
    mkdir ~/"$template"
    cd ~/"$template"
    rm -rf ~/.local/share/reflex ~/"$template"/.web
    reflex init --template "$template"
    reflex export
}

echo "Preparing test project dir"
python3 -m venv ~/venv
source ~/venv/bin/activate

echo "Installing reflex from local repo code"
pip install /reflex-repo

echo "Running reflex init in test project dir"
do_export blank
do_export sidebar