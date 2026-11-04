from __future__ import annotations

import hashlib
import logging
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .config import Config, TriageConfig

log = logging.getLogger("showfeed.triage")


class Decision(str, Enum):
    APPROVED = "approved"
    HOLD = "hold"


@dataclass
class TriageResult:
    decision: Decision
    reason: str


def _partial_hash(path: Path, nbytes: int) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        chunk = f.read(nbytes)
        h.update(chunk)
        size = path.stat().st_size
        h.update(str(size).encode("ascii"))
        h.update(path.name.encode("utf-8", errors="replace"))
    return h.hexdigest()


def _existing_fingerprints(approved_dir: Path, nbytes: int) -> set[str]:
    found: set[str] = set()
    if not approved_dir.is_dir():
        return found
    for p in approved_dir.rglob("*"):
        if not p.is_file():
            continue
        try:
            found.add(_partial_hash(p, nbytes))
            found.add(f"{p.name}:{p.stat().st_size}")
        except OSError:
            continue
    return found


def evaluate(path: Path, cfg: TriageConfig, approved_dir: Path) -> TriageResult:
    suffix = path.suffix.lower()
    image_exts = set(cfg.image_extensions)
    video_exts = set(cfg.video_extensions)
    allowed = image_exts | video_exts

    if suffix not in allowed:
        return TriageResult(Decision.HOLD, f"extension_not_allowed:{suffix or '(none)'}")

    try:
        size = path.stat().st_size
    except OSError as exc:
        return TriageResult(Decision.HOLD, f"stat_error:{exc}")

    is_image = suffix in image_exts
    min_bytes = cfg.min_image_bytes if is_image else cfg.min_video_bytes
    if size < min_bytes:
        return TriageResult(Decision.HOLD, f"too_small:{size}<{min_bytes}")

    name_size_key = f"{path.name}:{size}"
    try:
        file_hash = _partial_hash(path, cfg.hash_bytes)
    except OSError as exc:
        return TriageResult(Decision.HOLD, f"hash_error:{exc}")

    fingerprints = _existing_fingerprints(approved_dir, cfg.hash_bytes)
    if file_hash in fingerprints or name_size_key in fingerprints:
        return TriageResult(Decision.HOLD, "duplicate")

    if is_image:
        try:
            with Image.open(path) as img:
                img.verify()
            with Image.open(path) as img:
                width, _height = img.size
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            return TriageResult(Decision.HOLD, f"image_unreadable:{exc}")
        if width < cfg.min_image_width:
            return TriageResult(
                Decision.HOLD, f"image_too_narrow:{width}<{cfg.min_image_width}"
            )
        return TriageResult(Decision.APPROVED, f"image_ok:{width}px")

    # Video V1: extension + size only
    return TriageResult(Decision.APPROVED, "video_ok")


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


def route_file(path: Path, config: Config) -> TriageResult:
    """Evaluate and move path from inbox into approved/ or hold/."""
    if not path.is_file():
        return TriageResult(Decision.HOLD, "not_a_file")

    # Ignore macOS / Samba junk
    if path.name.startswith(".") or path.name.startswith("._"):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return TriageResult(Decision.HOLD, "ignored_dotfile")

    result = evaluate(path, config.triage, config.approved)
    dest_dir = config.approved if result.decision == Decision.APPROVED else config.hold
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = _unique_dest(dest_dir, path.name)

    try:
        shutil.move(str(path), str(dest))
    except OSError as exc:
        log.error("Failed to move %s → %s: %s", path, dest, exc)
        return TriageResult(Decision.HOLD, f"move_error:{exc}")

    log.info("%s → %s (%s)", path.name, result.decision.value, result.reason)
    return result
