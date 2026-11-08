"""
StudyMind AI — Page 4: Weak Spot Analyzer & Spaced Revision Rescheduler
Powered by MCP (Model Context Protocol) + Spaced Repetition + Google Calendar Sync
"""
import streamlit as st
import json
from datetime import date
import plotly.graph_objects as go
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from gemini_client import call_gemini_json
from prompts import weak_spot_analyzer_prompt, smart_rescheduler_prompt
from mcp_tools import reschedule_spaced_revisions, apply_schedule_changes
from core.weak_topic_manager import extract_topic_performance, identify_weak_topics
from ui_components import render_sidebar_header, render_gcal_sidebar_status
from storage import save_persistent_state
from config import COLORS, URGENCY_COLORS
import google_calendar as gcal

st.set_page_config(page_title="Weak Spot Analyzer — StudyMind AI", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
render_sidebar_header()
render_gcal_sidebar_status()

st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["warning"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["warning"]};
            padding:1.5rem 2rem; border-radius:12px; margin-bottom:1.5rem;'>
  <h1 style='margin:0; color:{COLORS["warning"]}'>📊 Weak Spot Analyzer &amp; Spaced Rescheduler</h1>
  <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}'>
    MCP-powered gap detection, repeated mistake tracking, and automated spaced revision rescheduling.
  </p>
</div>
""", unsafe_allow_html=True)

quiz_results = st.session_state.get("quiz_results", [])
mock_evaluation = st.session_state.get("mock_evaluation", {})
student = st.session_state.get("student_profile", {})
student_name = student.get("student_name", "Student")

# ── Prerequisite check ────────────────────────────────────────────────────────
has_data = bool(quiz_results or (mock_evaluation and mock_evaluation.get("topic_performance")))

if not has_data:
    st.info("📝 No quiz or mock exam evaluations recorded yet. Take at least one quiz or mock test first.")
    col_q, col_m = st.columns(2)
    with col_q:
        if st.button("🎯 Go to AI Quiz", width="stretch"):
            st.switch_page("pages/3_🎯_Quiz.py")
    with col_m:
        if st.button("📝 Go to Mock Exam", width="stretch"):
            st.switch_page("pages/6_📝_Mock_Exam.py")
    st.stop()

# ── 1. Topic Performance & Repeated Mistake Tracking ─────────────────────────
topic_metrics = extract_topic_performance(quiz_results, mock_evaluation)

st.subheader(f"📈 Performance & Repeated Mistake Tracker ({len(topic_metrics)} topics)")

cols = st.columns(min(max(len(topic_metrics), 1), 4))
for i, (tid, tm) in enumerate(topic_metrics.items()):
    with cols[i % 4]:
        score = tm.get("recent_accuracy", 0)
        urgency = tm.get("urgency", "weak")
        mistakes = tm.get("repeated_mistakes_count", 0)
        attempts = tm.get("attempts", 1)

        color = COLORS["success"] if score >= 70 else COLORS["warning"] if score >= 50 else COLORS["danger"]
        status_label = {
            "critical": "🚨 Critical",
            "weak": "⚠️ Needs Review",
            "improving": "📈 Improving",
            "mastered": "✅ Mastered",
        }.get(urgency, "Tested")

        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-radius:10px; padding:1.1rem;
            border-top:3px solid {color}; margin-bottom:0.8rem;'>
  <small style='color:{COLORS["text_muted"]};'>{tm.get("topic_title","")[:26]}</small>
  <h2 style='margin:0.2rem 0; color:{color};'>{score}%</h2>
  <div style='display:flex; justify-content:space-between; font-size:0.8rem;'>
    <span>Attempts: <b>{attempts}</b></span>
    <span style='color:{COLORS["danger"] if mistakes > 0 else COLORS["success"]};'>Repeated Errors: <b>{mistakes}</b></span>
  </div>
  <div style='margin-top:0.4rem; font-size:0.75rem; color:#aaa;'>Status: <b>{status_label}</b></div>
</div>
""", unsafe_allow_html=True)

# ── 2. MCP Deep Gap Analysis ──────────────────────────────────────────────────
st.divider()

if st.button("🧠 Run MCP Deep Diagnostic", type="primary", width="stretch"):
    with st.spinner("🔍 Running MCP diagnostic on quiz and mock exam patterns..."):
        try:
            prompt = weak_spot_analyzer_prompt(quiz_results, student_name)
            analysis = call_gemini_json(prompt, temperature=0.3)
            st.session_state["weak_analysis"] = analysis
            save_persistent_state(st.session_state)
            st.toast("✅ MCP Diagnostic completed!", icon="🧠")
        except Exception as e:
            st.error(f"❌ Analysis failed: {e}")

