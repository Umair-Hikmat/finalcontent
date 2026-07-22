"""
AI Quiz Studio - a Canva + Typito style quiz video maker built with Streamlit.

Run locally:    streamlit run app.py
Run in Docker:  see Dockerfile (Cloud Run compatible, PORT env var honored)
"""
from __future__ import annotations

import time
from pathlib import Path

import streamlit as st
from PIL import Image

from config import settings
from core.models import AudioConfig, Project, RenderSettings, SceneType, VideoFormat
from core.project_manager import project_manager
from editor.timeline import render_timeline, scene_count_summary
from editor.ui_components import (
    animation_picker, audio_uploader_row, background_editor, font_picker, question_editor,
)
from engines.render_engine import ScheduledScene, SceneRenderer, build_schedule, render_project
from templates.template_loader import apply_template, list_templates, save_as_template
from utils.helpers import human_duration, safe_filename
from utils.validators import validate_quiz

st.set_page_config(page_title="AI Quiz Studio", page_icon="🎬", layout="wide")


# --------------------------------------------------------------------------- #
# Session state bootstrap
# --------------------------------------------------------------------------- #

if "project" not in st.session_state:
    st.session_state.project = Project()
    apply_template(st.session_state.project, "neon_pulse")

if "page" not in st.session_state:
    st.session_state.page = "Projects"

project: Project = st.session_state.project


def sync_and_rerun():
    st.session_state.project = project
    st.rerun()


# --------------------------------------------------------------------------- #
# Sidebar navigation
# --------------------------------------------------------------------------- #

with st.sidebar:
    st.markdown("## 🎬 AI Quiz Studio")
    st.caption("Canva + Typito style quiz video maker")
    st.divider()

    page = st.radio(
        "Navigate",
        ["Projects", "Quiz Editor", "Templates", "Style Studio", "Timeline & Preview", "Render & Export"],
        index=["Projects", "Quiz Editor", "Templates", "Style Studio", "Timeline & Preview", "Render & Export"].index(st.session_state.page),
        label_visibility="collapsed",
    )
    st.session_state.page = page

    st.divider()
    st.markdown(f"**Current project:** {project.name}")
    st.caption(f"{len(project.quiz.questions)} question(s) · {scene_count_summary(project)}")
    if st.button("💾 Save project", use_container_width=True):
        path = project_manager.save(project)
        st.success(f"Saved to {path.name}")


# --------------------------------------------------------------------------- #
# Page: Projects
# --------------------------------------------------------------------------- #

def page_projects():
    st.title("📁 Projects")
    st.write("Create a new quiz video project or continue an existing one.")

    col1, col2 = st.columns([2, 1])
    with col1:
        new_name = st.text_input("New project name", "My Awesome Quiz")
    with col2:
        st.write("")
        st.write("")
        if st.button("➕ Create project", use_container_width=True, type="primary"):
            st.session_state.project = Project(name=new_name)
            apply_template(st.session_state.project, "neon_pulse")
            st.session_state.page = "Quiz Editor"
            st.rerun()

    st.divider()
    st.subheader("Existing projects")
    projects = project_manager.list_projects()
    if not projects:
        st.info("No saved projects yet. Create one above, or edit the current unsaved project.")
        return

    for p in projects:
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 1])
            c1.markdown(f"**{p['name']}**")
            c2.caption(f"{p['num_questions']} questions")
            c3.caption(f"Template: {p['template_id']}")
            if c4.button("Open", key=f"open_{p['id']}"):
                st.session_state.project = project_manager.load(p["path"])
                st.session_state.page = "Quiz Editor"
                st.rerun()
            if c5.button("🗑️", key=f"del_{p['id']}"):
                project_manager.delete(p["path"])
                st.rerun()


# --------------------------------------------------------------------------- #
# Page: Quiz Editor
# --------------------------------------------------------------------------- #

