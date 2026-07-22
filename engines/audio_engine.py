"""
Builds the full audio track for a rendered video: looped background music
plus one-shot sound effects (tick, correct, wrong, reveal) placed at the
exact second they occur in the timeline, driven by the scene schedule
produced by engines.render_engine.build_schedule().
"""
from __future__ import annotations

from typing import List, Optional

from core.models import AudioConfig, SceneType
from engines.render_engine import ScheduledScene


def _safe_audio_clip(path: Optional[str]):
    if not path:
        return None
    try:
        from moviepy.editor import AudioFileClip
        return AudioFileClip(path)
    except Exception:
        return None


def build_audio_track(audio_cfg: AudioConfig, schedule: List[ScheduledScene], total_duration: float):
    """Returns a MoviePy AudioClip (CompositeAudioClip) or None if no audio configured."""
    from moviepy.editor import CompositeAudioClip, afx

    layers = []

    # 1. Background music, looped & trimmed to total duration, volume-adjusted
    music = _safe_audio_clip(audio_cfg.music_path)
    if music is not None:
        try:
            looped = music.fx(afx.audio_loop, duration=total_duration) if music.duration < total_duration else music.subclip(0, total_duration)
            looped = looped.volumex(audio_cfg.music_volume)
            layers.append(looped)
        except Exception:
            pass

    # 2. SFX per scene event
    sfx_map = {
        SceneType.TIMER: audio_cfg.sfx_tick_path,
        SceneType.ANSWER_REVEAL: audio_cfg.sfx_correct_path,
        SceneType.FUN_FACT: audio_cfg.sfx_reveal_path,
    }
    for scene in schedule:
        sfx_path = sfx_map.get(scene.scene_type)
        if not sfx_path:
            continue
        clip = _safe_audio_clip(sfx_path)
        if clip is None:
            continue
        try:
            clip = clip.volumex(audio_cfg.sfx_volume).set_start(scene.start)
            layers.append(clip)
        except Exception:
            pass

    # 3. Optional voiceover track (single, starts at t=0)
    voiceover = _safe_audio_clip(audio_cfg.voiceover_path)
    if voiceover is not None:
        layers.append(voiceover.set_start(0))

    if not layers:
        return None

    return CompositeAudioClip(layers).set_duration(total_duration)