if "weak_analysis" in st.session_state:
    analysis = st.session_state["weak_analysis"]
    mastery = analysis.get("overall_mastery_pct", 0)

    # Gauge
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=mastery,
        title={"text": "Overall Mastery", "font": {"size": 18}},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": COLORS["primary"]},
            "steps": [
                {"range": [0,  50], "color": COLORS["danger"] + "44"},
                {"range": [50, 70], "color": COLORS["warning"] + "44"},
                {"range": [70, 100],"color": COLORS["success"] + "44"},
            ],
            "threshold": {"line": {"color": "white", "width": 2}, "value": 70},
        },
        number={"suffix": "%"},
    ))
    fig.update_layout(height=240, margin=dict(t=35, b=0, l=0, r=0),
                      paper_bgcolor="rgba(0,0,0,0)", font_color="white")
    st.plotly_chart(fig, width="stretch")

    coach_msg = analysis.get("coach_message", "")
    if coach_msg:
        st.info(f"🧠 **StudyMind AI Coach:** {coach_msg}")

    # Weak spots detailed list
    weak_spots = analysis.get("weak_spots", [])
    if weak_spots:
        st.subheader("🚨 Identified Weak Spots & Diagnostic Recovery")
        for ws in weak_spots:
            urgency = ws.get("urgency", "medium")
            u_color = URGENCY_COLORS.get(urgency, COLORS["info"])
            t_title = ws.get("topic_title", "")
            t_metric = topic_metrics.get(ws.get("topic_id", ""), {})
            rep_mistakes = t_metric.get("repeated_mistakes_count", 0)

            with st.expander(
                f"**{t_title}** · Score: {ws.get('current_score_pct',0)}% · "
                f"Urgency: {urgency.upper()} "
                f"{f'· ⚠️ {rep_mistakes} Repeated Error(s)' if rep_mistakes > 0 else ''}",
                expanded=(urgency == "critical")
            ):
                st.markdown(f"**Subtopic / Concept:** {ws.get('subtopic_tag', 'Core fundamentals')}")
                st.markdown(f"**Root Cause:** {ws.get('root_cause', '')}")
                st.markdown(f"**Recovery Hours Recommended:** {ws.get('recommended_study_hours', 1.0)}h · **Schedule within:** {ws.get('schedule_within_days', 4)} days")
                st.markdown("**Surgical Action Steps:**")
                for step in ws.get("recovery_plan", []):
                    st.markdown(f"- {step}")

# ── 3. Spaced Revision Rescheduler ─────────────────────────────────────────────
weak_topics_list = identify_weak_topics(quiz_results, mock_evaluation, threshold=70.0)

if weak_topics_list and "schedule" in st.session_state:
    st.divider()
    st.subheader("🔄 Automated Spaced Revision Rescheduler")
    _muted = COLORS['text_muted']
    st.markdown(
        f"<p style='color:{_muted};'>"
        f"StudyMind AI detected <b>{len(weak_topics_list)} topic(s)</b> requiring revision. "
        f"Using evidence-based spaced repetition, revisions are scheduled at optimal intervals "
        f"(<b>Round 1: 1-2 days</b> for immediate consolidation, <b>Round 2: 4-6 days</b> for long-term retention). "
        f"Already completed sessions remain untouched."
        f"</p>",
        unsafe_allow_html=True,
    )

    if st.button("⚡ Generate Spaced Revision Schedule", type="primary", width="stretch", key="btn_gen_spaced"):
        with st.spinner("Calculating optimal spaced revision slots with non-disturbance verification..."):
            try:
                curr_sched = st.session_state["schedule"]
                proposal = reschedule_spaced_revisions(curr_sched, weak_topics_list, student)
                st.session_state["spaced_reschedule_proposal"] = proposal
            except Exception as e:
                st.error(f"❌ Rescheduling error: {e}")

