from __future__ import annotations

import argparse
import logging
import mimetypes
import sys
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import Config, load_config
from .ops import (
    build_ops_snapshot,
    force_approve_hold,
    requeue_all_hold,
    requeue_hold,
)

log = logging.getLogger("showfeed.api")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}


def _media_type(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXT:
        return "image"
    if suffix in VIDEO_EXT:
        return "video"
    return None


def _created_iso(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
    except OSError:
        ts = datetime.now(tz=timezone.utc).timestamp()
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def build_playlist(config: Config) -> list[dict]:
    items: list[dict] = []
    if not config.approved.is_dir():
        return items

    files: list[Path] = []
    for path in config.approved.rglob("*"):
        if not path.is_file():
            continue
        if path.name.startswith(".") or path.name.startswith("._"):
            continue
        if _media_type(path) is None:
            continue
        files.append(path)

    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    limit = config.api.max_playlist_items
    for path in files[:limit]:
        rel = path.relative_to(config.approved).as_posix()
        kind = _media_type(path)
        items.append(
            {
                "id": rel,
                "url": f"/media/{rel}",
                "type": kind,
                "created_at": _created_iso(path),
                "name": path.name,
            }
        )
    items.reverse()
    return items


def resolve_idle_path(config: Config) -> Path | None:
    raw = config.player.idle_media
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (config.media_root / path).resolve()
    else:
        path = path.resolve()
    if not path.is_file():
        return None
    if _media_type(path) is None:
        return None
    return path


def idle_payload(config: Config) -> dict:
    path = resolve_idle_path(config)
    return {
        "enabled": bool(config.player.idle_enabled),
        "url": "/idle" if path else None,
        "type": _media_type(path) if path else None,
        "message": config.player.idle_message,
        "available": path is not None,
    }


def create_app(config: Config) -> FastAPI:
    config.ensure_dirs()
    (config.media_root / "idle").mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="ShowFeed", version="0.1.0")
    player_html = Path(__file__).with_name("player.html")
    regie_html = Path(__file__).with_name("regie.html")

    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "inbox": str(config.inbox),
            "approved": str(config.approved),
            "hold": str(config.hold),
        }

    @app.get("/api/playlist")
    def playlist() -> dict:
        items = build_playlist(config)
        return {
            "items": items,
            "count": len(items),
            "photo_display_seconds": config.api.photo_display_seconds,
            "brand_title": config.player.brand_title,
            "brand_subtitle": config.player.brand_subtitle,
            "idle": idle_payload(config),
        }

    @app.get("/idle")
    def idle_file() -> FileResponse:
        path = resolve_idle_path(config)
        if not path or not config.player.idle_enabled:
            raise HTTPException(status_code=404, detail="idle media not configured")
        media = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        return FileResponse(path, media_type=media)

    @app.get("/api/status")
    def status() -> dict:
        snap = build_ops_snapshot(config, playlist_count=len(build_playlist(config)))
        return {
            "inbox": snap["counts"]["inbox"],
            "approved": snap["counts"]["approved"],
            "hold": snap["counts"]["hold"],
            "playlist": snap["counts"]["playlist"],
            "disk_percent": snap["disk"].get("percent_used"),
            "alerts": snap["alerts"],
        }

    @app.get("/api/ops")
    def ops() -> dict:
        return build_ops_snapshot(config, playlist_count=len(build_playlist(config)))

    @app.post("/api/hold/{name}/requeue")
    def hold_requeue(name: str) -> dict:
        try:
            return requeue_hold(config, name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="not found") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except OSError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from None

    @app.post("/api/hold/{name}/approve")
    def hold_approve(name: str) -> dict:
        try:
            return force_approve_hold(config, name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="not found") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except Exception as exc:
            log.exception("force approve failed")
            raise HTTPException(status_code=500, detail=str(exc)) from None

    @app.post("/api/hold/requeue-all")
    def hold_requeue_all() -> dict:
        return requeue_all_hold(config)

    @app.get("/", response_class=HTMLResponse)
    def player() -> HTMLResponse:
        if not player_html.is_file():
            raise HTTPException(status_code=500, detail="player.html missing")
        return HTMLResponse(player_html.read_text(encoding="utf-8"))

    @app.get("/regie", response_class=HTMLResponse)
    def regie() -> HTMLResponse:
        if not regie_html.is_file():
            raise HTTPException(status_code=500, detail="regie.html missing")
        return HTMLResponse(regie_html.read_text(encoding="utf-8"))

    app.mount(
        "/media",
        StaticFiles(directory=str(config.approved)),
        name="media",
    )
    app.mount(
        "/hold-media",
        StaticFiles(directory=str(config.hold)),
        name="hold-media",
    )

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ShowFeed API + player")
    parser.add_argument("-c", "--config", default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config(args.config)
    app = create_app(config)
    log.info(
        "API on http://%s:%s  approved=%s  regie=/regie",
        config.api.host,
        config.api.port,
        config.approved,
    )
    uvicorn.run(
        app,
        host=config.api.host,
        port=config.api.port,
        log_level="debug" if args.verbose else "info",
    )
    return 0


mimetypes.add_type("image/jpeg", ".jpg")
mimetypes.add_type("image/jpeg", ".jpeg")
mimetypes.add_type("video/quicktime", ".mov")

if __name__ == "__main__":
    sys.exit(main())
