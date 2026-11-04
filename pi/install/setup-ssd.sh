#!/usr/bin/env bash
# Mount USB SSD at /media/liveframe and create inbox/approved/hold/archive.
set -euo pipefail

MOUNT_POINT="${LIVEFRAME_MOUNT:-/media/liveframe}"
LABEL="${LIVEFRAME_SSD_LABEL:-LIVEFRAME}"
FSTAB="/etc/fstab"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

echo "==> LiveFrame SSD setup"
echo "    Mount point: $MOUNT_POINT"
echo "    Looking for filesystem LABEL=$LABEL (or pass DEVICE=/dev/sdX1)"

mkdir -p "$MOUNT_POINT"

DEVICE="${DEVICE:-}"
if [[ -z "$DEVICE" ]]; then
  if [[ -e "/dev/disk/by-label/$LABEL" ]]; then
    DEVICE="/dev/disk/by-label/$LABEL"
  else
    echo "No device with label $LABEL found."
    echo "Format example (DESTROYS DATA):"
    echo "  sudo mkfs.ext4 -L $LABEL /dev/sdX1"
    echo "Or: DEVICE=/dev/sda1 sudo $0"
    exit 1
  fi
fi

UUID="$(blkid -s UUID -o value "$DEVICE" || true)"
if [[ -z "$UUID" ]]; then
  echo "Could not read UUID for $DEVICE" >&2
  exit 1
fi

if ! mountpoint -q "$MOUNT_POINT"; then
  mount "$DEVICE" "$MOUNT_POINT" || mount UUID="$UUID" "$MOUNT_POINT"
fi

for d in inbox approved hold archive; do
  mkdir -p "$MOUNT_POINT/$d"
done

# Camera / samba friendly perms (adjust user if needed)
chown -R pi:pi "$MOUNT_POINT" 2>/dev/null || chown -R "${SUDO_USER:-root}:${SUDO_USER:-root}" "$MOUNT_POINT"
chmod -R u+rwX,g+rwX,o+rX "$MOUNT_POINT"
# Sticky write for inbox group later
chmod 2775 "$MOUNT_POINT/inbox" || true

FSTAB_LINE="UUID=$UUID $MOUNT_POINT ext4 defaults,nofail,x-systemd.device-timeout=10 0 2"
if grep -q "$MOUNT_POINT" "$FSTAB" 2>/dev/null; then
  echo "fstab already mentions $MOUNT_POINT — check manually."
else
  echo "$FSTAB_LINE" >> "$FSTAB"
  echo "Added to fstab:"
  echo "  $FSTAB_LINE"
fi

echo "==> Done. Tree:"
find "$MOUNT_POINT" -maxdepth 1 -type d | sort