if "spaced_reschedule_proposal" in st.session_state:
    prop = st.session_state["spaced_reschedule_proposal"]
    changes = prop.get("changes", [])
    msg = prop.get("hitl_message", "")

    st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border:1px solid {COLORS["warning"]};
            border-radius:12px; padding:1.4rem; margin:1rem 0;'>
  <h4 style='color:{COLORS["warning"]}; margin:0 0 0.5rem 0;'>📋 Spaced Revision Plan ({len(changes)} Sessions)</h4>
  <p style='margin:0 0 0.8rem 0; font-size:0.95rem;'>{msg}</p>
</div>
""", unsafe_allow_html=True)

    # Show table of changes
    for ch in changes:
        st.markdown(
            f"📅 **{ch.get('new_date')}** ({ch.get('new_time', '10:00')}, {ch.get('duration_minutes', 60)}m) · "
            f"**Round {ch.get('round', 1)} Spaced Revision:** {ch.get('topic_title')} — "
            f"<em>{ch.get('reason')}</em>"
        )

    st.markdown("<br>", unsafe_allow_html=True)
    c_app, c_rej = st.columns(2)
    with c_app:
        if st.button("✅ Approve & Update Schedule", type="primary", width="stretch", key="btn_app_rev"):
            updated_schedule = prop.get("updated_schedule", st.session_state["schedule"])
            st.session_state["schedule"] = updated_schedule
            save_persistent_state(st.session_state)

            # Auto-sync with Google Calendar if connected
            sync_note = ""
            if gcal.is_connected(student_name):
                try:
                    res = gcal.sync_schedule_to_calendar(updated_schedule, student_name, student_name)
                    st.session_state["gcal_event_map"] = res
                    save_persistent_state(st.session_state)
                    sync_note = f" and auto-synced {res['created'] + res['updated']} sessions with 10-minute reminders to Google Calendar!"
                except Exception as sync_err:
                    sync_note = f" (Google Calendar sync note: {sync_err})"

            st.success(f"✅ Schedule updated with {len(changes)} spaced revision sessions{sync_note}")
            del st.session_state["spaced_reschedule_proposal"]
            st.balloons()
            st.rerun()

    with c_rej:
        if st.button("❌ Dismiss Proposal", width="stretch", key="btn_rej_rev"):
            del st.session_state["spaced_reschedule_proposal"]
            st.info("Proposed revision changes dismissed.")
            st.rerun()

# ── 4. Revision Completion & Performance Improvement Tracker ──────────────────
st.divider()
st.subheader("🎯 Revision Completion & Mastery Tracker")

completed_revisions = st.session_state.get("completed_revisions", [])
schedule_data = st.session_state.get("schedule", {})
daily_blocks = schedule_data.get("daily_blocks", [])

# Collect all revision blocks scheduled
revision_blocks = []
for day in daily_blocks:
    d_str = day.get("date", "")
    for b in day.get("blocks", []):
        if b.get("is_revision") or "Revision" in b.get("topic_title", ""):
            b_id = f"{d_str}_{b.get('start_time')}_{b.get('topic_id')}"
            revision_blocks.append((d_str, b, b_id))

if revision_blocks:
    st.caption("Track your scheduled revision sessions. Check off sessions as you finish them:")
    for d_str, b, b_id in revision_blocks:
        is_done = b_id in completed_revisions
        checked = st.checkbox(
            f"**{d_str}** · {b.get('start_time','')} ({b.get('duration_minutes',60)}m) — {b.get('topic_title','')} · {b.get('session_goal','')}",
            value=is_done,
            key=f"rev_check_{b_id}"
        )
        if checked != is_done:
            if checked and b_id not in completed_revisions:
                completed_revisions.append(b_id)
            elif not checked and b_id in completed_revisions:
                completed_revisions.remove(b_id)
            st.session_state["completed_revisions"] = completed_revisions
            save_persistent_state(st.session_state)
            st.rerun()
else:
    st.info("💡 No revision sessions currently scheduled. Generate a study schedule or run the Spaced Revision Rescheduler above to insert active recall sessions.")

# Performance Improvement Deltas
improved_topics = [tm for tm in topic_metrics.values() if tm.get("attempts", 0) > 1 and tm.get("improvement_pct", 0) > 0]
if improved_topics:
    st.markdown("#### 🚀 Topic Mastery Trajectory")
    for it in improved_topics:
        initial = it["scores"][0]
        recent = it["recent_accuracy"]
        delta = it["improvement_pct"]
        st.success(
            f"**{it.get('topic_title')}**: Initial Score: **{initial}%** ➔ Latest Score: **{recent}%** "
            f"(**+{delta}%** improvement across {it.get('attempts')} attempts!)"
        )
