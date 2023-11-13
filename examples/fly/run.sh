#!/bin/bash

echo "Starting Redis Server"
sudo service redis-server start

cd $PROJ_DIR

echo "Running poetry installs"
poetry init -n
#poetry add git+https://github.com/reflex-dev/reflex.git#main
poetry run pip install reflex==0.3.0a6

# Install Requirements
echo "Installing requirements"
poetry run pip install -r requirements.txt


# Run the project
echo "Running Pynecone App"
poetry run python3 config_setup.py
