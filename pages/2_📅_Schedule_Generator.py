"""
StudyMind AI — Page 2: Schedule Generator
"""
import streamlit as st
import json
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from gemini_client import call_gemini_json
from prompts import schedule_generator_prompt
from mcp_tools import push_to_calendar
from ui_components import render_sidebar_header
from config import COLORS

st.set_page_config(page_title="Schedule Generator — StudyMind AI", page_icon="📅", layout="wide", initial_sidebar_state="expanded")
render_sidebar_header()

st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["info"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["info"]};
            padding:1.5rem 2rem; border-radius:12px; margin-bottom:1.5rem;'>
  <h1 style='margin:0; color:{COLORS["info"]}'>📅 Study Schedule Generator</h1>
  <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}'>
    Tell StudyMind about yourself — get a personalized day-by-day study plan.
  </p>
</div>
""", unsafe_allow_html=True)

# ── Check prerequisites ────────────────────────────────────────────────────────
if "topic_tree" not in st.session_state:
    st.warning("⚠️ No topic tree found. Please parse your syllabus first.")
    if st.button("Go to Syllabus Parser"):
        st.switch_page("pages/1_📚_Syllabus_Parser.py")
    st.stop()

topic_tree = st.session_state["topic_tree"]

# ── Student Profile Form ───────────────────────────────────────────────────────
st.subheader("🎓 Student Profile")
saved_prof = st.session_state.get("student_profile", {})

with st.form("student_profile_form"):
    c1, c2 = st.columns(2)
    with c1:
        default_name = saved_prof.get("student_name", "")
        name = st.text_input("Your Name", value=default_name, placeholder="e.g. Riya")
        
        default_exam_val = date.today() + timedelta(days=14)
        if saved_prof.get("exam_date"):
            try:
                from datetime import datetime as dt
                default_exam_val = dt.strptime(saved_prof["exam_date"], "%Y-%m-%d").date()
            except Exception:
                pass
        exam_date = st.date_input("Exam Date", value=default_exam_val, min_value=date.today())
        
        default_hrs = float(saved_prof.get("daily_hours", 4.0))
        daily_hrs = st.slider("Daily Study Hours", min_value=1.0, max_value=12.0, value=default_hrs, step=0.5)
        
        lvl_options = ["beginner", "intermediate", "advanced"]
        lvl_idx = lvl_options.index(saved_prof.get("current_level", "intermediate")) if saved_prof.get("current_level") in lvl_options else 1
        level = st.selectbox("Current Level", lvl_options, index=lvl_idx)

    with c2:
        default_pref = saved_prof.get("preferred_times", ["morning", "evening"])
        pref_times = st.multiselect(
            "Preferred Study Times",
            ["early_morning", "morning", "afternoon", "evening", "night"],
            default=default_pref
        )
        default_blocked = saved_prof.get("blocked_days", ["sunday"])
        blocked_days = st.multiselect(
            "Days You Can't Study (blocked)",
            ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"],
            default=default_blocked
        )
        known_topics_str = ", ".join(saved_prof.get("known_topics", []))
        known_topics = st.text_input(
            "Topics you already know (comma-separated)",
            value=known_topics_str,
            placeholder="e.g. Arrays, Sorting"
        )
        styles = ["visual", "reading/writing", "auditory", "kinesthetic", "mixed"]
        style_idx = styles.index(saved_prof.get("learning_style", "mixed")) if saved_prof.get("learning_style") in styles else 4
        learning_style = st.selectbox(
            "Learning Style",
            styles,
            index=style_idx
        )

    submitted = st.form_submit_button("🚀 Generate My Study Plan", type="primary", use_container_width=True)

if submitted:
    days_left = (exam_date - date.today()).days
    if days_left < 7:
        st.warning(
            f"⚠️ That's very tight — only **{days_left} days** left! "
            "We'll need to prioritize ruthlessly. I'll build you an intense plan."
        )

    student_profile = {
        "student_name":   name or "Student",
        "subject":        topic_tree.get("subject", ""),
        "exam_date":      str(exam_date),
        "daily_hours":    daily_hrs,
        "preferred_times": pref_times,
        "blocked_days":   blocked_days,
        "current_level":  level,
        "known_topics":   [t.strip() for t in known_topics.split(",") if t.strip()],
        "learning_style": learning_style,
    }

    st.session_state["student_profile"] = student_profile

    with st.spinner("⚡ Assembling high-speed study schedule..."):
        try:
            prompt = schedule_generator_prompt(student_profile, topic_tree, str(date.today()))
            schedule = call_gemini_json(prompt, temperature=0.3, max_tokens=4096)
            st.session_state["schedule"] = schedule
            from storage import save_persistent_state
            save_persistent_state(st.session_state)
            st.success("✅ Study plan generated!")
        except ValueError as e:
            st.error(f"❌ Failed to generate schedule: {e}")
            st.stop()

# ── Display Schedule ───────────────────────────────────────────────────────────
if "schedule" in st.session_state:
    schedule = st.session_state["schedule"]
    summary  = schedule.get("schedule_summary", {})

    st.divider()
    st.subheader("📊 Schedule Summary")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Study Hours", f"{summary.get('total_study_hours', 0)}h")
    m2.metric("Rest Days", len(summary.get("rest_days", [])))
    m3.metric("Mock Test Days", len(summary.get("mock_test_days", [])))
    m4.metric("Revision Starts", summary.get("revision_start_date", "—"))

    st.divider()
    
    view_c1, view_c2 = st.columns([1, 1])
    with view_c1:
        st.subheader("📆 Study Plan")
    with view_c2:
        view_mode = st.radio("View Mode", ["📋 Detailed List", "📅 Visual Calendar"], horizontal=True, label_visibility="collapsed")

    daily = schedule.get("daily_blocks", [])
    day_type_colors = {
        "study":     COLORS["primary"],
        "revision":  COLORS["warning"],
        "mock_test": COLORS["danger"],
        "rest":      COLORS["success"],
    }
    day_type_icons = {"study": "📖", "revision": "🔄", "mock_test": "📝", "rest": "😴"}

    if view_mode == "📅 Visual Calendar":
        calendar_events = []
        for day in daily:
            d_str = day.get("date", "")
            d_type = day.get("day_type", "study")
            b_color = day_type_colors.get(d_type, COLORS["primary"])

            blocks = day.get("blocks", [])
            if not blocks:
                calendar_events.append({
                    "title": "😴 Rest Day",
                    "start": d_str,
                    "allDay": True,
                    "backgroundColor": COLORS["success"],
                    "borderColor": COLORS["success"],
                })
            else:
                for blk in blocks:
                    start_t = blk.get("start_time", "09:00")
                    dur = int(blk.get("duration_minutes", 60))
                    start_iso = f"{d_str}T{start_t}:00"
                    try:
                        from datetime import datetime as dt, timedelta as td
                        dt_s = dt.strptime(start_iso, "%Y-%m-%dT%H:%M:%S")
                        dt_e = dt_s + td(minutes=dur)
                        end_iso = dt_e.strftime("%Y-%m-%dT%H:%M:%S")
                    except Exception:
                        end_iso = start_iso
                    calendar_events.append({
                        "title": f"{blk.get('topic_title','')} ({dur}m)",
                        "start": start_iso,
                        "end": end_iso,
                        "backgroundColor": b_color,
                        "borderColor": b_color,
                    })
        try:
            from streamlit_calendar import calendar
            cal_options = {
                "headerToolbar": {
                    "left": "prev,next today",
                    "center": "title",
                    "right": "dayGridMonth,timeGridWeek,timeGridDay",
                },
                "initialView": "dayGridMonth",
                "navLinks": True,
                "selectable": True,
            }
            calendar(events=calendar_events, options=cal_options, custom_css="""
                .fc-event { border-radius: 4px; font-size: 0.85rem; padding: 2px 4px; }
            """)
        except Exception as e:
            st.warning(f"Calendar view note: {e}")

    else:
        for day in daily:
            d_type  = day.get("day_type", "study")
            d_color = day_type_colors.get(d_type, COLORS["primary"])
            d_icon  = day_type_icons.get(d_type, "📖")
            blocks  = day.get("blocks", [])

            with st.expander(
                f"{d_icon} **{day.get('date','')}** — {d_type.replace('_',' ').title()} "
                f"({len(blocks)} block{'s' if len(blocks)!=1 else ''})"
            ):
                if not blocks:
                    st.markdown(f"*{d_icon} Rest day — recharge!*")
                else:
                    for blk in blocks:
                        blk_copy = dict(blk)
                        blk_copy["date"] = day.get("date", "")
                        cal_data = push_to_calendar(blk_copy)
                        cal_url  = cal_data.get("google_calendar_url", "#")
                        st.markdown(f"""
