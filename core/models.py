"""
Pydantic v2 data models for AI Quiz Studio.

These models are the single source of truth for:
- quiz content (questions/options/fun facts)
- per-scene animation & timing configuration
- backgrounds, fonts, audio
- the full "Project" that gets saved/loaded as JSON

Everything the renderer needs is derivable from a `Project` instance.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #

class SceneType(str, Enum):
    INTRO = "intro"
    QUESTION = "question"
    TIMER = "timer"
    ANSWER_REVEAL = "answer_reveal"
    FUN_FACT = "fun_fact"
    OUTRO = "outro"


class AnimationType(str, Enum):
    NONE = "none"
    FADE = "fade"
    ZOOM = "zoom"
    SLIDE = "slide"
    BOUNCE = "bounce"
    GLITCH = "glitch"
    TYPEWRITER = "typewriter"
    GLOW = "glow"


class BackgroundType(str, Enum):
    SOLID = "solid"
    GRADIENT = "gradient"
    PARTICLES = "particles"
    IMAGE = "image"
    VIDEO_MP4 = "video_mp4"
    GIF = "gif"


class VideoFormat(str, Enum):
    SHORTS = "shorts"       # 1080x1920
    YOUTUBE = "youtube"     # 1920x1080
    SQUARE = "square"       # 1080x1080


class SlideDirection(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


# --------------------------------------------------------------------------- #
# Sub-configuration models
# --------------------------------------------------------------------------- #

class FontConfig(BaseModel):
    family: str = "Poppins"
    source: str = Field("google", description="'google' or 'custom'")
    custom_path: Optional[str] = None
    size: int = 64
    color: str = "#FFFFFF"
    bold: bool = True
    italic: bool = False
    stroke_color: Optional[str] = "#000000"
    stroke_width: int = 2


class BackgroundConfig(BaseModel):
    type: BackgroundType = BackgroundType.GRADIENT
    color_start: str = "#6a11cb"
    color_end: str = "#2575fc"
    gradient_angle: int = 135
    media_path: Optional[str] = None
    particle_count: int = 60
    particle_color: str = "#FFFFFF"
    blur: int = 0
    overlay_opacity: float = 0.0


class AnimationConfig(BaseModel):
    type: AnimationType = AnimationType.FADE
    duration: float = 0.6
    direction: SlideDirection = SlideDirection.LEFT
    intensity: float = 1.0  # generic multiplier (zoom scale, bounce height, glitch strength...)
    delay: float = 0.0


class AudioConfig(BaseModel):
    music_path: Optional[str] = None
    music_volume: float = 0.5
    sfx_tick_path: Optional[str] = None
    sfx_correct_path: Optional[str] = None
    sfx_wrong_path: Optional[str] = None
    sfx_reveal_path: Optional[str] = None
    voiceover_path: Optional[str] = None
    sfx_volume: float = 0.8


class SceneTiming(BaseModel):
    """Duration (seconds) for each scene type; used by the timeline builder."""
    intro: float = 3.0
    question: float = 4.0
    timer: float = 5.0
    answer_reveal: float = 3.0
    fun_fact: float = 4.0
    outro: float = 3.0

    def duration_for(self, scene: SceneType) -> float:
        return getattr(self, scene.value)


class RenderSettings(BaseModel):
    format: VideoFormat = VideoFormat.SHORTS
    fps: int = 30
    quality: str = Field("high", description="'draft' | 'standard' | 'high'")
    codec: str = "libx264"
    audio_codec: str = "aac"

    def resolution(self) -> tuple:
        return {
            VideoFormat.SHORTS: (1080, 1920),
            VideoFormat.YOUTUBE: (1920, 1080),
            VideoFormat.SQUARE: (1080, 1080),
        }[self.format]

    def bitrate(self) -> str:
        return {"draft": "2000k", "standard": "5000k", "high": "9000k"}.get(self.quality, "5000k")


# --------------------------------------------------------------------------- #
# Quiz content models
# --------------------------------------------------------------------------- #

class Option(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:6])
    text: str = ""


class Question(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    prompt: str = "Untitled question"
    options: List[Option] = Field(default_factory=lambda: [Option(text="") for _ in range(4)])
    correct_option_id: Optional[str] = None
    fun_fact: str = ""
    image_path: Optional[str] = None
    timer_seconds: int = 5
    points: int = 100

    @field_validator("options")
    @classmethod
    def must_have_options(cls, v: List[Option]) -> List[Option]:
        if len(v) < 2:
            raise ValueError("A question needs at least 2 options")
        return v

    def correct_option(self) -> Optional[Option]:
        for opt in self.options:
            if opt.id == self.correct_option_id:
                return opt
        return None


class Quiz(BaseModel):
    title: str = "My Quiz"
    subtitle: str = "How much do you know?"
    author: str = ""
    questions: List[Question] = Field(default_factory=list)

    def add_blank_question(self) -> Question:
        q = Question()
        self.questions.append(q)
        return q


# --------------------------------------------------------------------------- #
# Project (top-level, serialized as JSON)
# --------------------------------------------------------------------------- #

class Project(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    name: str = "Untitled Project"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    template_id: str = "neon_pulse"

    quiz: Quiz = Field(default_factory=Quiz)

    background: BackgroundConfig = Field(default_factory=BackgroundConfig)
    font: FontConfig = Field(default_factory=FontConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    timing: SceneTiming = Field(default_factory=SceneTiming)
    render: RenderSettings = Field(default_factory=RenderSettings)

    # per-scene-type animation overrides
    animations: dict = Field(
        default_factory=lambda: {
            SceneType.INTRO.value: AnimationConfig(type=AnimationType.ZOOM).model_dump(),
            SceneType.QUESTION.value: AnimationConfig(type=AnimationType.SLIDE).model_dump(),
            SceneType.TIMER.value: AnimationConfig(type=AnimationType.BOUNCE).model_dump(),
            SceneType.ANSWER_REVEAL.value: AnimationConfig(type=AnimationType.GLOW).model_dump(),
            SceneType.FUN_FACT.value: AnimationConfig(type=AnimationType.TYPEWRITER).model_dump(),
            SceneType.OUTRO.value: AnimationConfig(type=AnimationType.FADE).model_dump(),
        }
    )

    def animation_for(self, scene: SceneType) -> AnimationConfig:
        raw = self.animations.get(scene.value)
        if raw is None:
            return AnimationConfig()
        return AnimationConfig(**raw)

    def touch(self):
        self.updated_at = datetime.utcnow()

    def scene_sequence(self) -> List[SceneType]:
        """Full ordered scene list for the whole video:
        Intro, then per-question (Question -> Timer -> Answer -> FunFact), then Outro."""
        seq = [SceneType.INTRO]
        for _ in self.quiz.questions:
            seq += [SceneType.QUESTION, SceneType.TIMER, SceneType.ANSWER_REVEAL, SceneType.FUN_FACT]
        seq.append(SceneType.OUTRO)
        return seq

    def total_duration(self) -> float:
        total = self.timing.intro + self.timing.outro
        total += len(self.quiz.questions) * (
            self.timing.question + self.timing.timer + self.timing.answer_reveal + self.timing.fun_fact
        )
        return total
