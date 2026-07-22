"""
Handles JSON persistence for Project objects: save, load, list, delete, duplicate.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from slugify import slugify

from config import settings
from core.models import Project


class ProjectManager:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.projects_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, project: Project) -> Path:
        slug = slugify(project.name) or project.id
        return self.base_dir / f"{slug}-{project.id}.json"

    def save(self, project: Project) -> Path:
        project.touch()
        path = self._path_for(project)
        path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load(self, path: Path | str) -> Project:
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return Project(**data)

    def list_projects(self) -> List[dict]:
        """Return lightweight metadata (no full quiz body) for the dashboard list."""
        results = []
        for f in sorted(self.base_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results.append({
                    "path": str(f),
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "updated_at": data.get("updated_at"),
                    "num_questions": len(data.get("quiz", {}).get("questions", [])),
                    "template_id": data.get("template_id"),
                })
            except Exception:
                continue
        return results

    def delete(self, path: Path | str) -> None:
        p = Path(path)
        if p.exists() and p.parent == self.base_dir:
            p.unlink()

    def duplicate(self, path: Path | str, new_name: Optional[str] = None) -> Project:
        project = self.load(path)
        project.id = Project().id  # fresh id
        project.name = new_name or f"{project.name} (copy)"
        self.save(project)
        return project


project_manager = ProjectManager()
