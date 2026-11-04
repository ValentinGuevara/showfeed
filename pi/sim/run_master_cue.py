#!/usr/bin/env python3
"""ShowFeed — fake Master CUE production simulation on your Mac.

Starts watcher + API, then drops generated stills into inbox on a timeline
like a show cue list.

Usage (from pi/):
  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
  .venv/bin/python sim/run_master_cue.py
  open http://127.0.0.1:8080/
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

log = logging.getLogger("showfeed.sim")


def _font(size: int):
    for p in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(p).is_file():
            try:
                return ImageFont.truetype(p, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def make_fixture(dest: Path, quality: str, label: str) -> None:
    """Synthesize a fake camera still for the cue.

    'good' frames need enough high-frequency detail to pass the local blur gate.
    """
    w, h = 1600, 1000
    if quality == "dark":
        base = (14, 12, 18)
        ink = (70, 65, 80)
        accent = (90, 70, 40)
    elif quality == "bright":
        base = (245, 240, 230)
        ink = (40, 35, 50)
        accent = (200, 120, 40)
    else:
        base = (52, 46, 70)
        ink = (220, 210, 190)
        accent = (242, 169, 59)

    img = Image.new("RGB", (w, h), base)
    draw = ImageDraw.Draw(img)

    # Dense edge detail (checker + lines) so "good" clears min_edge_mean
    step = 24 if quality != "blurry" else 48
    for y in range(0, h, step):
        for x in range(0, w, step):
            if (x // step + y // step) % 2 == 0:
                draw.rectangle([x, y, x + step - 1, y + step - 1], fill=ink)

    for i in range(0, w, 8):
        draw.line([(i, 0), (i, h)], fill=accent, width=1)
    for i in range(0, h, 16):
        draw.line([(0, i), (w, i)], fill=(ink[0] // 2, ink[1] // 2, ink[2] // 2), width=1)

    for i in range(14):
        x0 = 60 + i * 110
        draw.ellipse([x0, 180, x0 + 80, 480], outline=accent, width=3)
        draw.rectangle([x0 + 10, 520, x0 + 70, 780], outline=ink, width=2)

    draw.rectangle([0, h - 120, w, h], fill=(20, 16, 28))
    draw.text((48, 48), label, font=_font(42), fill=(243, 236, 228))
    draw.text((48, h - 80), f"SIM · {quality.upper()}", font=_font(28), fill=(242, 169, 59))

    if quality == "blurry":
        img = img.filter(ImageFilter.GaussianBlur(radius=18))
    elif quality == "dark":
        # Keep some structure but crush luminance for ai_dark
        img = ImageEnhance.Brightness(img).enhance(0.22)

    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, quality=92)


def make_idle_brand(dest: Path, title: str, subtitle: str, message: str) -> None:
    """Branded still used while approved/ is empty."""
    w, h = 1920, 1080
    img = Image.new("RGB", (w, h), (11, 13, 18))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(11 + t * 18)
        g = int(13 + t * 12)
        b = int(18 + t * 28)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    draw.ellipse([w * 0.55, -120, w * 1.15, h * 0.55], fill=(28, 24, 40))
    draw.text((96, h // 2 - 90), title, font=_font(72), fill=(243, 236, 228))
    draw.text((96, h // 2 - 10), subtitle, font=_font(36), fill=(242, 169, 59))
    draw.text((96, h // 2 + 70), message, font=_font(28), fill=(180, 170, 160))
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, quality=92)


def write_sim_config(media_root: Path, cue_doc: dict, path: Path) -> None:
    player = cue_doc.get("player") or {}
    idle_msg = player.get("idle_message", "Bientôt sur vos écrans")
    title = player.get("brand_title", "ShowFeed")
    subtitle = player.get("brand_subtitle", "SIM")
    idle_path = media_root / "idle" / "brand.jpg"
    make_idle_brand(idle_path, title, subtitle, idle_msg)
    cfg = {
        "media_root": str(media_root),
        "api": {
            "host": cue_doc.get("api_host", "127.0.0.1"),
            "port": int(cue_doc.get("api_port", 8080)),
            "max_playlist_items": 50,
            "photo_display_seconds": 5,
        },
        "triage": {
            "min_image_bytes": 1000,
            "min_video_bytes": 1000,
            "min_image_width": 100,
            "stable_seconds": float(cue_doc.get("stable_seconds", 0.6)),
        },
        "moderation": {"enabled": True, "min_edge_mean": 12.0},
        "processing": {"sharpness": 1.4, "contrast": 1.08},
        "branding": {"enabled": True},
        "player": {
            "brand_title": title,
            "brand_subtitle": subtitle,
            "idle_enabled": True,
            "idle_media": "idle/brand.jpg",
            "idle_message": idle_msg,
        },
    }
    path.write_text(yaml.dump(cfg), encoding="utf-8")


def fetch_status(port: int) -> dict:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="ShowFeed Master CUE simulator")
    parser.add_argument(
        "-c",
        "--cue",
        default=str(Path(__file__).with_name("master_cue.yaml")),
        help="Path to master_cue.yaml",
    )
    parser.add_argument("--no-api", action="store_true", help="Only drop files (no server)")
    parser.add_argument(
        "--exit",
        action="store_true",
        help="Stop watcher/API after the cue list (no Ctrl+C wait)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    cue_path = Path(args.cue)
    cue_doc = yaml.safe_load(cue_path.read_text(encoding="utf-8"))
    media_root = Path(cue_doc.get("media_root", "/tmp/showfeed-sim"))
    port = int(cue_doc.get("api_port", 8080))
    for d in ("inbox", "approved", "hold", "archive"):
        (media_root / d).mkdir(parents=True, exist_ok=True)

    cfg_path = media_root / "config.yaml"
    write_sim_config(media_root, cue_doc, cfg_path)
    env = os.environ.copy()
    env["SHOWFEED_CONFIG"] = str(cfg_path)
    env["PYTHONPATH"] = str(ROOT)

    py = sys.executable
    procs: list[subprocess.Popen] = []

    def stop_all(*_args) -> None:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()

    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)

    print()
    print("=" * 60)
    print(f"  {cue_doc.get('name', 'MASTER CUE')}")
    print(f"  media: {media_root}")
    print(f"  player: http://127.0.0.1:{port}/")
    print("=" * 60)
    print()

    if not args.no_api:
        procs.append(
            subprocess.Popen(
                [py, "-m", "showfeed.watcher", "-c", str(cfg_path)],
                cwd=str(ROOT),
                env=env,
            )
        )
        procs.append(
            subprocess.Popen(
                [py, "-m", "showfeed.api", "-c", str(cfg_path)],
                cwd=str(ROOT),
                env=env,
            )
        )
        time.sleep(1.2)
        print("  [sys] watcher + API up")
        print()

    cues = sorted(cue_doc.get("cues") or [], key=lambda c: float(c.get("at", 0)))
    t0 = time.monotonic()
    idx = 0

    while idx < len(cues):
        now = time.monotonic() - t0
        cue = cues[idx]
        at = float(cue.get("at", 0))
        if now < at:
            time.sleep(min(0.2, at - now))
            continue

        cid = cue.get("id", f"CUE-{idx}")
        label = cue.get("label", "")
        action = cue.get("action", "announce")
        print(f"  [{now:6.1f}s] {cid}  {label}")

        if action == "drop":
            name = cue.get("filename") or f"{cid}.jpg"
            quality = cue.get("quality", "good")
            dest = media_root / "inbox" / name
            make_fixture(dest, quality, label)
            print(f"           → inbox/{name} ({quality})")
        elif action == "status":
            st = fetch_status(port)
            print(
                f"           → inbox={st.get('inbox')} approved={st.get('approved')} "
                f"hold={st.get('hold')} playlist={st.get('playlist')}"
            )
        elif action == "announce":
            pass

        idx += 1

    # Let watcher finish last files
    time.sleep(2.5)
    st = fetch_status(port)
    print()
    print("  FINAL STATUS", st)
    print()
    print(f"  Open player → http://127.0.0.1:{port}/")
    if args.exit or args.no_api:
        print("  Exiting (--exit / --no-api).")
        stop_all()
        return 0

    print("  Ctrl+C to stop watcher/API.")
    print()

    if procs:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        stop_all()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
