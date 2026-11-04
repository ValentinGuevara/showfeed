#!/usr/bin/env bash
# Install SHOWFEED Python app to /opt/showfeed and enable systemd units.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${SHOWFEED_TARGET:-/opt/showfeed}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

APP_USER="${SHOWFEED_FORCE_USER:-pi}"

echo "==> Installing ShowFeed to $TARGET"
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

install -m 644 "$ROOT/install/showfeed-watcher.service" /etc/systemd/system/showfeed-watcher.service
install -m 644 "$ROOT/install/showfeed-api.service" /etc/systemd/system/showfeed-api.service

# Fix User= in units if not pi
if [[ "$APP_USER" != "pi" ]]; then
  sed -i "s/^User=pi/User=$APP_USER/; s/^Group=pi/Group=$APP_USER/" \
    /etc/systemd/system/showfeed-watcher.service \
    /etc/systemd/system/showfeed-api.service
fi

systemctl daemon-reload
systemctl enable showfeed-watcher showfeed-api
systemctl restart showfeed-watcher showfeed-api

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo ""
echo "==> App running"
echo "    Player:  http://${IP:-<pi-ip>}:8080/"
echo "    Health:  http://${IP:-<pi-ip>}:8080/api/health"
echo "    Status:  http://${IP:-<pi-ip>}:8080/api/status"
echo "    Logs:    journalctl -u showfeed-watcher -u showfeed-api -f"
