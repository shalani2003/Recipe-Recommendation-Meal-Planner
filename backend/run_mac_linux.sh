#!/usr/bin/env bash
cd "$(dirname "$0")"
[ -d venv ] || python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo
echo "Open  http://127.0.0.1:5000/login.html  in your browser"
echo
python app.py
