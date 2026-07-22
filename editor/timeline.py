"""
Scene timeline: Intro -> (Question -> Timer -> Answer Reveal -> Fun Fact) x N -> Outro

This module renders that sequence as an HTML/CSS strip inside Streamlit and
exposes helpers for computing per-scene start times, used both by the UI
and indirectly mirrored by engines.render_engine.build_schedule (kept
independent so the render engine has zero Streamlit dependency).
"""
from __future__ import annotations

from typing import List

import streamlit as st

from core.models import Project, SceneType
from utils.helpers import human_duration

SCENE_COLORS = {
    SceneType.INTRO: "#8C6BFA",
    SceneType.QUESTION: "#3EC1D3",
    SceneType.TIMER: "#FFB65C",
    SceneType.ANSWER_REVEAL: "#3DDC84",
    SceneType.FUN_FACT: "#FF5C7C",
    SceneType.OUTRO: "#8C6BFA",
}

SCENE_ICONS = {
    SceneType.INTRO: "\U0001F3AC",       # clapper
    SceneType.QUESTION: "\u2753",         # question mark
    SceneType.TIMER: "\u23F1\ufe0f",      # stopwatch
    SceneType.ANSWER_REVEAL: "\u2705",    # check
    SceneType.FUN_FACT: "\U0001F4A1",     # bulb
    SceneType.OUTRO: "\U0001F44B",        # wave
}


def render_timeline(project: Project):
    """Renders a horizontal, proportionally-scaled timeline strip."""
    schedule = []
    t = 0.0
    timing = project.timing

    schedule.append((SceneType.INTRO, t, timing.intro, None))
    t += timing.intro
    for qi, q in enumerate(project.quiz.questions):
        for stype, dur in [
            (SceneType.QUESTION, timing.question),
            (SceneType.TIMER, timing.timer),
            (SceneType.ANSWER_REVEAL, timing.answer_reveal),
            (SceneType.FUN_FACT, timing.fun_fact),
        ]:
            schedule.append((stype, t, dur, qi))
            t += dur
    schedule.append((SceneType.OUTRO, t, timing.outro, None))
    t += timing.outro

    total = max(t, 0.01)

    blocks_html = ""
    for stype, start, dur, qi in schedule:
        pct = max(dur / total * 100, 2.5)
        color = SCENE_COLORS[stype]
        icon = SCENE_ICONS[stype]
        label = stype.value.replace("_", " ").title()
        q_tag = f" Q{qi + 1}" if qi is not None else ""
        blocks_html += (
            f'<div title="{label}{q_tag}: {dur:.1f}s" '
            f'style="flex: 0 0 {pct:.2f}%; background:{color}; '
            f'padding:8px 4px; text-align:center; color:white; font-size:11px; '
            f'font-weight:600; border-right:2px solid rgba(255,255,255,0.4); '
            f'overflow:hidden; white-space:nowrap; text-overflow:ellipsis;">'
            f'{icon} {label}{q_tag}</div>'
        )

    html = (
        '<div style="display:flex; width:100%; border-radius:10px; overflow:hidden; '
        'box-shadow: 0 2px 8px rgba(0,0,0,0.15);">'
        f"{blocks_html}"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    st.caption(f"Total runtime: {human_duration(total)}  ·  {len(schedule)} scenes")
    return total


def scene_count_summary(project: Project) -> str:
    n = len(project.quiz.questions)
    scenes = 2 + n * 4
    return f"{scenes} scenes ({n} question{'s' if n != 1 else ''} \u00d7 4 + intro/outro)"
