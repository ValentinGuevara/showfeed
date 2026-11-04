"""Show-night ops helpers: disk, alerts, hold listing, rescue."""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from .config import Config
from .process import process_and_approve

log = logging.getLogger("showfeed.ops")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}


def count_files(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    return sum(
        1 for p in folder.rglob("*") if p.is_file() and not p.name.startswith(".")
    )


def list_media(folder: Path, limit: int = 40) -> list[dict]:
    if not folder.is_dir():
        return []
    files: list[Path] = []
    for path in folder.rglob("*"):
        if not path.is_file() or path.name.startswith(".") or path.name.startswith("._"):
            continue
        files.append(path)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    out: list[dict] = []
    for path in files[:limit]:
        try:
            st = path.stat()
        except OSError:
            continue
        suffix = path.suffix.lower()
        kind = "image" if suffix in IMAGE_EXT else "video" if suffix in VIDEO_EXT else "other"
        out.append(
            {
                "name": path.name,
                "type": kind,
                "bytes": st.st_size,
                "mtime": st.st_mtime,
                "age_seconds": max(0, int(time.time() - st.st_mtime)),
            }
        )
    return out


def newest_mtime(folder: Path) -> float | None:
    newest: float | None = None
    if not folder.is_dir():
        return None
    for path in folder.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        try:
            mt = path.stat().st_mtime
        except OSError:
            continue
        if newest is None or mt > newest:
            newest = mt
    return newest


def disk_stats(root: Path) -> dict:
    try:
        usage = shutil.disk_usage(root)
        percent = round(100.0 * usage.used / usage.total, 1) if usage.total else 0.0
        return {
            "path": str(root),
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "percent_used": percent,
            "ok": True,
        }
    except OSError as exc:
        return {
            "path": str(root),
            "ok": False,
            "error": str(exc),
            "percent_used": 100.0,
            "free_bytes": 0,
            "total_bytes": 0,
            "used_bytes": 0,
        }


def safe_child(folder: Path, name: str) -> Path:
    """Resolve name inside folder; reject path traversal."""
    if not name or name != Path(name).name or ".." in name:
        raise ValueError("invalid name")
    path = (folder / name).resolve()
    folder_r = folder.resolve()
    if folder_r not in path.parents and path != folder_r:
        raise ValueError("path escape")
    if not path.is_file():
        raise FileNotFoundError(name)
    return path


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


def requeue_hold(config: Config, name: str) -> dict:
    src = safe_child(config.hold, name)
    config.inbox.mkdir(parents=True, exist_ok=True)
    dest = _unique_dest(config.inbox, src.name)
    shutil.move(str(src), str(dest))
    log.info("Rescue requeue %s → inbox", name)
    return {"ok": True, "action": "requeue", "name": name, "dest": dest.name}


def force_approve_hold(config: Config, name: str) -> dict:
    """Skip quality gate: brand + send to approved."""
    src = safe_child(config.hold, name)
    suffix = src.suffix.lower()
    is_image = suffix in set(config.triage.image_extensions)
    dest = process_and_approve(src, config, is_image=is_image)
    # Archive original from hold
    config.archive.mkdir(parents=True, exist_ok=True)
    arch = _unique_dest(config.archive, src.name)
    shutil.move(str(src), str(arch))
    log.info("Rescue force-approve %s → %s", name, dest.name)
    return {
        "ok": True,
        "action": "force_approve",
        "name": name,
        "approved": dest.name,
    }


def requeue_all_hold(config: Config) -> dict:
    names = [p.name for p in list_media(config.hold, limit=500)]
    done = []
    errors = []
    for name in names:
        try:
            requeue_hold(config, name)
            done.append(name)
        except Exception as exc:
            errors.append({"name": name, "error": str(exc)})
    return {"ok": not errors, "requeued": done, "errors": errors}


def build_alerts(config: Config, counts: dict, disk: dict, holds: list[dict], inbox: list[dict]) -> list[dict]:
    alerts: list[dict] = []
    ops = config.ops

    if not disk.get("ok"):
        alerts.append(
            {
                "level": "critical",
                "code": "disk_error",
                "message": f"Disque illisible: {disk.get('error', '?')}",
            }
        )
    elif float(disk.get("percent_used") or 0) >= ops.disk_warn_percent:
        alerts.append(
            {
                "level": "critical" if disk["percent_used"] >= 95 else "warning",
                "code": "disk_full",
                "message": f"SSD {disk['percent_used']}% plein ({disk['free_bytes'] // (1024**3)} Go libres)",
            }
        )

    if counts["hold"] >= ops.hold_warn_count:
        alerts.append(
            {
                "level": "warning" if counts["hold"] < ops.hold_warn_count * 2 else "critical",
                "code": "hold_flood",
                "message": f"{counts['hold']} fichiers en hold — à rattraper",
            }
        )

    stuck = [
        h
        for h in inbox
        if h["age_seconds"] >= ops.inbox_stuck_seconds
    ]
    if stuck:
        alerts.append(
            {
                "level": "warning",
                "code": "inbox_stuck",
                "message": f"{len(stuck)} fichier(s) coincé(s) dans inbox (> {ops.inbox_stuck_seconds}s) — watcher ?",
            }
        )

    if counts["approved"] == 0 and counts["playlist"] == 0:
        idle_ok = bool(config.player.idle_enabled and config.player.idle_media)
        alerts.append(
            {
                "level": "info" if idle_ok else "warning",
                "code": "playlist_empty",
                "message": "Playlist vide — idle branding"
                if idle_ok
                else "Playlist vide et pas d’idle media configuré",
            }
        )

    return alerts


def build_ops_snapshot(config: Config, playlist_count: int) -> dict:
    holds = list_media(config.hold, limit=40)
    inbox = list_media(config.inbox, limit=20)
    disk = disk_stats(config.media_root)
    counts = {
        "inbox": count_files(config.inbox),
        "approved": count_files(config.approved),
        "hold": count_files(config.hold),
        "archive": count_files(config.archive),
        "playlist": playlist_count,
    }
    last_approved = newest_mtime(config.approved)
    return {
        "ok": True,
        "ts": time.time(),
        "brand_title": config.player.brand_title,
        "counts": counts,
        "disk": disk,
        "alerts": build_alerts(config, counts, disk, holds, inbox),
        "hold_files": holds,
        "inbox_files": inbox,
        "last_approved_age_seconds": (
            int(time.time() - last_approved) if last_approved else None
        ),
        "thresholds": {
            "hold_warn_count": config.ops.hold_warn_count,
            "disk_warn_percent": config.ops.disk_warn_percent,
            "inbox_stuck_seconds": config.ops.inbox_stuck_seconds,
        },
    }
