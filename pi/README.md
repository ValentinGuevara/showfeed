# ShowFeed — Raspberry Pi V1

Receives media from a Lumix GH6 over **Samba**, stores it on a **USB SSD**, runs basic **triage**, and serves an **HTTP playlist + fullscreen player** for Fire TV / browsers.

Product pitch: [https://lyrionix.fr/showfeed/](https://lyrionix.fr/showfeed/)

Copyright © 2026 Valentin Guevara / Lyrionix. All rights reserved. Proprietary — see root `LICENSE`.

```
GH6 --Wi‑Fi SMB--> Pi Samba --> /media/showfeed/inbox
                                  │
                              watcher
                    triage → AI quality → filters + brand
                             ╱              ╲
                      approved            hold
                     (+ archive)
                          │
                     HTTP :8080  -->  Fire TV / Chrome
```

## Contents

| Path | Role |
|---|---|
| `showfeed/` | Watcher, triage, moderation, process, API, player HTML |
| `config.example.yaml` | Copy to `config.yaml` |
| `install/setup-ssd.sh` | Mount SSD at `/media/showfeed` |
| `install/setup-samba.sh` | Share `showfeed`, user `wall`, hostname `regie` |
| `install/install-app.sh` | Install to `/opt/showfeed` + systemd units |
| `scripts/smoke_test.sh` | Local test without Pi hardware |
| `sim/` | Fake Master CUE runner (Mac / laptop) |

## Install on the Pi (order)

### 1. SSD

Format a partition as ext4 with label `SHOWFEED` (once):

```bash
# WARNING: destroys data — use the correct /dev/sdX1
sudo mkfs.ext4 -L SHOWFEED /dev/sda1
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
| Share | `showfeed` → `/media/showfeed/inbox` |
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
journalctl -u showfeed-watcher -u showfeed-api -f
```

## GH6 configuration

1. Same dedicated Wi‑Fi as the Pi  
2. **Wi‑Fi Function** → **New Connection** → **Send Images While Recording** (or *Stored*) → **PC**  
3. **Via Network** → host `regie` (or Pi IP)  
4. Folder / share `showfeed`  
5. User `wall` + Samba password  
6. Prefer JPEG for live; short 1080p MP4/MOV clips are fine  

If the camera says destination not found: wait ~15 s, check `nmbd`, retry. Lumix PC transfer does **not** auto-resume after power-on — re-enable it at the start of the event.

## Pipeline (V1)

| Stage | Result |
|---|---|
| Extension outside `.jpg` `.jpeg` `.png` `.mp4` `.mov` | `hold` |
| File too small / duplicate / unreadable / width &lt; 800 px | `hold` |
| Blur / too dark / too bright (`moderation`) | `hold` |
| Pass → filters + branding burn-in → `approved/` | original → `archive/` |

Rescue a hold (skip re-process, or drop back into inbox):

```bash
sudo mv /media/showfeed/hold/IMG_1234.jpg /media/showfeed/inbox/
```

Tune thresholds in `config.yaml` (`moderation`, `processing`, `branding`).

## Test without a camera

On the Pi:

```bash
cp /path/to/photo.jpg /media/showfeed/inbox/
# wait ~2 seconds
ls /media/showfeed/approved/
curl -s http://127.0.0.1:8080/api/playlist
```

On a Mac (dev):

```bash
cd pi
./scripts/smoke_test.sh
```

### Fake Master CUE (full sim)

Drops timed stills into a temp inbox like a show cue list — good / blurry / dark — then you watch the player.

```bash
cd pi
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python sim/run_master_cue.py
# → http://127.0.0.1:8080/
# Cue list: sim/master_cue.yaml
# Auto-stop after cues:  .venv/bin/python sim/run_master_cue.py --exit
```

## Local API development

```bash
cd pi
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
mkdir -p /tmp/showfeed/{inbox,approved,hold,archive}
cp config.example.yaml config.yaml
# set media_root: /tmp/showfeed in config.yaml
SHOWFEED_CONFIG=./config.yaml .venv/bin/python -m showfeed.api
# other terminal:
SHOWFEED_CONFIG=./config.yaml .venv/bin/python -m showfeed.watcher
```

## Out of scope (later)

Cloud AI moderation, native Fire TV player, souvenir Apple Pay / 4G option.
