"""
Animation engine: pure functions that turn (elapsed_time, config) into
drawing parameters. Kept independent of PIL/MoviePy so they're easy to
unit test and reuse across scene types.

Every function returns a dict of parameters that the renderer applies when
compositing a layer (text block, image, option card) onto a frame:

    opacity      float 0..1
    scale        float (1.0 = 100%)
    offset_x/y   pixels
    glitch_dx    pixels of per-frame RGB channel split (0 = none)
    glow         float 0..1 intensity of outer glow
    chars        int, how many characters of a string should be visible (typewriter)
"""
from __future__ import annotations

import math
import random
from typing import Dict

from core.models import AnimationConfig, AnimationType, SlideDirection
from utils.helpers import ease_out_bounce, ease_out_cubic, ease_in_out_quad

DEFAULT_PARAMS = {
    "opacity": 1.0,
    "scale": 1.0,
    "offset_x": 0.0,
    "offset_y": 0.0,
    "glitch_dx": 0.0,
    "glow": 0.0,
    "chars": None,  # None => show full text
}


def animate(t: float, scene_duration: float, cfg: AnimationConfig, text_len: int = 0,
            frame_w: int = 1080, frame_h: int = 1920) -> Dict:
    """t: seconds elapsed since the scene started."""
    params = dict(DEFAULT_PARAMS)

    t_eff = t - cfg.delay
    if t_eff < 0:
        params["opacity"] = 0.0
        params["chars"] = 0
        return params

    d = max(cfg.duration, 0.05)
    progress_in = min(t_eff / d, 1.0)  # 0..1 entrance progress

    # Exit animation window: last `d` seconds of the scene fade things back out
    time_left = scene_duration - t_eff
    progress_out = 1.0
    if time_left < d:
        progress_out = max(time_left, 0.0) / d

    if cfg.type == AnimationType.NONE:
        pass

    elif cfg.type == AnimationType.FADE:
        params["opacity"] = ease_in_out_quad(progress_in) * ease_in_out_quad(progress_out)

    elif cfg.type == AnimationType.ZOOM:
        scale_in = 0.5 + 0.5 * ease_out_cubic(progress_in)
        params["scale"] = scale_in * (0.85 + 0.15 * ease_in_out_quad(progress_out))
        params["opacity"] = min(1.0, progress_in * 3) * ease_in_out_quad(progress_out)

    elif cfg.type == AnimationType.SLIDE:
        distance = 400 * cfg.intensity
        direction_vec = {
            SlideDirection.LEFT: (1, 0),
            SlideDirection.RIGHT: (-1, 0),
            SlideDirection.UP: (0, 1),
            SlideDirection.DOWN: (0, -1),
        }[cfg.direction]
        eased = ease_out_cubic(progress_in)
        params["offset_x"] = direction_vec[0] * distance * (1 - eased)
        params["offset_y"] = direction_vec[1] * distance * (1 - eased)
        params["opacity"] = ease_in_out_quad(progress_in) * ease_in_out_quad(progress_out)

    elif cfg.type == AnimationType.BOUNCE:
        eased = ease_out_bounce(progress_in)
        params["offset_y"] = (1 - eased) * -250 * cfg.intensity
        params["scale"] = 1.0 + 0.08 * math.sin(progress_in * math.pi)
        params["opacity"] = min(1.0, progress_in * 4) * ease_in_out_quad(progress_out)

    elif cfg.type == AnimationType.GLITCH:
        params["opacity"] = ease_in_out_quad(progress_in) * ease_in_out_quad(progress_out)
        # glitch is strongest right at entrance, settles down after `duration`
        if progress_in < 1.0:
            rnd = random.Random(int(t_eff * 60))  # deterministic per-frame jitter
            params["glitch_dx"] = (rnd.random() - 0.5) * 40 * cfg.intensity * (1 - progress_in)
        else:
            params["glitch_dx"] = 0.0

    elif cfg.type == AnimationType.TYPEWRITER:
        params["opacity"] = 1.0 * ease_in_out_quad(progress_out)
        chars_per_sec = max(text_len / d, 1)
        params["chars"] = min(text_len, int(t_eff * chars_per_sec))

    elif cfg.type == AnimationType.GLOW:
        pulse = 0.5 + 0.5 * math.sin(t_eff * 4.0)
        params["glow"] = pulse * cfg.intensity
        params["opacity"] = ease_in_out_quad(progress_in) * ease_in_out_quad(progress_out)

    return params
