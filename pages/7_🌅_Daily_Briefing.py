"""
StudyMind AI — Page 7: Daily Briefing
"""
import streamlit as st
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from gemini_client import call_gemini_text
from prompts import daily_briefing_prompt
from config import COLORS

st.set_page_config(page_title="Daily Briefing — StudyMind AI", page_icon="🌅", layout="wide")

st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["warning"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["warning"]};
            padding:1.5rem 2rem; border-radius:12px; margin-bottom:1.5rem;'>
  <h1 style='margin:0; color:{COLORS["warning"]}'>🌅 Daily Briefing</h1>
  <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}'>
    Your personalized morning briefing — honest, focused, energizing.
  </p>
</div>
""", unsafe_allow_html=True)

student    = st.session_state.get("student_profile", {})
schedule   = st.session_state.get("schedule", {})
quiz_results = st.session_state.get("quiz_results", [])

today = str(date.today())

# Find today's schedule blocks
today_blocks = []
for day in schedule.get("daily_blocks", []):
    if day.get("date") == today:
        today_blocks = day.get("blocks", [])
        break

# Calculate mastery pct
if quiz_results:
    mastery_pct = round(sum(r.get("score_pct",0) for r in quiz_results) / len(quiz_results))
else:
    mastery_pct = 0

# Days left
days_left = 0
if student.get("exam_date"):
    try:
        from datetime import datetime
        exam_dt = datetime.strptime(student["exam_date"], "%Y-%m-%d").date()
        days_left = (exam_dt - date.today()).days
    except Exception:
        pass

if not student:
    st.info("👋 Set up your profile first! Go to the main page to onboard.")
    st.stop()

if st.button("🌅 Generate Today's Briefing", type="primary", use_container_width=True):
    with st.spinner("Preparing your morning briefing..."):
        prompt = daily_briefing_prompt(student, today_blocks, mastery_pct, days_left)
        briefing = call_gemini_text(prompt, temperature=0.8)
        st.session_state["daily_briefing"] = briefing

if "daily_briefing" in st.session_state:
    st.divider()
    # Quick stats bar
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📅 Today", today)
    c2.metric("⏰ Days Left", days_left)
    c3.metric("🎯 Mastery", f"{mastery_pct}%")
    c4.metric("📚 Today's Blocks", len(today_blocks))

    st.markdown(st.session_state["daily_briefing"])
