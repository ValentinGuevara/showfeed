# Live Memory Wall — Raspberry Pi V1

Receives media from a Lumix GH6 over **Samba**, stores it on a **USB SSD**, runs basic **triage**, and serves an **HTTP playlist + fullscreen player** for Fire TV / browsers.

```
GH6 --Wi‑Fi SMB--> Pi Samba --> /media/lmw/inbox
                                  │
                              watcher
                             ╱        ╲
                      approved         hold
                          │
                     HTTP :8080  -->  Fire TV / Chrome
```

## Contents

| Path | Role |
|---|---|
| `lmw/` | Watcher, triage, API, player HTML |
| `config.example.yaml` | Copy to `config.yaml` |
| `install/setup-ssd.sh` | Mount SSD at `/media/lmw` |
| `install/setup-samba.sh` | Share `lmw`, user `wall`, hostname `regie` |
| `install/install-app.sh` | Install to `/opt/lmw` + systemd units |
| `scripts/smoke_test.sh` | Local test without Pi hardware |

## Install on the Pi (order)

### 1. SSD

Format a partition as ext4 with label `LMW` (once):

```bash
# WARNING: destroys data — use the correct /dev/sdX1
sudo mkfs.ext4 -L LMW /dev/sda1
sudo ./install/setup-ssd.sh
```

### 2. Samba (GH6)

```bash
sudo ./install/setup-samba.sh
# Set the Samba password for user wall when prompted
```

| Setting | Value |
|---|---|
| NetBIOS hostname | `regie` |
| Share | `lmw` → `/media/lmw/inbox` |
| User | `wall` |

### 3. App + services

```bash
sudo ./install/install-app.sh
```

| Endpoint | URL |
|---|---|
| Player | `http://<pi-ip>:8080/` |
| Health | `http://<pi-ip>:8080/api/health` |
| Status | `http://<pi-ip>:8080/api/status` |
| Playlist | `http://<pi-ip>:8080/api/playlist` |

Logs:

```bash
journalctl -u lmw-watcher -u lmw-api -f
```

## GH6 configuration

1. Same dedicated Wi‑Fi as the Pi  
2. **Wi‑Fi Function** → **New Connection** → **Send Images While Recording** (or *Stored*) → **PC**  
3. **Via Network** → host `regie` (or Pi IP)  
4. Folder / share `lmw`  
5. User `wall` + Samba password  
6. Prefer JPEG for live; short 1080p MP4/MOV clips are fine  

If the camera says destination not found: wait ~15 s, check `nmbd`, retry. Lumix PC transfer does **not** auto-resume after power-on — re-enable it at the start of the event.

## Triage rules (V1)

| Rule | Result |
|---|---|
| Extension outside `.jpg` `.jpeg` `.png` `.mp4` `.mov` | `hold` |
| File too small | `hold` |
| Duplicate (partial hash / name+size) | `hold` |
| Unreadable image or width &lt; 800 px | `hold` |
| Otherwise | `approved` |

Rescue a hold:

```bash
sudo mv /media/lmw/hold/IMG_1234.jpg /media/lmw/approved/
```

## Test without a camera

On the Pi:

```bash
cp /path/to/photo.jpg /media/lmw/inbox/
# wait ~2 seconds
ls /media/lmw/approved/
curl -s http://127.0.0.1:8080/api/playlist
```

On a Mac (dev):

```bash
cd pi
./scripts/smoke_test.sh
```

## Local API development

```bash
cd pi
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
mkdir -p /tmp/lmw/{inbox,approved,hold,archive}
cp config.example.yaml config.yaml
# set media_root: /tmp/lmw in config.yaml
LMW_CONFIG=./config.yaml .venv/bin/python -m lmw.api
# other terminal:
LMW_CONFIG=./config.yaml .venv/bin/python -m lmw.watcher
```

## Out of scope (later)

AI moderation, FFmpeg branding burn-in, native Fire TV player, souvenir Apple Pay / 4G option.
