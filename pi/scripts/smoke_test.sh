#!/usr/bin/env bash
# Local smoke test without a Pi: temp media root + triage one image.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d /tmp/showfeed-smoke.XXXXXX)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

mkdir -p "$TMP"/{inbox,approved,hold,archive}

cat > "$TMP/config.yaml" <<EOF
media_root: $TMP
api:
  host: "127.0.0.1"
  port: 18080
  max_playlist_items: 20
  photo_display_seconds: 3
triage:
  min_image_bytes: 100
  min_video_bytes: 100
  min_image_width: 10
  stable_seconds: 0.5
moderation:
  enabled: true
  min_edge_mean: 8.0
processing:
  sharpness: 1.2
branding:
  enabled: true
player:
  brand_title: "ShowFeed"
  brand_subtitle: "SMOKE"
EOF

cd "$ROOT"
python3 -m venv "$TMP/venv"
"$TMP/venv/bin/pip" -q install -r requirements.txt

# Valid JPEG with edges (passes blur gate) + junk + blurry hold fixture
"$TMP/venv/bin/python" - "$TMP" <<'PY'
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path
import sys
tmp = Path(sys.argv[1])
img = Image.new("RGB", (1200, 800), color=(30, 40, 50))
d = ImageDraw.Draw(img)
for i in range(40):
    d.line((i * 30, 0, i * 30, 800), fill=(200, 180, 100))
img.save(tmp / "inbox" / "test_shot.jpg", quality=85)
blur = img.filter(ImageFilter.GaussianBlur(18))
blur.save(tmp / "inbox" / "blur_shot.jpg", quality=85)
(tmp / "inbox" / "too_small.jpg").write_bytes(b"not-an-image")
print("wrote inbox fixtures")
PY

"$TMP/venv/bin/python" - "$ROOT" "$TMP" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from showfeed.config import load_config
from showfeed.triage import route_file

cfg = load_config(Path(sys.argv[2]) / "config.yaml")
for p in sorted(cfg.inbox.iterdir()):
    if p.is_file():
        r = route_file(p, cfg)
        print(p.name, "->", r.decision.value, r.reason)

approved = list(cfg.approved.iterdir())
hold = list(cfg.hold.iterdir())
assert any(p.name == "test_shot.jpg" for p in approved), approved
assert any(p.name == "blur_shot.jpg" for p in hold), hold
assert any(p.name == "too_small.jpg" for p in hold), hold
assert any(p.name == "test_shot.jpg" for p in cfg.archive.iterdir()), "original should be archived"
print("SMOKE OK", "approved=", len(approved), "hold=", len(hold))
PY
