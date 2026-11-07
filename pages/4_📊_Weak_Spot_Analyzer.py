"""
StudyMind AI — Page 4: Weak Spot Analyzer
"""
import streamlit as st
import json
import plotly.graph_objects as go
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from gemini_client import call_gemini_json
from prompts import weak_spot_analyzer_prompt, smart_rescheduler_prompt
from mcp_tools import apply_schedule_changes
from config import COLORS, URGENCY_COLORS

st.set_page_config(page_title="Weak Spot Analyzer — StudyMind AI", page_icon="📊", layout="wide")

st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["warning"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["warning"]};
            padding:1.5rem 2rem; border-radius:12px; margin-bottom:1.5rem;'>
  <h1 style='margin:0; color:{COLORS["warning"]}'>📊 Weak Spot Analyzer</h1>
  <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}'>
    Know exactly where you're struggling — and get a precise recovery plan.
  </p>
</div>
""", unsafe_allow_html=True)

quiz_results = st.session_state.get("quiz_results", [])
student = st.session_state.get("student_profile", {})
student_name = student.get("student_name", "Student")

if not quiz_results:
    st.info("📝 No quiz results yet. Take at least one quiz first.")
    if st.button("Go to Quiz"):
        st.switch_page("pages/3_🎯_Quiz.py")
    st.stop()

# ── Summary cards ──────────────────────────────────────────────────────────────
st.subheader(f"📈 Quiz History — {len(quiz_results)} topic(s) tested")

cols = st.columns(min(len(quiz_results), 4))
for i, r in enumerate(quiz_results):
    with cols[i % 4]:
        score = r.get("score_pct", 0)
        color = COLORS["success"] if score >= 70 else COLORS["warning"] if score >= 50 else COLORS["danger"]
        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-radius:10px; padding:1rem;
            border-top:3px solid {color}; text-align:center;'>
  <p style='margin:0; font-size:0.85rem; color:{COLORS["text_muted"]};'>{r.get('topic_title','')[:25]}</p>
  <h2 style='margin:0.3rem 0; color:{color};'>{score}%</h2>
  <p style='margin:0; font-size:0.8rem;'>{r.get('correct',0)}/{r.get('total',0)} correct</p>
</div>
""", unsafe_allow_html=True)

# ── Analyze button ─────────────────────────────────────────────────────────────
if st.button("🧠 Analyze My Weak Spots", type="primary", use_container_width=True):
    with st.spinner("🔍 Analyzing your performance patterns..."):
        try:
            prompt = weak_spot_analyzer_prompt(quiz_results, student_name)
            analysis = call_gemini_json(prompt, temperature=0.3)
            st.session_state["weak_analysis"] = analysis
        except ValueError as e:
            st.error(f"❌ Analysis failed: {e}")

# ── Display Analysis ───────────────────────────────────────────────────────────
if "weak_analysis" in st.session_state:
    analysis = st.session_state["weak_analysis"]

    st.divider()

    # Overall mastery gauge
    mastery = analysis.get("overall_mastery_pct", 0)
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
    fig.update_layout(height=250, margin=dict(t=40, b=0, l=0, r=0),
                      paper_bgcolor="rgba(0,0,0,0)", font_color="white")
    st.plotly_chart(fig, use_container_width=True)

    # Coach message
    coach_msg = analysis.get("coach_message", "")
    if coach_msg:
        st.info(f"🧠 **StudyMind says:** {coach_msg}")

    # Weak spots
    weak_spots = analysis.get("weak_spots", [])
    if weak_spots:
        st.subheader("🚨 Weak Spots")
        for ws in weak_spots:
            urgency = ws.get("urgency", "medium")
            u_color = URGENCY_COLORS.get(urgency, COLORS["info"])
            with st.expander(
                f"**{ws.get('topic_title','')}** · {ws.get('current_score_pct',0)}% "
                f"· {urgency.upper()}",
                expanded=(urgency == "critical")
            ):
                st.markdown(f"**Subtopic:** {ws.get('subtopic_tag','')}")
                st.markdown(f"**Root Cause:** {ws.get('root_cause','')}")
                st.markdown(f"**Recommended Hours:** {ws.get('recommended_study_hours',0)}h "
                            f"· **Schedule within:** {ws.get('schedule_within_days',7)} days")
                st.markdown("**Recovery Plan:**")
                for step in ws.get("recovery_plan", []):
                    st.markdown(f"  - {step}")

    # Blind spots
    blind_spots = analysis.get("blind_spots", [])
    if blind_spots:
        st.subheader("👁️ Blind Spots (You think you know, but you don't)")
        for bs in blind_spots:
            st.warning(
                f"**Topic {bs.get('topic_id','')}** — "
                f"Confidence: {bs.get('confidence_rating',0)}/5 · "
                f"Actual Score: {bs.get('actual_score_pct',0)}%\n\n"
                f"⚠️ {bs.get('warning','')}"
            )

    # Improving topics
    improving = analysis.get("improving_topics", [])
    if improving:
        st.subheader("📈 Improving Topics — Keep Going!")
        for t in improving:
            st.success(
                f"**{t.get('topic_title','')}** +{t.get('improvement_pct',0)}% improvement — "
                f"{t.get('encouragement','')}"
            )

    # Auto-reschedule trigger
    if weak_spots and "schedule" in st.session_state:
        st.divider()
        st.subheader("🔄 Smart Rescheduler")
        st.info("Topics below 70% detected. Want me to surgically adjust your schedule?")
        if st.button("⚡ Auto-Reschedule Weak Topics", type="primary"):
            with st.spinner("Rescheduling..."):
                try:
                    schedule = st.session_state["schedule"]
                    prompt = smart_rescheduler_prompt(schedule, weak_spots, student_name)
                    reschedule = call_gemini_json(prompt, temperature=0.3)
                    st.session_state["reschedule_proposal"] = reschedule
                except ValueError as e:
                    st.error(f"❌ Reschedule failed: {e}")

    if "reschedule_proposal" in st.session_state:
        rp = st.session_state["reschedule_proposal"]
        summary = rp.get("reschedule_summary", {})
        hitl    = rp.get("hitl_message", "")

        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border:1px solid {COLORS["warning"]};
            border-radius:12px; padding:1.5rem; margin:1rem 0;'>
  <h4>📋 Proposed Changes</h4>
  <p>{hitl}</p>
  <small>Blocks added: {summary.get('blocks_added',0)} · 
         Moved: {summary.get('blocks_moved',0)} · 
         Removed: {summary.get('blocks_removed',0)} · 
         Risk: {summary.get('risk_assessment','low').upper()}</small>
</div>
""", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Approve Changes", type="primary", use_container_width=True):
                if "schedule" in st.session_state and "changes" in rp:
                    st.session_state["schedule"] = apply_schedule_changes(
                        st.session_state["schedule"], rp["changes"]
                    )
                st.success("✅ Schedule surgically updated! New revision blocks inserted.")
                del st.session_state["reschedule_proposal"]
                st.rerun()
        with c2:
            if st.button("❌ Reject Changes", use_container_width=True):
                st.info("No changes made.")
                del st.session_state["reschedule_proposal"]
