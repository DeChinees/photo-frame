#!/usr/bin/env bash
# Run the display_next.py script in local dev or Pi environment.

set -e

# Ensure venv exists
if [ ! -d "venv" ]; then
  echo "[*] Creating virtual environment venv"
  python3 -m venv venv
fi

# Activate
source venv/bin/activate

# Install requirements if needed
if [ -f "requirements.txt" ]; then
  echo "[*] Ensuring dependencies are installed"
  pip install -r requirements.txt
fi

echo "[*] Running display_image.py"
python display_image.py