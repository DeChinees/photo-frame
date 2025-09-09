#!/usr/bin/env bash
set -euo pipefail

# --- config you can tweak ---
SERVICE_WEB=photoframe-web.service
FRAME_TOKEN_DEFAULT="changeme123"
PYTHON_BIN="/usr/bin/python3"

# --- resolve paths ---
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"
WEB_PY="$REPO_DIR/webframe.py"

echo "==> Repo dir: $REPO_DIR"
echo "==> User: $(whoami)"

# --- apt dependencies ---
echo "==> Installing apt packages…"
sudo apt update
sudo apt install -y python3-venv python3-dev libheif1 libheif-dev libjpeg62-turbo \
                    avahi-daemon

# --- python venv ---
if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> Creating venv at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
echo "==> Upgrading pip & installing Python deps…"
"$VENV_DIR/bin/pip" install --upgrade pip wheel
"$VENV_DIR/bin/pip" install flask pillow pillow-heif

# --- data folders ---
echo "==> Creating data folders…"
mkdir -p "$REPO_DIR/photos/photos_source" \
         "$REPO_DIR/photos/photos_ready" \
         "$REPO_DIR/photos/thumbs"
         
# --- sanity check ---
if [[ ! -f "$WEB_PY" ]]; then
  echo "!! $WEB_PY not found. Please place webframe.py in the repo root."
  exit 1
fi

# --- systemd unit ---
UNIT_WEB_PATH="/etc/systemd/system/$SERVICE_WEB"

echo "==> Writing $UNIT_WEB_PATH"
sudo tee "$UNIT_WEB_PATH" >/dev/null <<UNIT
[Unit]
Description=Photo Frame Web UI (uploads + conversion)
After=network-online.target

[Service]
User=$(whoami)
WorkingDirectory=$REPO_DIR
# Token for upload actions (header or hidden field)
Environment=FRAME_TOKEN=${FRAME_TOKEN_DEFAULT}
ExecStart=$VENV_DIR/bin/python $WEB_PY
Restart=always

[Install]
WantedBy=multi-user.target
UNIT

# --- reload & enable services ---
echo "==> Reloading systemd…"
sudo systemctl daemon-reload

echo "==> Enabling + starting web UI service…"
sudo systemctl enable --now "$SERVICE_WEB"

echo "==> Web UI status:"
systemctl --no-pager --full status "$SERVICE_WEB" || true

echo
echo "==> Done."
echo "Open:  http://photoframe.local:5000/"
echo "Token: ${FRAME_TOKEN_DEFAULT}  (change it by editing $UNIT_WEB_PATH and restarting the service)"