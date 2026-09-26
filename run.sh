#!/usr/bin/env bash
# Quick launcher for the Intelligent Code Reviewer & Explainer.
set -e
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi
# shellcheck disable=SC1091
source venv/bin/activate
pip install -q -r requirements.txt

if [ -f ".env" ]; then
  set -a; source .env; set +a
fi

echo ""
echo "=== Demo: reviewing samples/buggy_example.py (offline engine) ==="
python -m reviewer review samples/buggy_example.py
echo ""
echo "Tip: python -m reviewer review <your-file> --engine gemini --save"
echo "     Web UI: python web/app.py  ->  http://127.0.0.1:5054"
