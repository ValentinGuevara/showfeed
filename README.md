# ShowFeed

Event media pipeline: **pro capture → local triage → branded live screens**.

During the party, selected photos and short clips appear on the venue screens within about a minute — not the next-day aftermovie.

**Product pitch (French):** [https://lyrionix.fr/showfeed/](https://lyrionix.fr/showfeed/)  
**Cahier des charges (FR) — livré + backlog :** [docs/CAHIER_DES_CHARGES.md](docs/CAHIER_DES_CHARGES.md)

```
Camera (Lumix GH6 / S1 / Osmo)
        │  Wi‑Fi (dedicated event LAN)
        ▼
Raspberry Pi  ·  Samba inbox  ·  SSD storage
        │  triage → quality gate → filters + brand burn-in
        │  approved / hold (+ archive originals)
        ▼
HTTP player (:8080)  ·  Régie /regie
        │
   ┌────┴────┐
Fire TV    Browser / iPad
```

## Docs

| Doc | Role |
|---|---|
| **[docs/CAHIER_DES_CHARGES.md](docs/CAHIER_DES_CHARGES.md)** | Spec produit FR : ce qui est livré (V1) + backlog à implémenter (cloud Vision, fallback local, **crédits**, etc.) |
| [pi/README.md](pi/README.md) | Install Pi, Samba, pipeline, sim, `/regie` |
| [firetv/README.md](firetv/README.md) | Build / install Fire TV |

## Repository layout

| Path | Description |
|---|---|
| [`pi/`](pi/) | Raspberry Pi V1 — Samba receive, watcher, FastAPI playlist + web player |
| [`firetv/`](firetv/) | Fire TV / Android TV V1 — fullscreen WebView kiosk |
| [`docs/`](docs/) | Cahier des charges + specs backlog |
| [`index.html`](index.html) | Pitch page (French), also deployed at [lyrionix.fr/showfeed](https://lyrionix.fr/showfeed/) |
| [`assets/`](assets/) | Pitch imagery |

## Quick start

### 1. Raspberry Pi

See **[pi/README.md](pi/README.md)**.

```bash
cd pi
sudo ./install/setup-ssd.sh       # USB SSD → /media/showfeed
sudo ./install/setup-samba.sh     # share showfeed, host regie, user wall
sudo ./install/install-app.sh     # /opt/showfeed + systemd
```

Player URL: `http://<pi-ip>:8080/`

Local smoke test (no Pi hardware):

```bash
cd pi && ./scripts/smoke_test.sh
```

Fake Master CUE on your Mac (watcher + API + timed drops):

```bash
cd pi
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python sim/run_master_cue.py
# open http://127.0.0.1:8080/
# or: .venv/bin/python sim/run_master_cue.py --exit
```

### 2. Fire TV Stick

See **[firetv/README.md](firetv/README.md)**.

```bash
cd firetv
./gradlew :app:assembleDebug
adb connect <stick-ip>:5555
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Open **SHOWFEED Player**, press **Menu** to set the Pi URL if it is not `http://192.168.50.10:8080/`.

### 3. Camera (GH6)

1. Join the dedicated event Wi‑Fi  
2. **Send Images to PC** → Via Network → host `regie` → share `showfeed`  
3. User `wall` + Samba password  
4. Prefer JPEG + short 1080p clips for live latency  

## V1 scope (shipped)

- GH6 → Samba → SSD folders (`inbox` / `approved` / `hold` / `archive`)
- Basic triage (extension, size, duplicates, image width)
- **Local** quality gate (Pillow blur / exposure — not a cloud LLM) + filters + branding burn-in
- Playlist API + browser player + idle branding when empty
- Fire TV WebView app with configurable URL
- Master CUE local simulation (`pi/sim/`)
- Régie page `/regie` — alerts + one-tap hold rescue

## Backlog (not coded yet)

Full write-up: **[docs/CAHIER_DES_CHARGES.md](docs/CAHIER_DES_CHARGES.md)** — use that file to generate the next lot.

Priority (§3 du CDC) :

1. **Cloud Vision** (Gemini and/or ChatGPT) for still moderation when uplink is up  
2. **Local fallback** on timeout / offline / API error (existing Pillow gate) — show must never stall  
3. **Credits pool** per event to cap cloud cost (persist on SSD, warn on `/regie`, force local at 0)

Also later: native Fire TV kiosk, souvenir QR + Apple Pay (optional 4G), multi-stick provisioning.

## Hardware checklist (MVP)

**Capture (partner):** Lumix S1, 2× GH6, Osmo Pocket 3, spare batteries/cards  

**Regie bag:** dedicated Wi‑Fi router, Raspberry Pi 4/5, USB3 SSD (500 GB–1 TB), Fire TV Stick(+), HDMI, power strip, gaffer  

Media lives on the **SSD**, not the Pi SD card.

## Ownership & license

**Copyright © 2026 Valentin Guevara / Lyrionix. All rights reserved.**

This is **proprietary software**. No license is granted to copy, modify, reuse,
redistribute, or create derivative works — commercially or otherwise — without
prior written permission from the copyright holder.

See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

Viewing or cloning this repository does **not** grant any rights to use the code.
