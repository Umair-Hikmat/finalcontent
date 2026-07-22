"""
The heart of AI Quiz Studio: turns a Project into a rendered MP4.

Pipeline:
  1. build_schedule()   -> ordered list of ScheduledScene (type, start, duration, question index)
  2. SceneRenderer       -> draws a single PIL frame for any (scene, local_time)
  3. render_project()    -> wraps each scene in a MoviePy VideoClip(make_frame=...),
                             concatenates them, attaches audio, writes the MP4.

Frame drawing uses Pillow only (fast, no video decode needed) except for
video/gif backgrounds which sample an underlying MoviePy clip.
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from core.cache import make_key
from core.models import Project, Question, SceneType
from editor.font_manager import get_font
from engines.animations import animate
from engines.background_engine import BackgroundRenderer
from utils.helpers import hex_to_rgb, hex_to_rgba, ease_in_out_quad


# --------------------------------------------------------------------------- #
# Scheduling
# --------------------------------------------------------------------------- #

@dataclass
class ScheduledScene:
    scene_type: SceneType
    start: float
    duration: float
    question_index: Optional[int] = None  # index into project.quiz.questions, if applicable


def build_schedule(project: Project) -> List[ScheduledScene]:
    schedule: List[ScheduledScene] = []
    t = 0.0
    timing = project.timing

    schedule.append(ScheduledScene(SceneType.INTRO, t, timing.intro))
    t += timing.intro

    for qi, _ in enumerate(project.quiz.questions):
        for scene_type, dur in [
            (SceneType.QUESTION, timing.question),
            (SceneType.TIMER, timing.timer),
            (SceneType.ANSWER_REVEAL, timing.answer_reveal),
            (SceneType.FUN_FACT, timing.fun_fact),
        ]:
            schedule.append(ScheduledScene(scene_type, t, dur, question_index=qi))
            t += dur

    schedule.append(ScheduledScene(SceneType.OUTRO, t, timing.outro))
    t += timing.outro
    return schedule


# --------------------------------------------------------------------------- #
# Drawing helpers
# --------------------------------------------------------------------------- #

def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    if not text:
        return [""]
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        w = draw.textlength(trial, font=font)
        if w <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_centered_text(draw: ImageDraw.ImageDraw, center_xy: Tuple[float, float], text: str,
                         font: ImageFont.FreeTypeFont, fill, stroke_fill=None, stroke_width=0,
                         max_width: Optional[int] = None, line_spacing: int = 12,
                         glow_amount: float = 0.0, base_image: Optional[Image.Image] = None):
    cx, cy = center_xy
    lines = _wrap_text(text, font, max_width, draw) if max_width else [text]

    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line or " ", font=font, stroke_width=stroke_width)
        line_heights.append(bbox[3] - bbox[1])
    total_h = sum(line_heights) + line_spacing * (len(lines) - 1)

    y = cy - total_h / 2
    for line, lh in zip(lines, line_heights):
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
        w = bbox[2] - bbox[0]
        x = cx - w / 2

        if glow_amount > 0 and base_image is not None:
            glow_layer = Image.new("RGBA", base_image.size, (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_layer)
            glow_color = fill if isinstance(fill, tuple) else hex_to_rgba(str(fill))
            glow_draw.text((x, y), line, font=font, fill=(glow_color[0], glow_color[1], glow_color[2], int(200 * glow_amount)))
            blur_radius = 6 + 14 * glow_amount
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(blur_radius))
            base_image.alpha_composite(glow_layer)

        draw.text((x, y), line, font=font, fill=fill, stroke_fill=stroke_fill, stroke_width=stroke_width)
        y += lh + line_spacing


def _rounded_rect(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=0):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


# --------------------------------------------------------------------------- #
# Scene renderer
# --------------------------------------------------------------------------- #

class SceneRenderer:
    def __init__(self, project: Project):
        self.project = project
        self.size = project.render.resolution()
        self.bg = BackgroundRenderer(project.background, self.size)
        f = project.font
        self.font_title = get_font(f.family, int(f.size * 1.15), f.source, f.custom_path)
        self.font_body = get_font(f.family, f.size, f.source, f.custom_path)
        self.font_option = get_font(f.family, int(f.size * 0.75), f.source, f.custom_path)
        self.font_small = get_font(f.family, int(f.size * 0.55), f.source, f.custom_path)
        self.font_timer = get_font(f.family, int(f.size * 2.2), f.source, f.custom_path)

    def close(self):
        self.bg.close()

    # -- public API ---------------------------------------------------------

    def render_frame(self, scene: ScheduledScene, local_t: float) -> Image.Image:
        base = self.bg.frame_pil(scene.start + local_t).convert("RGBA")
        draw = ImageDraw.Draw(base)

        anim_cfg = self.project.animation_for(scene.scene_type)
        question = None
        if scene.question_index is not None and scene.question_index < len(self.project.quiz.questions):
            question = self.project.quiz.questions[scene.question_index]

        if scene.scene_type == SceneType.INTRO:
            self._draw_intro(base, draw, local_t, scene.duration, anim_cfg)
        elif scene.scene_type == SceneType.QUESTION:
            self._draw_question(base, draw, local_t, scene.duration, anim_cfg, question)
        elif scene.scene_type == SceneType.TIMER:
            self._draw_timer(base, draw, local_t, scene.duration, anim_cfg, question)
        elif scene.scene_type == SceneType.ANSWER_REVEAL:
            self._draw_answer_reveal(base, draw, local_t, scene.duration, anim_cfg, question)
        elif scene.scene_type == SceneType.FUN_FACT:
            self._draw_fun_fact(base, draw, local_t, scene.duration, anim_cfg, question)
        elif scene.scene_type == SceneType.OUTRO:
            self._draw_outro(base, draw, local_t, scene.duration, anim_cfg)

        return base.convert("RGB")

    # -- individual scenes ---------------------------------------------------

    def _apply_common(self, params: dict) -> Tuple[float, float, float, float]:
        """Returns (opacity, scale, offset_x, offset_y) ready to use."""
        return params["opacity"], params["scale"], params["offset_x"], params["offset_y"]

    def _draw_intro(self, base, draw, t, dur, anim_cfg):
        w, h = self.size
        text = self.project.quiz.title
        params = animate(t, dur, anim_cfg, text_len=len(text), frame_w=w, frame_h=h)
        opacity, scale, ox, oy = self._apply_common(params)

        color = hex_to_rgba(self.project.font.color, int(255 * opacity))
        font = get_font(self.project.font.family, int(self.font_title.size * scale),
                         self.project.font.source, self.project.font.custom_path)
        _draw_centered_text(draw, (w / 2 + ox, h * 0.42 + oy), text, font, color,
                             stroke_fill=hex_to_rgba(self.project.font.stroke_color or "#000000", int(255 * opacity)),
                             stroke_width=self.project.font.stroke_width, max_width=int(w * 0.85),
                             glow_amount=params["glow"], base_image=base)

        sub_font = get_font(self.project.font.family, int(self.font_small.size), self.project.font.source, self.project.font.custom_path)
        sub_color = hex_to_rgba("#EAEAEA", int(220 * opacity))
        _draw_centered_text(draw, (w / 2 + ox, h * 0.42 + oy + self.font_title.size + 40), self.project.quiz.subtitle,
                             sub_font, sub_color, max_width=int(w * 0.8))

        badge_text = f"{len(self.project.quiz.questions)} QUESTIONS"
        _rounded_rect(draw, (w / 2 - 180, h * 0.65, w / 2 + 180, h * 0.65 + 70), 35,
                      fill=hex_to_rgba("#FFFFFF", int(40 * opacity)))
        _draw_centered_text(draw, (w / 2, h * 0.65 + 35), badge_text, self.font_small,
                             hex_to_rgba("#FFFFFF", int(255 * opacity)))

    def _draw_question(self, base, draw, t, dur, anim_cfg, question: Optional[Question]):
        w, h = self.size
        if question is None:
            return
        params = animate(t, dur, anim_cfg, text_len=len(question.prompt), frame_w=w, frame_h=h)
        opacity, scale, ox, oy = self._apply_common(params)
        color = hex_to_rgba(self.project.font.color, int(255 * opacity))

        _rounded_rect(draw, (60, 90, w - 60, 260), 24, fill=hex_to_rgba("#000000", int(120 * opacity)))
        prompt_text = question.prompt
        if params["chars"] is not None:
            prompt_text = prompt_text[:params["chars"]]
        _draw_centered_text(draw, (w / 2 + ox, 175 + oy), prompt_text, self.font_body, color,
                             max_width=int(w * 0.8), glow_amount=params["glow"], base_image=base)

        # option cards, 2x2 grid
        margin = 70
        gap = 24
        card_w = (w - margin * 2 - gap) / 2
        card_h = 170
        start_y = h * 0.55
        palette = ["#FF5C7C", "#3EC1D3", "#FFB65C", "#8C6BFA"]
        for i, opt in enumerate(question.options[:4]):
            row, col = divmod(i, 2)
            x0 = margin + col * (card_w + gap)
            y0 = start_y + row * (card_h + gap)
            fill_color = hex_to_rgba(palette[i % len(palette)], int(230 * opacity))
            _rounded_rect(draw, (x0 + ox, y0 + oy, x0 + card_w + ox, y0 + card_h + oy), 28, fill=fill_color)
            letter = chr(65 + i)
            _draw_centered_text(draw, (x0 + 60 + ox, y0 + card_h / 2 + oy), letter, self.font_body,
                                 hex_to_rgba("#FFFFFF", int(255 * opacity)))
            _draw_centered_text(draw, (x0 + card_w / 2 + 30 + ox, y0 + card_h / 2 + oy), opt.text,
                                 self.font_option, hex_to_rgba("#FFFFFF", int(255 * opacity)),
                                 max_width=int(card_w - 140))

    def _draw_timer(self, base, draw, t, dur, anim_cfg, question: Optional[Question]):
        w, h = self.size
        params = animate(t, dur, anim_cfg, frame_w=w, frame_h=h)
        opacity, scale, ox, oy = self._apply_common(params)

        remaining = max(0, dur - t)
        seconds_left = max(0, int(remaining) + (1 if remaining % 1 > 0 else 0))

        cx, cy = w / 2 + ox, h * 0.45 + oy
        radius = 160 * scale
        progress = 1 - (t / dur if dur > 0 else 0)

        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius),
                      outline=hex_to_rgba("#FFFFFF", int(60 * opacity)), width=14)
        bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
        start_angle = -90
        end_angle = start_angle + 360 * progress
        draw.arc(bbox, start=start_angle, end=end_angle, fill=hex_to_rgba("#FFD447", int(255 * opacity)), width=14)

        _draw_centered_text(draw, (cx, cy), str(seconds_left), self.font_timer,
                             hex_to_rgba("#FFFFFF", int(255 * opacity)),
                             glow_amount=params["glow"], base_image=base)

        _draw_centered_text(draw, (w / 2, h * 0.7), "TIME'S TICKING\u2026", self.font_small,
                             hex_to_rgba("#FFFFFF", int(200 * opacity)))

    def _draw_answer_reveal(self, base, draw, t, dur, anim_cfg, question: Optional[Question]):
        w, h = self.size
        if question is None:
            return
        params = animate(t, dur, anim_cfg, frame_w=w, frame_h=h)
        opacity, scale, ox, oy = self._apply_common(params)

        _draw_centered_text(draw, (w / 2, h * 0.28), "ANSWER REVEALED!", self.font_body,
                             hex_to_rgba("#FFD447", int(255 * opacity)), glow_amount=params["glow"], base_image=base)

        margin = 70
        gap = 24
        card_w = (w - margin * 2 - gap) / 2
        card_h = 170
        start_y = h * 0.5
        for i, opt in enumerate(question.options[:4]):
            row, col = divmod(i, 2)
            x0 = margin + col * (card_w + gap)
            y0 = start_y + row * (card_h + gap)
            is_correct = opt.id == question.correct_option_id
            fill_color = hex_to_rgba("#3DDC84" if is_correct else "#3A3A46", int(230 * opacity))
            scale_i = 1.08 if is_correct else 0.96
            cx0, cy0 = x0 + card_w / 2, y0 + card_h / 2
            hw, hh = (card_w / 2) * scale_i, (card_h / 2) * scale_i
            _rounded_rect(draw, (cx0 - hw + ox, cy0 - hh + oy, cx0 + hw + ox, cy0 + hh + oy), 28, fill=fill_color)
            label = f"{chr(65 + i)}. {opt.text}" + ("  \u2713" if is_correct else "")
            _draw_centered_text(draw, (cx0 + ox, cy0 + oy), label, self.font_option,
                                 hex_to_rgba("#FFFFFF", int(255 * opacity)), max_width=int(card_w - 60))

    def _draw_fun_fact(self, base, draw, t, dur, anim_cfg, question: Optional[Question]):
        w, h = self.size
        if question is None:
            return
        text = question.fun_fact or "Did you know? Every question here was picked to make you smarter!"
        params = animate(t, dur, anim_cfg, text_len=len(text), frame_w=w, frame_h=h)
        opacity, scale, ox, oy = self._apply_common(params)

        _rounded_rect(draw, (80, h * 0.35, w - 80, h * 0.65), 40, fill=hex_to_rgba("#000000", int(140 * opacity)))
        _draw_centered_text(draw, (w / 2, h * 0.3), "\U0001F4A1 FUN FACT", self.font_body,
                             hex_to_rgba("#FFD447", int(255 * opacity)))

        display_text = text
        if params["chars"] is not None:
            display_text = text[:params["chars"]]
        _draw_centered_text(draw, (w / 2 + ox, h * 0.5 + oy), display_text, self.font_option,
                             hex_to_rgba("#FFFFFF", int(255 * opacity)), max_width=int(w * 0.75))

    def _draw_outro(self, base, draw, t, dur, anim_cfg):
        w, h = self.size
        params = animate(t, dur, anim_cfg, frame_w=w, frame_h=h)
        opacity, scale, ox, oy = self._apply_common(params)
        _draw_centered_text(draw, (w / 2 + ox, h * 0.45 + oy), "THANKS FOR PLAYING!", self.font_title,
                             hex_to_rgba(self.project.font.color, int(255 * opacity)),
                             glow_amount=params["glow"], base_image=base, max_width=int(w * 0.85))
        _draw_centered_text(draw, (w / 2, h * 0.58), "Follow for more quizzes \u2764\ufe0f", self.font_small,
                             hex_to_rgba("#EAEAEA", int(220 * opacity)))


# --------------------------------------------------------------------------- #
# Top-level render
# --------------------------------------------------------------------------- #

ProgressCB = Optional[Callable[[float, str], None]]


def render_project(project: Project, output_path: Path, progress_cb: ProgressCB = None) -> Path:
    """Renders the entire project to an MP4 file at `output_path`."""
    from moviepy.editor import VideoClip, concatenate_videoclips

    schedule = build_schedule(project)
    total_duration = schedule[-1].start + schedule[-1].duration if schedule else 0.0
    renderer = SceneRenderer(project)

    clips = []
    try:
        for i, scene in enumerate(schedule):
            def make_frame(local_t, _scene=scene):
                img = renderer.render_frame(_scene, local_t)
                return np.array(img)

            clip = VideoClip(make_frame, duration=max(scene.duration, 1 / project.render.fps))
            clips.append(clip)
            if progress_cb:
                progress_cb((i + 1) / max(len(schedule), 1) * 0.5, f"Building scene {i + 1}/{len(schedule)}")

        final = concatenate_videoclips(clips, method="compose")
        final = final.set_fps(project.render.fps)

        # Audio
        try:
            from engines.audio_engine import build_audio_track
            audio_clip = build_audio_track(project.audio, schedule, total_duration)
            if audio_clip is not None:
                final = final.set_audio(audio_clip)
        except Exception:
            pass

        if progress_cb:
            progress_cb(0.55, "Encoding video with FFmpeg\u2026")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        final.write_videofile(
            str(output_path),
            fps=project.render.fps,
            codec=project.render.codec,
            audio_codec=project.render.audio_codec,
            bitrate=project.render.bitrate(),
            threads=4,
            preset="medium" if project.render.quality == "high" else "veryfast",
            logger=None,
        )

        if progress_cb:
            progress_cb(1.0, "Done!")

    finally:
        renderer.close()
        for c in clips:
            try:
                c.close()
            except Exception:
                pass

    return output_path


def render_cache_key(project: Project) -> str:
    return make_key(project.model_dump(mode="json"))
