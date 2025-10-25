"""Utility helpers for avatar colors and contrast."""

from __future__ import annotations

import hashlib
from typing import Sequence, Tuple

AVATAR_COLOR_PALETTE: tuple[str, ...] = (
    "#F94144",
    "#F3722C",
    "#F8961E",
    "#F9844A",
    "#F9C74F",
    "#90BE6D",
    "#43AA8B",
    "#4D908E",
    "#577590",
    "#277DA1",
    "#9D4EDD",
    "#F72585",
    "#B5179E",
    "#7209B7",
    "#4361EE",
    "#4CC9F0",
)


def normalize_hex_color(value: str | None) -> str:
    """Normalize a HEX color string to the canonical "#RRGGBB" form."""
    if not value:
        raise ValueError("Empty color value")
    candidate = value.strip()
    if candidate.startswith("#"):
        candidate = candidate[1:]
    if len(candidate) != 6:
        raise ValueError("Color must contain exactly 6 hexadecimal characters")
    int(candidate, 16)  # Raises ValueError if not hex
    return f"#{candidate.upper()}"


def is_valid_hex_color(value: str | None) -> bool:
    """Return True when *value* is a valid HEX color string."""
    try:
        normalize_hex_color(value)
    except ValueError:
        return False
    return True


def generate_avatar_color(seed: str, palette: Sequence[str] | None = None) -> str:
    """Deterministically choose a color from *palette* based on *seed*."""
    colors = tuple(normalize_hex_color(color) for color in (palette or AVATAR_COLOR_PALETTE))
    if not colors:
        raise ValueError("Palette must contain at least one color")
    normalized_seed = seed or "default"
    digest = hashlib.sha256(normalized_seed.encode("utf-8")).digest()
    index = digest[0] % len(colors)
    return colors[index]


def srgb_to_linear(channel: float) -> float:
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def pick_text_color(color: str) -> Tuple[str, bool]:
    """Return contrasting text color (#000000 or #FFFFFF) and whether a border is needed."""
    normalized = normalize_hex_color(color)
    r = int(normalized[1:3], 16) / 255.0
    g = int(normalized[3:5], 16) / 255.0
    b = int(normalized[5:7], 16) / 255.0

    luminance = 0.2126 * srgb_to_linear(r) + 0.7152 * srgb_to_linear(g) + 0.0722 * srgb_to_linear(b)
    text_color = "#000000" if luminance > 0.179 else "#FFFFFF"
    needs_border = luminance > 0.65
    return text_color, needs_border


__all__ = [
    "AVATAR_COLOR_PALETTE",
    "generate_avatar_color",
    "is_valid_hex_color",
    "normalize_hex_color",
    "pick_text_color",
]