def page_quiz_editor():
    st.title("📝 Quiz Editor")

    c1, c2 = st.columns(2)
    with c1:
        project.quiz.title = st.text_input("Quiz title", project.quiz.title)
        project.quiz.author = st.text_input("Author / channel name", project.quiz.author)
    with c2:
        project.quiz.subtitle = st.text_input("Subtitle / hook", project.quiz.subtitle)
        project.name = st.text_input("Project name (for saving)", project.name)

    st.divider()
    st.subheader(f"Questions ({len(project.quiz.questions)})")

    for i, q in enumerate(list(project.quiz.questions)):
        updated = question_editor(q, i)
        project.quiz.questions[i] = updated
        cdel, _ = st.columns([1, 5])
        if cdel.button("Remove question", key=f"remove_q{i}"):
            project.quiz.questions.pop(i)
            st.rerun()
        st.write("")

    if st.button("➕ Add question", type="primary"):
        project.quiz.add_blank_question()
        st.rerun()

    st.divider()
    errors = validate_quiz(project.quiz)
    if errors:
        st.warning("Fix these before rendering:\n\n" + "\n".join(f"- {e}" for e in errors))
    else:
        st.success("Quiz looks good and is ready to render!")


# --------------------------------------------------------------------------- #
# Page: Templates
# --------------------------------------------------------------------------- #

