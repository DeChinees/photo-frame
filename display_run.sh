#!/usr/bin/env bash
set -euo pipefail

VENV="venv"

main() {
    echo "[*] Running display_image.py"
    exec "$VENV/bin/python" display_image.py
}

main "$@"