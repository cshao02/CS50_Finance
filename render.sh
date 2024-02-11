#!/usr/bin/env bash
# exit on error
set -o errexit

export FLASK_APP=app.py
pip install -r requirements.txt
