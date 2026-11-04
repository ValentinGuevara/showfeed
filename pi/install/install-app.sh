#!/usr/bin/env bash
# Install LIVEFRAME Python app to /opt/liveframe and enable systemd units.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${LIVEFRAME_TARGET:-/opt/liveframe}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

APP_USER="${LIVEFRAME_FORCE_USER:-pi}"

echo "==> Installing LiveFrame to $TARGET"
mkdir -p "$TARGET"
rsync -a --delete \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude 'config.yaml' \
  --exclude '.git' \
  "$ROOT/" "$TARGET/"

if [[ ! -f "$TARGET/config.yaml" ]]; then
  cp "$TARGET/config.example.yaml" "$TARGET/config.yaml"
  echo "Created $TARGET/config.yaml from example"
fi

python3 -m venv "$TARGET/.venv"
"$TARGET/.venv/bin/pip" install --upgrade pip
"$TARGET/.venv/bin/pip" install -r "$TARGET/requirements.txt"

chown -R "$APP_USER:$APP_USER" "$TARGET"

install -m 644 "$ROOT/install/liveframe-watcher.service" /etc/systemd/system/liveframe-watcher.service
install -m 644 "$ROOT/install/liveframe-api.service" /etc/systemd/system/liveframe-api.service

# Fix User= in units if not pi
if [[ "$APP_USER" != "pi" ]]; then
  sed -i "s/^User=pi/User=$APP_USER/; s/^Group=pi/Group=$APP_USER/" \
    /etc/systemd/system/liveframe-watcher.service \
    /etc/systemd/system/liveframe-api.service
fi

systemctl daemon-reload
systemctl enable liveframe-watcher liveframe-api
systemctl restart liveframe-watcher liveframe-api

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo ""
echo "==> App running"
echo "    Player:  http://${IP:-<pi-ip>}:8080/"
echo "    Health:  http://${IP:-<pi-ip>}:8080/api/health"
echo "    Status:  http://${IP:-<pi-ip>}:8080/api/status"
echo "    Logs:    journalctl -u liveframe-watcher -u liveframe-api -f"
