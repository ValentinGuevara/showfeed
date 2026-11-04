# ShowFeed

Event media pipeline: **pro capture → local triage → branded live screens**.

During the party, selected photos and short clips appear on the venue screens within about a minute — not the next-day aftermovie.

**Product pitch (French):** [https://lyrionix.fr/showfeed/](https://lyrionix.fr/showfeed/)

```
Camera (Lumix GH6 / S1 / Osmo)
        │  Wi‑Fi (dedicated event LAN)
        ▼
Raspberry Pi  ·  Samba inbox  ·  SSD storage
        │  triage → approved / hold
        │  optional quality + branding (later)
        ▼
HTTP player (:8080)
        │
   ┌────┴────┐
Fire TV    Browser / iPad
```

## Repository layout

| Path | Description |
|---|---|
| [`pi/`](pi/) | Raspberry Pi V1 — Samba receive, watcher, FastAPI playlist + web player |
| [`firetv/`](firetv/) | Fire TV / Android TV V1 — fullscreen WebView kiosk |
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

## V1 scope

**In**

- GH6 → Samba → SSD folders (`inbox` / `approved` / `hold`)
- Basic triage (extension, size, duplicates, image width)
- Playlist API + browser player
- Fire TV WebView app with configurable URL

**Later**

- AI moderation, sharpness / filters, burned-in branding
- Native Fire TV player / boot kiosk
- Souvenir QR + Apple Pay (optional 4G uplink)
- Multi-stick provisioning

## Hardware checklist (MVP)

**Capture (partner):** Lumix S1, 2× GH6, Osmo Pocket 3, spare batteries/cards  

**Regie bag:** dedicated Wi‑Fi router, Raspberry Pi 4/5, USB3 SSD (500 GB–1 TB), Fire TV Stick(+), HDMI, power strip, gaffer  

Media lives on the **SSD**, not the Pi SD card.

## License / visibility

Private repository — internal Lyrionix / partners only.
