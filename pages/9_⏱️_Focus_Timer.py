"""
StudyMind AI — Page 9: Focus Timer & Active Session
Pomodoro technique with schedule block integration & Feynman recall notes
"""
import streamlit as st
import time
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage import save_persistent_state
from ui_components import render_sidebar_header
from config import COLORS

st.set_page_config(page_title="Focus Timer — StudyMind AI", page_icon="⏱️", layout="wide", initial_sidebar_state="expanded")
render_sidebar_header()

st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["primary"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["primary"]};
            padding:1.5rem 2rem; border-radius:12px; margin-bottom:1.5rem;'>
  <h1 style='margin:0; color:{COLORS["primary"]}'>⏱️ Focus Timer & Study Session</h1>
  <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}'>
    Execute your scheduled blocks with high-intensity focus. Pomodoro intervals + Feynman notes.
  </p>
</div>
""", unsafe_allow_html=True)

schedule = st.session_state.get("schedule", {})
today_str = str(date.today())

# Find today's blocks or fallback to all blocks
available_blocks = []
for day in schedule.get("daily_blocks", []):
    for blk in day.get("blocks", []):
        b = dict(blk)
        b["date"] = day.get("date", "")
        available_blocks.append(b)

col_setup, col_timer = st.columns([1, 1], gap="large")

with col_setup:
    st.subheader("🎯 Session Target")

    selected_block = None
    if available_blocks:
        block_labels = {
            f"{b.get('date','')} | {b.get('start_time','')} — {b.get('topic_title','')}": b
            for b in available_blocks[:15]
        }
        chosen_label = st.selectbox("Select Study Block", list(block_labels.keys()))
        selected_block = block_labels[chosen_label]

        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; padding:1.2rem; border-radius:10px;
            border-left:3px solid {COLORS["info"]}; margin:1rem 0;'>
  <strong style='color:{COLORS["info"]};'>🎯 Goal:</strong> {selected_block.get('session_goal','')}<br><br>
  <strong style='color:{COLORS["warning"]};'>💡 Tip:</strong> {selected_block.get('resources_tip','')}
</div>
""", unsafe_allow_html=True)
    else:
        custom_topic = st.text_input("Topic Name", value="Computer Networks — Active Revision")
        custom_goal  = st.text_input("Session Goal", value="Solve 5 subnetting problems")
        selected_block = {
            "topic_title": custom_topic,
            "session_goal": custom_goal,
            "duration_minutes": 50,
            "resources_tip": "Recall formulas before looking at notes."
        }

    c1, c2 = st.columns(2)
    with c1:
        study_duration = st.slider("Focus Interval (minutes)", 15, 90, 25, 5)
    with c2:
        break_duration = st.slider("Break Duration (minutes)", 3, 20, 5, 1)

    st.subheader("📝 Feynman Recall Scratchpad")
    scratchpad = st.text_area(
        "Explain what you just learned in plain English as if teaching a beginner:",
        height=160,
        placeholder="e.g. TCP slow start works like testing the water with your toe before jumping in..."
    )

with col_timer:
    st.subheader("⏳ Live Pomodoro Timer")

    # Timer state
    if "timer_running" not in st.session_state:
        st.session_state["timer_running"] = False
        st.session_state["timer_mode"] = "Focus"
        st.session_state["timer_seconds"] = study_duration * 60
        st.session_state["total_studied_seconds"] = 0

    total_sec = study_duration * 60 if st.session_state["timer_mode"] == "Focus" else break_duration * 60
    current_sec = st.session_state.get("timer_seconds", total_sec)

    mins = current_sec // 60
    secs = current_sec % 60

    timer_color = COLORS["primary"] if st.session_state["timer_mode"] == "Focus" else COLORS["success"]

    st.markdown(f"""
<div style='text-align:center; padding:3rem 2rem; background:{COLORS["card_bg"]};
            border-radius:20px; border:3px solid {timer_color}; margin-bottom:1.5rem;
            box-shadow:0 10px 30px rgba(0,0,0,0.4);'>
  <span style='font-size:1rem; text-transform:uppercase; letter-spacing:2px; color:{timer_color}; font-weight:700;'>
    {st.session_state["timer_mode"].upper()} INTERVAL
  </span>
  <h1 style='font-size:5rem; font-family:monospace; margin:0.5rem 0; color:white;'>
    {mins:02d}:{secs:02d}
  </h1>
  <p style='color:{COLORS["text_muted"]}; margin:0;'>
    {selected_block.get('topic_title','')}
  </p>
</div>
""", unsafe_allow_html=True)

    btn_c1, btn_c2, btn_c3 = st.columns(3)

    with btn_c1:
        if not st.session_state["timer_running"]:
            if st.button("▶️ Start Focus", type="primary", width="stretch"):
                st.session_state["timer_running"] = True
                st.session_state["timer_mode"] = "Focus"
                st.session_state["timer_seconds"] = study_duration * 60
                st.rerun()
        else:
            if st.button("⏸️ Pause", width="stretch"):
                st.session_state["timer_running"] = False
                st.rerun()

    with btn_c2:
        if st.button("☕ Take Break", width="stretch"):
            st.session_state["timer_mode"] = "Break"
            st.session_state["timer_seconds"] = break_duration * 60
            st.session_state["timer_running"] = True
            st.rerun()

    with btn_c3:
        if st.button("🔄 Reset Timer", width="stretch"):
            st.session_state["timer_running"] = False
            st.session_state["timer_seconds"] = study_duration * 60
            st.rerun()

    if st.session_state["timer_running"]:
        time.sleep(1)
        if st.session_state["timer_seconds"] > 0:
            st.session_state["timer_seconds"] -= 1
            if st.session_state["timer_mode"] == "Focus":
                st.session_state["total_studied_seconds"] += 1
            st.rerun()
        else:
            st.session_state["timer_running"] = False
            if st.session_state["timer_mode"] == "Focus":
                st.balloons()
                st.success("🎉 Great focus session! Time for a short break.")
                st.session_state["timer_mode"] = "Break"
                st.session_state["timer_seconds"] = break_duration * 60
            else:
                st.info("☕ Break complete! Ready for the next focus sprint?")
                st.session_state["timer_mode"] = "Focus"
                st.session_state["timer_seconds"] = study_duration * 60
            st.rerun()

    # Logged study time
    total_mins = st.session_state.get("total_studied_seconds", 0) // 60
    if total_mins > 0:
        st.caption(f"🔥 Today's Logged Focus Time: **{total_mins} minutes**")

