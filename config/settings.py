"""
Central configuration for AI Quiz Studio.
All paths are resolved relative to the project root so the app works
identically on local machines, Docker containers, and Cloud Run.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def _writable_dir(path: Path) -> Path:
    """Ensure a directory exists and is writable; fall back to /tmp on
    read-only deployments (e.g. some serverless containers)."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
        return path
    except Exception:
        fallback = Path("/tmp") / path.relative_to(ROOT_DIR)
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


@dataclass
class Settings:
    app_name: str = "AI Quiz Studio"
    version: str = "1.0.0"

    root_dir: Path = ROOT_DIR
    assets_dir: Path = ROOT_DIR / "assets"
    fonts_dir: Path = ROOT_DIR / "assets" / "fonts"
    images_dir: Path = ROOT_DIR / "assets" / "images"
    backgrounds_dir: Path = ROOT_DIR / "assets" / "backgrounds"
    music_dir: Path = ROOT_DIR / "assets" / "audio" / "music"
    sfx_dir: Path = ROOT_DIR / "assets" / "audio" / "sfx"

    templates_dir: Path = ROOT_DIR / "templates" / "library"

    projects_dir: Path = ROOT_DIR / "data" / "projects"
    exports_dir: Path = ROOT_DIR / "data" / "exports"
    cache_dir: Path = ROOT_DIR / "data" / ".cache"

    # Video defaults
    default_fps: int = 30
    shorts_size: tuple = (1080, 1920)
    youtube_size: tuple = (1920, 1080)

    # Google Fonts API (no key required for the CSS2 endpoint, but an
    # API key enables the metadata endpoint with more font families)
    google_fonts_api_key: str = field(default_factory=lambda: os.environ.get("GOOGLE_FONTS_API_KEY", ""))

    def __post_init__(self):
        for d in [
            self.assets_dir, self.fonts_dir, self.images_dir, self.backgrounds_dir,
            self.music_dir, self.sfx_dir, self.templates_dir,
            self.projects_dir, self.exports_dir, self.cache_dir,
        ]:
            _writable_dir(d)


settings = Settings()
