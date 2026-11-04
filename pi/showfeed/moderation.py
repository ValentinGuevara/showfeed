"""Local 'AI' quality gate — blur / exposure heuristics (no cloud)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

from .config import ModerationConfig
from .models import Decision, TriageResult

log = logging.getLogger("showfeed.moderation")


@dataclass
class QualityScores:
    edge_mean: float
    brightness: float
    decision: Decision
    reason: str


def _edge_mean(img: Image.Image) -> float:
    """Higher ≈ sharper. FIND_EDGES mean on a downscaled luma image."""
    gray = img.convert("L")
    w, h = gray.size
    scale = max(w, h) / 512.0
    if scale > 1:
        gray = gray.resize((max(1, int(w / scale)), max(1, int(h / scale))))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    return float(ImageStat.Stat(edges).mean[0])


def _brightness(img: Image.Image) -> float:
    gray = img.convert("L")
    return float(ImageStat.Stat(gray).mean[0])


def score_image(path: Path, cfg: ModerationConfig) -> QualityScores:
    try:
        with Image.open(path) as img:
            img.load()
            edge = _edge_mean(img)
            bright = _brightness(img)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        return QualityScores(0.0, 0.0, Decision.HOLD, f"ai_unreadable:{exc}")

    # Exposure first (dark frames also lose edges — report the root cause)
    if bright < cfg.min_brightness:
        return QualityScores(edge, bright, Decision.HOLD, f"ai_dark:{bright:.1f}<{cfg.min_brightness}")
    if bright > cfg.max_brightness:
        return QualityScores(edge, bright, Decision.HOLD, f"ai_bright:{bright:.1f}>{cfg.max_brightness}")
    if edge < cfg.min_edge_mean:
        return QualityScores(edge, bright, Decision.HOLD, f"ai_blur:{edge:.1f}<{cfg.min_edge_mean}")

    return QualityScores(
        edge,
        bright,
        Decision.APPROVED,
        f"ai_ok:edge={edge:.1f},bri={bright:.1f}",
    )


def moderate(path: Path, cfg: ModerationConfig, is_image: bool) -> TriageResult:
    if not cfg.enabled:
        return TriageResult(Decision.APPROVED, "ai_disabled")
    if not is_image:
        # Video deep analysis later; pass through
        return TriageResult(Decision.APPROVED, "ai_skip_video")
    scores = score_image(path, cfg)
    log.info("%s moderation %s (%s)", path.name, scores.decision.value, scores.reason)
    return TriageResult(scores.decision, scores.reason)
