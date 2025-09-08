#!/usr/bin/env bash
set -euo pipefail

VENV="venv"

setup_venv() {
    if [ ! -d "$VENV" ]; then
        echo "[*] Creating virtual environment in $VENV..."
        python3 -m venv "$VENV"
        echo "[*] Upgrading pip..."
        "$VENV/bin/pip" install --upgrade pip
        echo "[*] Installing dependencies..."
        "$VENV/bin/pip" install Flask Pillow pillow-heif Werkzeug
    else
        echo "[*] Using existing virtual environment $VENV"
    fi
}

main() {
    setup_venv

    echo "[*] Starting server at http://localhost:5000"
    echo "[*] Default token: changeme123"
    exec "$VENV/bin/python" webframe.py
}

main "$@"