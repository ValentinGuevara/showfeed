"""Filters + branding burn-in (Pillow images; FFmpeg videos when available)."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from .config import Config

log = logging.getLogger("showfeed.process")


def _unique_dest(dest_dir: Path, name: str) -> Path:
    dest = dest_dir / name
    if not dest.exists():
        return dest
    stem = Path(name).stem
    suffix = Path(name).suffix
    n = 1
    while True:
        candidate = dest_dir / f"{stem}_{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def apply_filters(img: Image.Image, config: Config) -> Image.Image:
    p = config.processing
    out = img.convert("RGB")
    if p.contrast != 1.0:
        out = ImageEnhance.Contrast(out).enhance(p.contrast)
    if p.color != 1.0:
        out = ImageEnhance.Color(out).enhance(p.color)
    if p.brightness != 1.0:
        out = ImageEnhance.Brightness(out).enhance(p.brightness)
    if p.sharpness != 1.0:
        out = ImageEnhance.Sharpness(out).enhance(p.sharpness)
    return out


def burn_branding(img: Image.Image, config: Config) -> Image.Image:
    b = config.branding
    if not b.enabled:
        return img

    out = img.convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = out.size

    # Soft bottom gradient bar for legibility
    bar_h = max(48, h // 12)
    for y in range(bar_h):
        alpha = int(140 * (y / bar_h))
        draw.line([(0, h - bar_h + y), (w, h - bar_h + y)], fill=(0, 0, 0, alpha))

    title = config.player.brand_title or "ShowFeed"
    subtitle = config.player.brand_subtitle or ""
    font_title = _load_font(max(18, w // 40))
    font_sub = _load_font(max(14, w // 55))

    margin = max(16, w // 50)
    # Title bottom-right
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = w - margin - tw
    y = h - margin - th
    if subtitle:
        sb = draw.textbbox((0, 0), subtitle, font=font_sub)
        sw, sh = sb[2] - sb[0], sb[3] - sb[1]
        draw.text((w - margin - sw, y - sh - 6), subtitle, font=font_sub, fill=(243, 236, 228, 200))
    draw.text((x, y), title, font=font_title, fill=(242, 169, 59, 255))

    # Optional PNG logo top-right
    if b.logo_path:
        logo_file = Path(b.logo_path)
        if logo_file.is_file():
            try:
                logo = Image.open(logo_file).convert("RGBA")
                max_w = max(64, w // b.logo_max_width_ratio)
                logo.thumbnail((max_w, max_w))
                lx = w - margin - logo.width
                ly = margin
                overlay.alpha_composite(logo, (lx, ly))
            except OSError as exc:
                log.warning("Logo load failed: %s", exc)

    return Image.alpha_composite(out, overlay).convert("RGB")


def process_image(src: Path, config: Config) -> Path:
    """Filter + brand → write into approved/. Returns destination path."""
    config.approved.mkdir(parents=True, exist_ok=True)
    dest = _unique_dest(config.approved, src.name)
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)
        framed = burn_branding(apply_filters(img, config), config)
        suffix = dest.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            framed.save(dest, quality=config.processing.jpeg_quality, optimize=True)
        else:
            framed.save(dest)
    log.info("Processed image %s → %s", src.name, dest.name)
    return dest


def _ffmpeg_available() -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            check=False,
            capture_output=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def process_video(src: Path, config: Config) -> Path:
    """Brand burn-in via ffmpeg drawtext when possible; else copy."""
    config.approved.mkdir(parents=True, exist_ok=True)
    dest = _unique_dest(config.approved, src.name)
    b = config.branding
    if not b.enabled or not _ffmpeg_available():
        shutil.copy2(src, dest)
        log.info("Video copy (no ffmpeg burn-in) %s → %s", src.name, dest.name)
        return dest

    title = config.player.brand_title.replace(":", "\\:")
    # Escape for drawtext
    title = title.replace("'", "\\'")
    vf = (
        f"drawtext=text='{title}':fontsize=28:fontcolor=0xF2A93B:"
        f"x=w-tw-40:y=h-th-40:box=1:boxcolor=black@0.45:boxborderw=8"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
        "-vf",
        vf,
        "-codec:a",
        "copy",
        str(dest),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        log.info("Video branded %s → %s", src.name, dest.name)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        log.warning("ffmpeg failed (%s) — copying raw", exc)
        if dest.exists():
            dest.unlink(missing_ok=True)
        shutil.copy2(src, dest)
    return dest


def process_and_approve(src: Path, config: Config, is_image: bool) -> Path:
    if is_image:
        return process_image(src, config)
    return process_video(src, config)
