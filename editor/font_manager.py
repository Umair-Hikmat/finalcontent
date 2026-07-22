"""
Font manager: resolves a FontConfig (family name + source) into an actual
.ttf/.otf file path that Pillow's ImageFont can load, downloading from
Google Fonts on first use and caching locally, or using a user-uploaded
custom font.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import requests
from PIL import ImageFont

from config import settings

# A curated list so the UI has a fast, reliable dropdown without hitting the
# network just to populate the picker. Any of these can be fetched on demand.
CURATED_GOOGLE_FONTS: List[str] = [
    "Poppins", "Montserrat", "Bebas Neue", "Anton", "Oswald", "Roboto",
    "Inter", "Nunito", "Baloo 2", "Fredoka", "Archivo Black", "Bangers",
    "Righteous", "Lobster", "Pacifico", "Press Start 2P", "Orbitron",
    "Kanit", "Rubik", "Comfortaa", "DM Sans", "Space Grotesk", "Sora",
]

GOOGLE_FONTS_CSS2 = "https://fonts.googleapis.com/css2?family={family}:wght@400;700;900&display=swap"
FONT_FILE_URL_RE = re.compile(r"url\((https://[^)]+\.(?:ttf|otf))\)")


def _family_slug(family: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", family.strip())


def local_font_path(family: str, weight: str = "bold") -> Path:
    return settings.fonts_dir / f"{_family_slug(family)}_{weight}.ttf"


def download_google_font(family: str) -> Optional[Path]:
    """Downloads a Google Font's TTF file and caches it under assets/fonts/."""
    dest = local_font_path(family)
    if dest.exists():
        return dest

    css_url = GOOGLE_FONTS_CSS2.format(family=family.replace(" ", "+"))
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; AIQuizStudio/1.0)"}
        css_resp = requests.get(css_url, headers=headers, timeout=10)
        css_resp.raise_for_status()
        matches = FONT_FILE_URL_RE.findall(css_resp.text)
        if not matches:
            return None
        font_url = matches[-1]  # last match tends to be the boldest/most complete
        font_resp = requests.get(font_url, headers=headers, timeout=15)
        font_resp.raise_for_status()
        dest.write_bytes(font_resp.content)
        return dest
    except Exception:
        return None


def save_custom_font(uploaded_bytes: bytes, filename: str) -> Path:
    dest = settings.fonts_dir / filename
    dest.write_bytes(uploaded_bytes)
    return dest


def list_installed_fonts() -> List[str]:
    return sorted({f.stem for f in settings.fonts_dir.glob("*.ttf")} | {f.stem for f in settings.fonts_dir.glob("*.otf")})


def resolve_font_path(family: str, source: str = "google", custom_path: Optional[str] = None) -> Optional[str]:
    if source == "custom" and custom_path:
        p = Path(custom_path)
        return str(p) if p.exists() else None

    path = download_google_font(family)
    return str(path) if path else None


@lru_cache(maxsize=64)
def _load_font_cached(path_or_none: str, size: int):
    if path_or_none and Path(path_or_none).exists():
        try:
            return ImageFont.truetype(path_or_none, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def get_font(family: str, size: int, source: str = "google", custom_path: Optional[str] = None):
    """Main entrypoint used by the render engine. Always returns a usable
    PIL ImageFont, falling back to the default bitmap font on any failure."""
    path = resolve_font_path(family, source, custom_path) or ""
    return _load_font_cached(path, size)
