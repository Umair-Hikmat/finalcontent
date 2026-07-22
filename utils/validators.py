"""Validation helpers for uploaded files and quiz content sanity checks."""
from __future__ import annotations

from pathlib import Path
from typing import List

from core.models import Quiz

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".webm"}
ALLOWED_GIF_EXT = {".gif"}
ALLOWED_AUDIO_EXT = {".mp3", ".wav", ".ogg", ".m4a"}
ALLOWED_FONT_EXT = {".ttf", ".otf"}

MAX_UPLOAD_MB = 200


def validate_extension(filename: str, allowed: set) -> bool:
    return Path(filename).suffix.lower() in allowed


def validate_file_size(size_bytes: int, max_mb: int = MAX_UPLOAD_MB) -> bool:
    return size_bytes <= max_mb * 1024 * 1024


def validate_quiz(quiz: Quiz) -> List[str]:
    """Return a list of human-readable problems; empty list = valid quiz."""
    errors = []
    if not quiz.title.strip():
        errors.append("Quiz title is empty.")
    if not quiz.questions:
        errors.append("Add at least one question.")
    for i, q in enumerate(quiz.questions, start=1):
        if not q.prompt.strip():
            errors.append(f"Question {i}: prompt is empty.")
        non_empty = [o for o in q.options if o.text.strip()]
        if len(non_empty) < 2:
            errors.append(f"Question {i}: needs at least 2 non-empty options.")
        if not q.correct_option_id:
            errors.append(f"Question {i}: no correct answer selected.")
        elif q.correct_option_id not in [o.id for o in q.options]:
            errors.append(f"Question {i}: correct answer id does not match any option.")
    return errors
