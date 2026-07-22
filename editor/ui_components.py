"""
Reusable Streamlit widgets shared across the AI Quiz Studio dashboard pages.
Keeping these separate from app.py keeps the main file readable.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

import streamlit as st

from config import settings
from core.models import (
    AnimationConfig, AnimationType, BackgroundConfig, BackgroundType,
    FontConfig, Option, Question, SlideDirection,
)
from editor.font_manager import CURATED_GOOGLE_FONTS, list_installed_fonts, save_custom_font
from utils.validators import (
    ALLOWED_AUDIO_EXT, ALLOWED_FONT_EXT, ALLOWED_GIF_EXT, ALLOWED_IMAGE_EXT,
    ALLOWED_VIDEO_EXT, validate_extension, validate_file_size,
)


def save_upload(uploaded_file, dest_dir: Path) -> Optional[str]:
    """Persists a Streamlit UploadedFile to disk and returns its path, or None."""
    if uploaded_file is None:
        return None
    if not validate_file_size(uploaded_file.size):
        st.error(f"'{uploaded_file.name}' is too large (max 200MB).")
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex[:8]}_{uploaded_file.name}"
    dest = dest_dir / unique_name
    dest.write_bytes(uploaded_file.getbuffer())
    return str(dest)


def font_picker(font_cfg: FontConfig, key_prefix: str) -> FontConfig:
    st.markdown("**Font**")
    col1, col2 = st.columns([2, 1])
    with col1:
        source = st.radio("Source", ["google", "custom"], horizontal=True,
                           index=0 if font_cfg.source == "google" else 1, key=f"{key_prefix}_font_source")
    with col2:
        pass

    custom_path = font_cfg.custom_path
    family = font_cfg.family
    if source == "google":
        options = sorted(set(CURATED_GOOGLE_FONTS))
        idx = options.index(family) if family in options else 0
        family = st.selectbox("Google Font family", options, index=idx, key=f"{key_prefix}_family")
    else:
        uploaded = st.file_uploader("Upload custom .ttf / .otf", type=["ttf", "otf"], key=f"{key_prefix}_ttf")
        if uploaded is not None and validate_extension(uploaded.name, ALLOWED_FONT_EXT):
            path = save_custom_font(uploaded.getbuffer(), uploaded.name)
            custom_path = str(path)
            family = Path(uploaded.name).stem
            st.success(f"Custom font saved: {uploaded.name}")
        installed = list_installed_fonts()
        if installed:
            st.caption("Installed fonts: " + ", ".join(installed))

    c1, c2, c3 = st.columns(3)
    with c1:
        size = st.slider("Size", 24, 120, font_cfg.size, key=f"{key_prefix}_size")
    with c2:
        color = st.color_picker("Color", font_cfg.color, key=f"{key_prefix}_color")
    with c3:
        stroke_color = st.color_picker("Stroke color", font_cfg.stroke_color or "#000000", key=f"{key_prefix}_stroke")

    bold = st.checkbox("Bold", font_cfg.bold, key=f"{key_prefix}_bold")
    stroke_width = st.slider("Stroke width", 0, 8, font_cfg.stroke_width, key=f"{key_prefix}_strokew")

    return FontConfig(
        family=family, source=source, custom_path=custom_path, size=size, color=color,
        bold=bold, stroke_color=stroke_color, stroke_width=stroke_width,
    )


def background_editor(bg_cfg: BackgroundConfig, key_prefix: str) -> BackgroundConfig:
    st.markdown("**Background**")
    type_labels = {
        BackgroundType.SOLID: "Solid color",
        BackgroundType.GRADIENT: "Animated gradient",
        BackgroundType.PARTICLES: "Particles + gradient",
        BackgroundType.IMAGE: "Static image",
        BackgroundType.VIDEO_MP4: "Video (MP4)",
        BackgroundType.GIF: "GIF loop",
    }
    options = list(type_labels.keys())
    idx = options.index(bg_cfg.type) if bg_cfg.type in options else 1
    chosen = st.selectbox("Type", options, index=idx, format_func=lambda t: type_labels[t], key=f"{key_prefix}_bgtype")

    media_path = bg_cfg.media_path
    c1, c2 = st.columns(2)
    with c1:
        color_start = st.color_picker("Color start", bg_cfg.color_start, key=f"{key_prefix}_c1")
    with c2:
        color_end = st.color_picker("Color end", bg_cfg.color_end, key=f"{key_prefix}_c2")

    angle = bg_cfg.gradient_angle
    particle_count = bg_cfg.particle_count
    particle_color = bg_cfg.particle_color

    if chosen in (BackgroundType.GRADIENT, BackgroundType.PARTICLES):
        angle = st.slider("Gradient angle", 0, 360, bg_cfg.gradient_angle, key=f"{key_prefix}_angle")
    if chosen == BackgroundType.PARTICLES:
        particle_count = st.slider("Particle count", 10, 200, bg_cfg.particle_count, key=f"{key_prefix}_pcount")
        particle_color = st.color_picker("Particle color", bg_cfg.particle_color, key=f"{key_prefix}_pcolor")

    if chosen == BackgroundType.IMAGE:
        up = st.file_uploader("Upload image", type=["png", "jpg", "jpeg", "webp"], key=f"{key_prefix}_img")
        if up and validate_extension(up.name, ALLOWED_IMAGE_EXT):
            media_path = save_upload(up, settings.backgrounds_dir)
    elif chosen == BackgroundType.VIDEO_MP4:
        up = st.file_uploader("Upload MP4", type=["mp4", "mov", "webm"], key=f"{key_prefix}_vid")
        if up and validate_extension(up.name, ALLOWED_VIDEO_EXT):
            media_path = save_upload(up, settings.backgrounds_dir)
    elif chosen == BackgroundType.GIF:
        up = st.file_uploader("Upload GIF", type=["gif"], key=f"{key_prefix}_gif")
        if up and validate_extension(up.name, ALLOWED_GIF_EXT):
            media_path = save_upload(up, settings.backgrounds_dir)

    if media_path:
        st.caption(f"Using media: {Path(media_path).name}")

    c3, c4 = st.columns(2)
    with c3:
        blur = st.slider("Blur", 0, 20, bg_cfg.blur, key=f"{key_prefix}_blur")
    with c4:
        overlay = st.slider("Dark overlay", 0.0, 1.0, bg_cfg.overlay_opacity, key=f"{key_prefix}_overlay")

    return BackgroundConfig(
        type=chosen, color_start=color_start, color_end=color_end, gradient_angle=angle,
        media_path=media_path, particle_count=particle_count, particle_color=particle_color,
        blur=blur, overlay_opacity=overlay,
    )


def animation_picker(cfg: AnimationConfig, key_prefix: str, label: str) -> AnimationConfig:
    st.markdown(f"**{label}**")
    options = list(AnimationType)
    idx = options.index(cfg.type) if cfg.type in options else 0
    atype = st.selectbox("Effect", options, index=idx, format_func=lambda a: a.value.title(),
                          key=f"{key_prefix}_atype")
    c1, c2 = st.columns(2)
    with c1:
        duration = st.slider("Duration (s)", 0.1, 3.0, cfg.duration, 0.1, key=f"{key_prefix}_adur")
    with c2:
        intensity = st.slider("Intensity", 0.1, 2.0, cfg.intensity, 0.1, key=f"{key_prefix}_aint")
    direction = cfg.direction
    if atype == AnimationType.SLIDE:
        options_dir = list(SlideDirection)
        d_idx = options_dir.index(cfg.direction) if cfg.direction in options_dir else 0
        direction = st.selectbox("Direction", options_dir, index=d_idx,
                                  format_func=lambda d: d.value.title(), key=f"{key_prefix}_adir")
    return AnimationConfig(type=atype, duration=duration, direction=direction, intensity=intensity, delay=cfg.delay)


def question_editor(question: Question, index: int) -> Question:
    with st.container(border=True):
        st.markdown(f"#### Question {index + 1}")
        prompt = st.text_input("Prompt", question.prompt, key=f"q{index}_prompt")

        cols = st.columns(4)
        new_options = []
        for i in range(4):
            opt = question.options[i] if i < len(question.options) else Option(text="")
            with cols[i]:
                text = st.text_input(f"Option {chr(65 + i)}", opt.text, key=f"q{index}_opt{i}")
            new_options.append(Option(id=opt.id, text=text))

        labels = [f"{chr(65 + i)}: {o.text or '(empty)'}" for i, o in enumerate(new_options)]
        current_idx = 0
        for i, o in enumerate(new_options):
            if o.id == question.correct_option_id:
                current_idx = i
        correct_idx = st.radio("Correct answer", list(range(4)), index=current_idx,
                                format_func=lambda i: labels[i], horizontal=True, key=f"q{index}_correct")

        fun_fact = st.text_area("Fun fact (shown after the reveal)", question.fun_fact, key=f"q{index}_fact", height=70)

        c1, c2 = st.columns(2)
        with c1:
            timer_seconds = st.number_input("Timer (s)", 3, 30, question.timer_seconds, key=f"q{index}_timer")
        with c2:
            points = st.number_input("Points", 10, 1000, question.points, step=10, key=f"q{index}_points")

        image_path = question.image_path
        up = st.file_uploader("Question image (optional)", type=["png", "jpg", "jpeg", "webp"], key=f"q{index}_img")
        if up and validate_extension(up.name, ALLOWED_IMAGE_EXT):
            image_path = save_upload(up, settings.images_dir)
        if image_path:
            st.caption(f"Image: {Path(image_path).name}")

        return Question(
            id=question.id, prompt=prompt, options=new_options,
            correct_option_id=new_options[correct_idx].id, fun_fact=fun_fact,
            image_path=image_path, timer_seconds=int(timer_seconds), points=int(points),
        )


def audio_uploader_row(label: str, current_path: Optional[str], key: str, dest_dir: Path) -> Optional[str]:
    up = st.file_uploader(label, type=["mp3", "wav", "ogg", "m4a"], key=key)
    if up and validate_extension(up.name, ALLOWED_AUDIO_EXT):
        return save_upload(up, dest_dir)
    if current_path:
        st.caption(f"Current: {Path(current_path).name}")
    return current_path
