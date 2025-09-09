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
sudo apt install -y \
  python3-venv python3-dev libjpeg62-turbo \
  libheif1 libheif-examples \
  avahi-daemon

# quick sanity: heif-convert present?
if ! command -v heif-convert >/dev/null 2>&1; then
  echo "!! heif-convert not found; HEIC uploads won't auto-convert. Did libheif-examples install?"
fi

# --- python venv ---
if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> Creating venv at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
echo "==> Upgrading pip & installing Python deps…"
"$VENV_DIR/bin/pip" install --upgrade pip wheel
"$VENV_DIR/bin/pip" install flask pillow

# --- project folders ---
echo "==> Creating photos/ folder structure…"
mkdir -p \
  "$REPO_DIR/photos/photos_source" \
  "$REPO_DIR/photos/photos_ready" \
  "$REPO_DIR/photos/thumbs"

# (optional) keep empty dirs in git
for d in photos/photos_source photos/photos_ready photos/thumbs; do
  [[ -f "$REPO_DIR/$d/.gitkeep" ]] || touch "$REPO_DIR/$d/.gitkeep"
done

# --- logging directory for Flask rotating logs ---
echo "==> Preparing log directory…"
sudo mkdir -p /var/log/photo-frame
sudo chown "$(whoami)":"$(id -gn)" /var/log/photo-frame

# --- sanity check for app file ---
if [[ ! -f "$WEB_PY" ]]; then
  echo "!! $WEB_PY not found. Place webframe.py in the repo root."
  exit 1
fi

# --- systemd unit for web ui ---
UNIT_WEB_PATH="/etc/systemd/system/$SERVICE_WEB"

echo "==> Writing $UNIT_WEB_PATH"
sudo tee "$UNIT_WEB_PATH" >/dev/null <<UNIT
[Unit]
Description=Photo Frame Web UI (uploads + conversion)
After=network-online.target

[Service]
User=$(whoami)
WorkingDirectory=$REPO_DIR
Environment=FRAME_TOKEN=${FRAME_TOKEN_DEFAULT}
# Use the venv python so site-packages resolve correctly
ExecStart=$VENV_DIR/bin/python $WEB_PY
Restart=always
# If you configured RotatingFileHandler in webframe.py, send stdout/stderr nowhere:
StandardOutput=null
StandardError=null

[Install]
WantedBy=multi-user.target
UNIT

# --- reload & enable service ---
echo "==> Reloading systemd…"
sudo systemctl daemon-reload

echo "==> Enabling + starting web UI service…"
sudo systemctl enable --now "$SERVICE_WEB"

echo "==> Web UI status:"
systemctl --no-pager --full status "$SERVICE_WEB" || true

echo
echo "==> Done."
echo "Open:  http://photoframe.local:5000/"
echo "Token: ${FRAME_TOKEN_DEFAULT}  (change by editing $UNIT_WEB_PATH, then: sudo systemctl daemon-reload && sudo systemctl restart $SERVICE_WEB)"