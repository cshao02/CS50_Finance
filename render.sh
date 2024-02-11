#!/usr/bin/env bash
# exit on error
set -o errexit

export FLASK_APP=app.py
pip install -r requirements.txt
export API_KEY=pk_e46347831c69417cb9db6e6878707c5d