def page_templates():
    st.title("🎨 Video Templates")
    st.write("Pick a complete visual style: background, fonts, animation set, and pacing all update together.")

    templates = list_templates()
    cols = st.columns(3)
    for i, tpl in enumerate(templates):
        with cols[i % 3]:
            with st.container(border=True):
                grad_css = f"linear-gradient(135deg, {tpl['preview_colors'][0]}, {tpl['preview_colors'][1]})"
                st.markdown(
                    f'<div style="height:110px;border-radius:10px;background:{grad_css};'
                    f'display:flex;align-items:center;justify-content:center;color:white;'
                    f'font-weight:700;font-size:18px;">{tpl["name"]}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(tpl["description"])
                is_current = project.template_id == tpl["id"]
                if st.button("✅ Applied" if is_current else "Use this template",
                             key=f"tpl_{tpl['id']}", disabled=is_current, use_container_width=True):
                    apply_template(project, tpl["id"])
                    st.rerun()

    st.divider()
    st.subheader("Save current styling as a new template")
    c1, c2 = st.columns(2)
    with c1:
        new_id = st.text_input("Template id (slug)", "my_custom_style")
    with c2:
        new_name = st.text_input("Template display name", "My Custom Style")
    if st.button("💾 Save as template"):
        save_as_template(project, safe_filename(new_id), new_name)
        st.success(f"Saved template '{new_name}'")
        st.rerun()


# --------------------------------------------------------------------------- #
# Page: Style Studio
# --------------------------------------------------------------------------- #

def page_style_studio():
    st.title("✨ Style Studio")

    tabs = st.tabs(["Background", "Font", "Animations", "Audio"])

    with tabs[0]:
        project.background = background_editor(project.background, "bg")

    with tabs[1]:
        project.font = font_picker(project.font, "font")

    with tabs[2]:
        st.write("Configure the animation used for each scene type in the timeline.")
        for scene in SceneType:
            with st.expander(scene.value.replace("_", " ").title(), expanded=False):
                current = project.animation_for(scene)
                updated = animation_picker(current, f"anim_{scene.value}", "Effect settings")
                project.animations[scene.value] = updated.model_dump()

    with tabs[3]:
        st.write("Background music plays throughout; sound effects fire at specific scene moments.")
        project.audio.music_path = audio_uploader_row("Background music", project.audio.music_path, "music", settings.music_dir)
        project.audio.music_volume = st.slider("Music volume", 0.0, 1.0, project.audio.music_volume)
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            project.audio.sfx_tick_path = audio_uploader_row("Timer tick SFX", project.audio.sfx_tick_path, "sfx_tick", settings.sfx_dir)
            project.audio.sfx_correct_path = audio_uploader_row("Correct/reveal SFX", project.audio.sfx_correct_path, "sfx_correct", settings.sfx_dir)
        with c2:
            project.audio.sfx_reveal_path = audio_uploader_row("Fun fact chime SFX", project.audio.sfx_reveal_path, "sfx_reveal", settings.sfx_dir)
            project.audio.sfx_volume = st.slider("SFX volume", 0.0, 1.0, project.audio.sfx_volume)


# --------------------------------------------------------------------------- #
# Page: Timeline & Preview
# --------------------------------------------------------------------------- #

def page_timeline_preview():
    st.title("🎬 Timeline & Preview")
    st.write("Intro → Question → Timer → Answer Reveal → Fun Fact → Outro (repeated per question)")

    render_timeline(project)

    errors = validate_quiz(project.quiz)
    if errors:
        st.warning("Add at least one complete question to preview frames.")
        return

    st.divider()
    st.subheader("Frame preview")

    schedule = build_schedule(project)
    scene_labels = [
        f"{i+1}. {s.scene_type.value.replace('_',' ').title()}" + (f" (Q{s.question_index+1})" if s.question_index is not None else "")
        for i, s in enumerate(schedule)
    ]
    idx = st.selectbox("Scene", list(range(len(schedule))), format_func=lambda i: scene_labels[i])
    scene = schedule[idx]
    local_t = st.slider("Time within scene (s)", 0.0, max(scene.duration - 0.05, 0.05), 0.0, 0.05)

    if st.button("🖼️ Render this frame"):
        with st.spinner("Rendering frame\u2026"):
            renderer = SceneRenderer(project)
            img = renderer.render_frame(scene, local_t)
            renderer.close()
            st.image(img, caption=scene_labels[idx], width=360)


# --------------------------------------------------------------------------- #
# Page: Render & Export
# --------------------------------------------------------------------------- #

def page_render_export():
    st.title("🚀 Render & Export")

    errors = validate_quiz(project.quiz)
    if errors:
        st.error("Fix these issues before rendering:\n\n" + "\n".join(f"- {e}" for e in errors))
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        fmt_labels = {VideoFormat.SHORTS: "Shorts / Reels / TikTok (1080x1920)",
                      VideoFormat.YOUTUBE: "YouTube (1920x1080)",
                      VideoFormat.SQUARE: "Square (1080x1080)"}
        fmt = st.selectbox("Format", list(fmt_labels.keys()),
                            index=list(fmt_labels.keys()).index(project.render.format),
                            format_func=lambda f: fmt_labels[f])
    with c2:
        quality = st.selectbox("Quality", ["draft", "standard", "high"],
                                index=["draft", "standard", "high"].index(project.render.quality))
    with c3:
        fps = st.selectbox("FPS", [24, 30, 60], index=[24, 30, 60].index(project.render.fps) if project.render.fps in (24, 30, 60) else 1)

    project.render = RenderSettings(format=fmt, fps=fps, quality=quality,
                                     codec=project.render.codec, audio_codec=project.render.audio_codec)

    total = project.total_duration()
    st.info(f"Estimated runtime: **{human_duration(total)}** · Resolution: **{project.render.resolution()[0]}x{project.render.resolution()[1]}** · {quality.title()} quality")

    st.divider()

    if st.button("🎥 Render final video", type="primary", use_container_width=True):
        progress_bar = st.progress(0.0)
        status = st.empty()

        def cb(pct: float, msg: str):
            progress_bar.progress(min(max(pct, 0.0), 1.0))
            status.write(msg)

        out_name = f"{safe_filename(project.name)}_{int(time.time())}.mp4"
        out_path = settings.exports_dir / out_name

        with st.spinner("Rendering your quiz video\u2026 this can take a few minutes."):
            try:
                render_project(project, out_path, progress_cb=cb)
                st.success("Render complete!")
                st.video(str(out_path))
                with open(out_path, "rb") as f:
                    st.download_button("⬇️ Download MP4", f, file_name=out_name, mime="video/mp4", use_container_width=True)
            except Exception as e:
                st.error(f"Render failed: {e}")

    st.divider()
    st.subheader("Previous exports")
    exports = sorted(settings.exports_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not exports:
        st.caption("No exports yet.")
    for exp in exports[:10]:
        c1, c2 = st.columns([4, 1])
        c1.write(exp.name)
        with open(exp, "rb") as f:
            c2.download_button("⬇️", f, file_name=exp.name, mime="video/mp4", key=f"dl_{exp.name}")


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #

PAGES = {
    "Projects": page_projects,
    "Quiz Editor": page_quiz_editor,
    "Templates": page_templates,
    "Style Studio": page_style_studio,
    "Timeline & Preview": page_timeline_preview,
    "Render & Export": page_render_export,
}

PAGES[st.session_state.page]()

st.session_state.project = project
