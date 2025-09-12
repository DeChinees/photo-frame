#!/usr/bin/env bash
set -euo pipefail

# --- config you can tweak ---
SERVICE_WEB=photoframe-web.service
SERVICE_ADVANCE=photoframe-advance.service
TIMER_ADVANCE=photoframe-advance.timer
ADVANCE_CALENDAR="${ADVANCE_CALENDAR:-*:*:0/300}"  # every 5 minutes (OnCalendar format: second-level)
FRAME_TOKEN_DEFAULT="changeme123"
PYTHON_BIN="/usr/bin/python3"

# --- resolve paths ---
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"
WEB_PY="$REPO_DIR/webframe.py"
DISPLAY_PY="$REPO_DIR/display_image.py"

echo "==> Repo dir: $REPO_DIR"
echo "==> User: $(whoami)"

# --- apt dependencies ---
echo "==> Installing apt packages…"
sudo apt update
sudo apt install -y \
  python3-venv python3-dev python3-pip \
  python3-gpiozero \
  libjpeg62-turbo zlib1g libopenjp2-7 \
  libheif1 libheif-examples \
  avahi-daemon \
  raspi-config

# quick sanity: heif-convert present?
if ! command -v heif-convert >/dev/null 2>&1; then
  echo "!! heif-convert not found; HEIC uploads won't auto-convert. Did libheif-examples install?"
fi

# --- python venv ---
if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> Creating venv at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
else
  echo "==> Using existing venv at $VENV_DIR"
fi

echo "==> Upgrading pip & installing Python deps…"
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel

# Core deps for BOTH webframe.py and display_image.py
# - flask: web UI (remove if not used)
# - pillow: image handling
# - gpiozero, spidev, RPi.GPIO: GPIO/SPI stack for Waveshare drivers
# "$VENV_DIR/bin/pip" install \
#   flask \
#   pillow \
#   gpiozero \
#   spidev \
#   RPi.GPIO

"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/pip" install flask pillow gpiozero spidev RPi.GPIO
# optional, ignore failure:
"$VENV_DIR/bin/pip" install lgpio || true

# Try lgpio (preferred backend for gpiozero on newer Pi OS); ignore failure
if "$VENV_DIR/bin/pip " install lgpio >/dev/null 2>&1; then
  echo "==> lgpio installed"
else
  echo "==> lgpio unavailable; continuing with RPi.GPIO backend"
fi

# --- project folders ---
echo "==> Creating photos/ folder structure…"
mkdir -p \
  "$REPO_DIR/photos/photos_source" \
  "$REPO_DIR/photos/photos_ready" \
  "$REPO_DIR/photos/thumbs"

for d in photos/photos_source photos/photos_ready photos/thumbs; do
  [[ -f "$REPO_DIR/$d/.gitkeep" ]] || touch "$REPO_DIR/$d/.gitkeep"
done

# --- logging directory for Flask rotating logs ---
echo "==> Preparing log directory…"
sudo mkdir -p /var/log/photo-frame
sudo chown "$(whoami)":"$(id -gn)" /var/log/photo-frame

# --- sanity checks for app files ---
if [[ ! -f "$WEB_PY" ]]; then
  echo "!! $WEB_PY not found. Place webframe.py in the repo root."
  exit 1
fi
if [[ ! -f "$DISPLAY_PY" ]]; then
  echo "!! $DISPLAY_PY not found. Place display_image.py in the repo root."
  exit 1
fi

# --- enable SPI + add user to groups for device access ---
echo "==> Enabling SPI and adding user to gpio/spi/i2c groups…"
sudo raspi-config nonint do_spi 0 || true
sudo usermod -aG gpio,spi,i2c "$(whoami)" || true
echo "   NOTE: Log out/in or reboot once after this script so group changes take effect."

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
ExecStart=$VENV_DIR/bin/python $WEB_PY
Restart=always
StandardOutput=null
StandardError=null

[Install]
WantedBy=multi-user.target
UNIT

# --- systemd oneshot service for advancing display ---
UNIT_ADV_PATH="/etc/systemd/system/$SERVICE_ADVANCE"
echo "==> Writing $UNIT_ADV_PATH"
sudo tee "$UNIT_ADV_PATH" >/dev/null <<UNIT
[Unit]
Description=Photo Frame - render current image to e-paper and rotate symlink
After=network-online.target

[Service]
Type=oneshot
User=$(whoami)
WorkingDirectory=$REPO_DIR
ExecStart=$VENV_DIR/bin/python $DISPLAY_PY
# If your display script logs to stdout:
StandardOutput=journal
StandardError=journal
UNIT

# --- systemd timer to run the oneshot service periodically ---
TIMER_ADV_PATH="/etc/systemd/system/$TIMER_ADVANCE"
echo "==> Writing $TIMER_ADV_PATH (every 5 minutes by default)"
sudo tee "$TIMER_ADV_PATH" >/dev/null <<UNIT
[Unit]
Description=Run photoframe-advance periodically to update e-paper

[Timer]
OnCalendar=${ADVANCE_CALENDAR}
Persistent=true
AccuracySec=1s

[Install]
WantedBy=timers.target
UNIT

# --- reload & enable services ---
echo "==> Reloading systemd…"
sudo systemctl daemon-reload

echo "==> Enabling + starting web UI service…"
sudo systemctl enable --now "$SERVICE_WEB"

echo "==> Enabling + starting advance timer…"
sudo systemctl enable --now "$TIMER_ADVANCE"

echo "==> Web UI status:"
systemctl --no-pager --full status "$SERVICE_WEB" || true

echo "==> Advance timer status:"
systemctl --no-pager --full status "$TIMER_ADVANCE" || true

echo
echo "==> Done."
echo "Open:  http://photoframe.local:5000/"
echo "Token: ${FRAME_TOKEN_DEFAULT}  (change by editing $UNIT_WEB_PATH, then: sudo systemctl daemon-reload && sudo systemctl restart $SERVICE_WEB)"
echo "Advance: runs via systemd timer (${ADVANCE_CALENDAR}). To change interval:"
echo "  sudo systemctl edit $TIMER_ADVANCE   # set a new OnCalendar"
echo "  sudo systemctl daemon-reload && sudo systemctl restart $TIMER_ADVANCE"