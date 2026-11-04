from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_NAMES = ("config.yaml", "config.example.yaml")


@dataclass
class ApiConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    max_playlist_items: int = 50
    photo_display_seconds: int = 8


@dataclass
class TriageConfig:
    image_extensions: list[str] = field(
        default_factory=lambda: [".jpg", ".jpeg", ".png"]
    )
    video_extensions: list[str] = field(
        default_factory=lambda: [".mp4", ".mov"]
    )
    min_image_bytes: int = 51200
    min_video_bytes: int = 102400
    min_image_width: int = 800
    stable_seconds: float = 2.0
    hash_bytes: int = 65536


@dataclass
class PlayerConfig:
    brand_title: str = "LiveFrame"
    brand_subtitle: str = "Logo de l’event"


@dataclass
class Config:
    media_root: Path
    inbox: Path
    approved: Path
    hold: Path
    archive: Path
    api: ApiConfig = field(default_factory=ApiConfig)
    triage: TriageConfig = field(default_factory=TriageConfig)
    player: PlayerConfig = field(default_factory=PlayerConfig)

    def ensure_dirs(self) -> None:
        for path in (self.media_root, self.inbox, self.approved, self.hold, self.archive):
            path.mkdir(parents=True, exist_ok=True)


def _package_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_config_path(explicit: str | Path | None = None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Config not found: {path}")
        return path

    env = os.environ.get("LIVEFRAME_CONFIG")
    if env:
        path = Path(env).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"LIVEFRAME_CONFIG not found: {path}")
        return path

    base = _package_dir()
    for name in DEFAULT_CONFIG_NAMES:
        candidate = base / name
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        "No config.yaml or config.example.yaml found. "
        "Copy config.example.yaml to config.yaml."
    )


def load_config(path: str | Path | None = None) -> Config:
    cfg_path = resolve_config_path(path)
    raw: dict[str, Any] = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    media_root = Path(raw.get("media_root", "/media/liveframe")).expanduser().resolve()
    inbox_name = raw.get("inbox", "inbox")
    approved_name = raw.get("approved", "approved")
    hold_name = raw.get("hold", "hold")
    archive_name = raw.get("archive", "archive")

    api_raw = raw.get("api") or {}
    triage_raw = raw.get("triage") or {}
    player_raw = raw.get("player") or {}

    api = ApiConfig(
        host=str(api_raw.get("host", "0.0.0.0")),
        port=int(api_raw.get("port", 8080)),
        max_playlist_items=int(api_raw.get("max_playlist_items", 50)),
        photo_display_seconds=int(api_raw.get("photo_display_seconds", 8)),
    )

    triage = TriageConfig(
        image_extensions=[
            e.lower() if e.startswith(".") else f".{e.lower()}"
            for e in triage_raw.get("image_extensions", [".jpg", ".jpeg", ".png"])
        ],
        video_extensions=[
            e.lower() if e.startswith(".") else f".{e.lower()}"
            for e in triage_raw.get("video_extensions", [".mp4", ".mov"])
        ],
        min_image_bytes=int(triage_raw.get("min_image_bytes", 51200)),
        min_video_bytes=int(triage_raw.get("min_video_bytes", 102400)),
        min_image_width=int(triage_raw.get("min_image_width", 800)),
        stable_seconds=float(triage_raw.get("stable_seconds", 2.0)),
        hash_bytes=int(triage_raw.get("hash_bytes", 65536)),
    )

    player = PlayerConfig(
        brand_title=str(player_raw.get("brand_title", "LiveFrame")),
        brand_subtitle=str(player_raw.get("brand_subtitle", "Logo de l’event")),
    )

    return Config(
        media_root=media_root,
        inbox=media_root / inbox_name,
        approved=media_root / approved_name,
        hold=media_root / hold_name,
        archive=media_root / archive_name,
        api=api,
        triage=triage,
        player=player,
    )
