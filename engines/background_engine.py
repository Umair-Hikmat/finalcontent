"""
Generates the background layer for every frame of a scene.

Supported types (core.models.BackgroundType):
- SOLID     : flat color
- GRADIENT  : animated diagonal gradient (slow color drift)
- PARTICLES : floating particle system over a gradient base
- IMAGE     : static image, cover-fit
- VIDEO_MP4 : looped video file
- GIF       : looped GIF file

Everything returns a numpy uint8 array of shape (h, w, 3) for a given time t,
so it can be dropped straight into MoviePy's VideoClip(make_frame=...).
"""
from __future__ import annotations

import math
import random
from functools import lru_cache
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from core.models import BackgroundConfig, BackgroundType
from utils.helpers import hex_to_rgb, lerp_color


# --------------------------------------------------------------------------- #
# Gradient
# --------------------------------------------------------------------------- #

def _gradient_frame(size: Tuple[int, int], c1, c2, angle_deg: float, t: float) -> np.ndarray:
    w, h = size
    # slow hue drift by oscillating the interpolation midpoint over time
    drift = 0.15 * math.sin(t * 0.3)
    angle = math.radians(angle_deg)
    dx, dy = math.cos(angle), math.sin(angle)

    xs = np.linspace(0, 1, w)
    ys = np.linspace(0, 1, h)
    grid_x, grid_y = np.meshgrid(xs, ys)
    proj = grid_x * dx + grid_y * dy
    proj = (proj - proj.min()) / (proj.max() - proj.min() + 1e-6)
    proj = np.clip(proj + drift, 0, 1)

    c1 = np.array(c1, dtype=np.float32)
    c2 = np.array(c2, dtype=np.float32)
    frame = c1[None, None, :] + (c2 - c1)[None, None, :] * proj[:, :, None]
    return frame.astype(np.uint8)


# --------------------------------------------------------------------------- #
# Particles
# --------------------------------------------------------------------------- #

class ParticleSystem:
    """Deterministic particle field: positions are an analytic function of
    time so any frame can be rendered independently (no simulation state)."""

    def __init__(self, count: int, size: Tuple[int, int], seed: int = 42):
        self.size = size
        rnd = random.Random(seed)
        self.particles = []
        for _ in range(count):
            self.particles.append({
                "x0": rnd.uniform(0, size[0]),
                "y0": rnd.uniform(0, size[1]),
                "speed": rnd.uniform(15, 60),
                "drift": rnd.uniform(-20, 20),
                "radius": rnd.uniform(2, 6),
                "phase": rnd.uniform(0, math.tau),
                "twinkle_speed": rnd.uniform(1.0, 3.0),
            })

    def render(self, t: float, color_rgb) -> Image.Image:
        w, h = self.size
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        for p in self.particles:
            y = (p["y0"] - p["speed"] * t) % (h + 40) - 20
            x = (p["x0"] + p["drift"] * math.sin(t * 0.5 + p["phase"])) % w
            twinkle = 0.5 + 0.5 * math.sin(t * p["twinkle_speed"] + p["phase"])
            alpha = int(180 * twinkle)
            r = p["radius"]
            draw.ellipse(
                [x - r, y - r, x + r, y + r],
                fill=(color_rgb[0], color_rgb[1], color_rgb[2], alpha),
            )
        return layer


@lru_cache(maxsize=16)
def _get_particle_system(count: int, w: int, h: int, seed: int) -> ParticleSystem:
    return ParticleSystem(count, (w, h), seed=seed)


# --------------------------------------------------------------------------- #
# Media-backed backgrounds (image / video / gif)
# --------------------------------------------------------------------------- #

def _cover_resize(img: Image.Image, size: Tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


class MediaBackground:
    """Wraps a MoviePy clip (video or gif) for looped frame lookups."""

    def __init__(self, path: str, size: Tuple[int, int]):
        from moviepy.editor import VideoFileClip
        self.clip = VideoFileClip(path, audio=False)
        self.size = size
        self.duration = self.clip.duration or 1.0

    def frame_at(self, t: float) -> np.ndarray:
        loop_t = t % self.duration
        frame = self.clip.get_frame(loop_t)
        img = Image.fromarray(frame).convert("RGB")
        img = _cover_resize(img, self.size)
        return np.array(img)

    def close(self):
        try:
            self.clip.close()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Public entrypoint
# --------------------------------------------------------------------------- #

class BackgroundRenderer:
    def __init__(self, cfg: BackgroundConfig, size: Tuple[int, int]):
        self.cfg = cfg
        self.size = size
        self._media: Optional[MediaBackground] = None
        if cfg.type in (BackgroundType.VIDEO_MP4, BackgroundType.GIF) and cfg.media_path:
            try:
                self._media = MediaBackground(cfg.media_path, size)
            except Exception:
                self._media = None  # fall back to gradient if the file is bad/missing

        self._static_image = None
        if cfg.type == BackgroundType.IMAGE and cfg.media_path:
            try:
                self._static_image = _cover_resize(Image.open(cfg.media_path).convert("RGB"), size)
            except Exception:
                self._static_image = None

        self._particles = None
        if cfg.type == BackgroundType.PARTICLES:
            self._particles = _get_particle_system(cfg.particle_count, size[0], size[1], seed=7)

    def frame_rgb(self, t: float) -> np.ndarray:
        cfg = self.cfg
        c1 = hex_to_rgb(cfg.color_start)
        c2 = hex_to_rgb(cfg.color_end)

        if cfg.type == BackgroundType.SOLID:
            base = np.zeros((self.size[1], self.size[0], 3), dtype=np.uint8)
            base[:, :] = c1
            return base

        if cfg.type == BackgroundType.IMAGE and self._static_image is not None:
            return np.array(self._static_image)

        if cfg.type in (BackgroundType.VIDEO_MP4, BackgroundType.GIF) and self._media is not None:
            return self._media.frame_at(t)

        if cfg.type == BackgroundType.PARTICLES and self._particles is not None:
            base = _gradient_frame(self.size, c1, c2, cfg.gradient_angle, t)
            base_img = Image.fromarray(base).convert("RGBA")
            particle_layer = self._particles.render(t, hex_to_rgb(cfg.particle_color))
            composited = Image.alpha_composite(base_img, particle_layer).convert("RGB")
            return np.array(composited)

        # default / fallback: animated gradient
        return _gradient_frame(self.size, c1, c2, cfg.gradient_angle, t)

    def frame_pil(self, t: float) -> Image.Image:
        img = Image.fromarray(self.frame_rgb(t)).convert("RGB")
        if self.cfg.blur > 0:
            img = img.filter(ImageFilter.GaussianBlur(self.cfg.blur))
        if self.cfg.overlay_opacity > 0:
            overlay = Image.new("RGB", img.size, (0, 0, 0))
            img = Image.blend(img, overlay, self.cfg.overlay_opacity)
        return img

    def close(self):
        if self._media:
            self._media.close()
