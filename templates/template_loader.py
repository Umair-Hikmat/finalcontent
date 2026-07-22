"""
Loads full-video templates (JSON) from templates/library/ and applies them
to a Project, overriding background/font/animation/timing/render defaults
while always preserving the user's quiz content.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from config import settings
from core.models import (
    AnimationConfig, AudioConfig, BackgroundConfig, FontConfig, Project,
    RenderSettings, SceneTiming,
)


def _library_dir() -> Path:
    return settings.templates_dir


def list_templates() -> List[Dict]:
    """Return metadata for every template JSON in the library, for the gallery UI."""
    out = []
    for f in sorted(_library_dir().glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out.append({
                "id": data.get("id", f.stem),
                "name": data.get("name", f.stem.title()),
                "description": data.get("description", ""),
                "preview_colors": [
                    data.get("background", {}).get("color_start", "#333333"),
                    data.get("background", {}).get("color_end", "#111111"),
                ],
                "path": str(f),
            })
        except Exception:
            continue
    return out


def load_template_raw(template_id: str) -> Optional[Dict]:
    for f in _library_dir().glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("id") == template_id or f.stem == template_id:
                return data
        except Exception:
            continue
    return None


def apply_template(project: Project, template_id: str) -> Project:
    """Mutates & returns `project` with the template's styling applied.
    Quiz content (title/questions) is left untouched."""
    data = load_template_raw(template_id)
    if data is None:
        return project

    project.template_id = data.get("id", template_id)

    if "background" in data:
        project.background = BackgroundConfig(**data["background"])
    if "font" in data:
        project.font = FontConfig(**data["font"])
    if "timing" in data:
        project.timing = SceneTiming(**data["timing"])
    if "render" in data:
        # keep user's chosen output format if already set, merge the rest
        merged = project.render.model_dump()
        merged.update(data["render"])
        project.render = RenderSettings(**merged)
    if "animations" in data:
        project.animations = data["animations"]
    if "audio" in data:
        merged_audio = project.audio.model_dump()
        merged_audio.update({k: v for k, v in data["audio"].items() if v})
        project.audio = AudioConfig(**merged_audio)

    return project


def save_as_template(project: Project, template_id: str, name: str, description: str = "") -> Path:
    """Lets a user save their current styling as a reusable template."""
    payload = {
        "id": template_id,
        "name": name,
        "description": description,
        "background": project.background.model_dump(),
        "font": project.font.model_dump(),
        "timing": project.timing.model_dump(),
        "render": project.render.model_dump(),
        "animations": project.animations,
        "audio": {k: v for k, v in project.audio.model_dump().items() if k.startswith("sfx_") or k == "music_path"},
    }
    path = _library_dir() / f"{template_id}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
