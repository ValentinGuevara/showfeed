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

log = logging.getLogger("lmw.api")

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
    # Player loops oldest→newest feel: reverse so oldest of the window plays first
    items.reverse()
    return items


def create_app(config: Config) -> FastAPI:
    config.ensure_dirs()
    app = FastAPI(title="Live Memory Wall", version="0.1.0")
    player_html = Path(__file__).with_name("player.html")

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
        }

    @app.get("/api/status")
    def status() -> dict:
        def count_files(folder: Path) -> int:
            if not folder.is_dir():
                return 0
            return sum(
                1
                for p in folder.rglob("*")
                if p.is_file() and not p.name.startswith(".")
            )

        return {
            "inbox": count_files(config.inbox),
            "approved": count_files(config.approved),
            "hold": count_files(config.hold),
            "playlist": len(build_playlist(config)),
        }

    @app.get("/", response_class=HTMLResponse)
    def player() -> HTMLResponse:
        if not player_html.is_file():
            raise HTTPException(status_code=500, detail="player.html missing")
        return HTMLResponse(player_html.read_text(encoding="utf-8"))

    # Serve approved media; prevent path escape via StaticFiles root
    app.mount(
        "/media",
        StaticFiles(directory=str(config.approved)),
        name="media",
    )

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live Memory Wall API + player")
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
        "API on http://%s:%s  approved=%s",
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
