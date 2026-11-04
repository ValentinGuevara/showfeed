#!/usr/bin/env bash
# Samba share for Lumix GH6 "Send images to PC" → inbox on SSD.
set -euo pipefail

MOUNT_POINT="${LMW_MOUNT:-/media/lmw}"
SHARE_NAME="${LMW_SHARE:-lmw}"
SAMBA_USER="${LMW_SAMBA_USER:-wall}"
WORKGROUP="${LMW_WORKGROUP:-WORKGROUP}"
HOSTNAME_SHORT="${LMW_HOSTNAME:-regie}"
FORCE_USER="${LMW_FORCE_USER:-pi}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

echo "==> Live Memory Wall Samba setup"
echo "    Share: //$HOSTNAME_SHORT/$SHARE_NAME → $MOUNT_POINT/inbox"
echo "    User:  $SAMBA_USER  Workgroup: $WORKGROUP"

apt-get update -qq
apt-get install -y -qq samba samba-common-bin

hostnamectl set-hostname "$HOSTNAME_SHORT" || true
if grep -q '^127.0.1.1' /etc/hosts; then
  sed -i "s/^127.0.1.1.*/127.0.1.1\t$HOSTNAME_SHORT/" /etc/hosts
else
  echo -e "127.0.1.1\t$HOSTNAME_SHORT" >> /etc/hosts
fi

INBOX="$MOUNT_POINT/inbox"
mkdir -p "$INBOX"

if ! id "$SAMBA_USER" &>/dev/null; then
  useradd --system --create-home --home-dir "/home/$SAMBA_USER" --shell /usr/sbin/nologin "$SAMBA_USER" || true
fi

if id "$FORCE_USER" &>/dev/null; then
  usermod -aG "$SAMBA_USER" "$FORCE_USER" || true
  chown -R "$FORCE_USER:$SAMBA_USER" "$MOUNT_POINT"
else
  chown -R "$SAMBA_USER:$SAMBA_USER" "$MOUNT_POINT"
fi
chmod -R g+rwX "$MOUNT_POINT"
chmod 2775 "$INBOX"

# Workgroup + allow older SMB for cameras
if grep -q '^\s*workgroup\s*=' /etc/samba/smb.conf; then
  sed -i "s/^\s*workgroup\s*=.*/   workgroup = $WORKGROUP/" /etc/samba/smb.conf
else
  sed -i "/^\[global\]/a\\   workgroup = $WORKGROUP" /etc/samba/smb.conf
fi
if ! grep -q 'server min protocol' /etc/samba/smb.conf; then
  sed -i "/^\[global\]/a\\   server min protocol = NT1" /etc/samba/smb.conf
fi

if ! grep -q "^\[$SHARE_NAME\]" /etc/samba/smb.conf; then
  cat >> /etc/samba/smb.conf <<EOF

# --- Live Memory Wall ---
[$SHARE_NAME]
   path = $INBOX
   browseable = yes
   writable = yes
   read only = no
   force user = $FORCE_USER
   force group = $SAMBA_USER
   create mask = 0664
   directory mask = 0775
   valid users = $SAMBA_USER $FORCE_USER
EOF
else
  echo "Share [$SHARE_NAME] already present in smb.conf — skipping append."
fi

echo "Set Samba password for user '$SAMBA_USER' (Lumix will ask for it):"
smbpasswd -a "$SAMBA_USER"

systemctl enable smbd nmbd
systemctl restart smbd nmbd

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo ""
echo "==> Samba ready"
echo "    Host (NetBIOS): $HOSTNAME_SHORT"
echo "    IP:             ${IP:-unknown}"
echo "    Share:          $SHARE_NAME"
echo "    Path:           $INBOX"
echo ""
echo "GH6: Wi-Fi → Send Images → PC → Via Network → $HOSTNAME_SHORT → $SHARE_NAME"
echo "     (user: $SAMBA_USER / the password you just set)"