<div style='border-left:3px solid {d_color}; padding:0.6rem 1rem; margin:0.5rem 0;
            background:{COLORS["card_bg"]}; border-radius:8px;'>
  <div style='display:flex; justify-content:space-between; align-items:center;'>
    <span><strong>{blk.get('start_time','')}</strong> · {blk.get('topic_title','')} · <em>{blk.get('duration_minutes',0)} min</em></span>
    <a href='{cal_url}' target='_blank' style='color:{COLORS["primary"]}; font-size:0.8rem; text-decoration:none;'>📅 Add to Google Calendar ↗</a>
  </div>
  <small style='color:#ccc;'>🎯 {blk.get('session_goal','')}</small><br>
  <small style='color:{COLORS["text_muted"]};'>💡 {blk.get('resources_tip','')}</small>
</div>
""", unsafe_allow_html=True)

    st.divider()
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.download_button(
            "⬇️ Download Schedule (JSON)",
            data=json.dumps(schedule, indent=2),
            file_name="study_schedule.json",
            mime="application/json",
            use_container_width=True,
        )
    with col_b:
        md_text = f"# 📅 StudyMind AI — Study Schedule\n\n"
        md_text += f"**Total Hours:** {summary.get('total_study_hours', 0)}h | **Revision Starts:** {summary.get('revision_start_date', '—')}\n\n---\n\n"
        for day in daily:
            md_text += f"### {day.get('date','')} — {day.get('day_type','study').upper()}\n"
            if not day.get("blocks"):
                md_text += "- *Rest Day — Recharge!*\n\n"
            for b in day.get("blocks", []):
                md_text += f"- **{b.get('start_time','')}** ({b.get('duration_minutes', 60)}m): {b.get('topic_title','')}\n"
                md_text += f"  - 🎯 Goal: {b.get('session_goal','')}\n"
                md_text += f"  - 💡 Tip: {b.get('resources_tip','')}\n"
            md_text += "\n"
        st.download_button(
            "📄 Export Printable Plan (.md)",
            data=md_text,
            file_name="printable_study_plan.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col_c:
        if st.button("➡️ Take a Quiz Now", use_container_width=True):
            st.switch_page("pages/3_🎯_Quiz.py")
