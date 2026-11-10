"""
StudyMind AI — Main Entry Point
Smart Study Planner powered by Gemini + Streamlit
"""
import streamlit as st
from datetime import date, datetime
from pathlib import Path
import sys, json

sys.path.insert(0, str(Path(__file__).parent))
from config import APP_TITLE, APP_ICON, APP_SUBTITLE, COLORS, GEMINI_API_KEY
from gemini_client import call_gemini_text, call_gemini_json, get_api_key
from prompts import daily_briefing_prompt, SYSTEM_PROMPT
from storage import load_persistent_state, save_persistent_state, clear_persistent_state
from ui_components import render_sidebar_header, render_gcal_sidebar_status

# ── Auto-restore saved session state ──────────────────────────────────────────
if "state_initialized" not in st.session_state:
    saved = load_persistent_state()
    for k, v in saved.items():
        if k not in st.session_state:
            st.session_state[k] = v
    st.session_state["state_initialized"] = True

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"Dashboard — {APP_TITLE}",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Google OAuth Callback Handler (if redirected to Dashboard root) ────────────
_oauth_code = st.query_params.get("code")
_oauth_state = st.query_params.get("state")
if _oauth_code:
    try:
        import google_calendar as gcal
        student_key = _oauth_state or st.session_state.get("student_profile", {}).get("student_name", "Student")
        gcal.exchange_code_for_token(_oauth_code, student_key)
        st.query_params.clear()
        st.session_state["gcal_just_connected"] = True
        st.switch_page("pages/2_📅_Schedule_Generator.py")
    except Exception as e:
        st.query_params.clear()
        st.error(f"❌ Google Calendar connection failed: {e}")

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  /* Dark theme enhancements */
  .block-container {{ max-width: 1200px; padding-top: 1.5rem; }}
  .stButton > button {{
    border-radius: 10px; font-weight: 600;
    transition: all 0.2s ease;
  }}




    /* Fix sidebar navigation link alignment and spacing */
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{
        display: flex !important;
        align-items: center !important;
        gap: 0.5rem !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] span {{
        display: inline-flex !important;
        align-items: center !important;
        line-height: 1 !important;
    }}








  
  .stButton > button:hover {{ transform: translateY(-1px); }}

  /* Metric cards */
  div[data-testid="metric-container"] {{
    background: {COLORS["card_bg"]};
    border-radius: 10px; padding: 1rem;
    border: 1px solid rgba(255,255,255,0.08);
  }}

  /* Sidebar */
  section[data-testid="stSidebar"] {{
    background: {COLORS["card_bg"]};
  }}

  /* Progress bars */
  .stProgress > div > div {{
    background-color: {COLORS["primary"]};
  }}

  /* Expanders */
  details summary {{ font-weight: 600; }}
</style>
""", unsafe_allow_html=True)

# ── Sidebar Brand Header ───────────────────────────────────────────────────────
render_sidebar_header()
render_gcal_sidebar_status()

# ── API Key Banner (only shows if API key is missing) ──────────────────────────
if not get_api_key():
    with st.expander("⚠️ Gemini API Key Needed — Click to configure", expanded=True):
        st.markdown("Enter your free Google Gemini API key from [Google AI Studio](https://aistudio.google.com/):")
        k_col1, k_col2 = st.columns([4, 1])
        with k_col1:
            input_key = st.text_input("Gemini API Key", type="password", placeholder="AIzaSy...", label_visibility="collapsed", key="banner_api_key")
        with k_col2:
            if st.button("Save Key", type="primary", width="stretch") and input_key.strip():
                st.session_state["gemini_api_key"] = input_key.strip()
                st.rerun()

# ── Main content ───────────────────────────────────────────────────────────────
if not st.session_state.get("student_profile"):
    # ── ONBOARDING ─────────────────────────────────────────────────────────────
    st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["primary"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["primary"]};
            border-radius:16px; padding:1.6rem 2rem; margin-bottom:1.5rem;'>
  <h1 style='margin:0 0 0.3rem 0; font-size:2.1rem; color:{COLORS["primary"]}; font-weight:800;'>🏠 Dashboard</h1>
  <p style='margin:0.2rem 0 0; color:white; font-size:1.15rem; font-weight:600;'>
    👋 Welcome to StudyMind AI — Your Smart Academic Coach
  </p>
  <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}; font-size:0.9rem;'>
    Evidence-based learning: spaced repetition, active recall, Feynman analogies, and personalized schedules.
  </p>
</div>
""", unsafe_allow_html=True)

    # Feature overview cards
    features = [
        ("📚", "Syllabus Parser",     "Upload PDF → structured topic tree with priorities"),
        ("📅", "Smart Scheduler",     "Day-by-day study plan with 70/20/10 distribution"),
        ("🎯", "AI Quiz",             "Scenario-based MCQs — no Googleable questions"),
        ("📊", "Weak Spot Analyzer",  "Find blind spots, get surgical recovery plans"),
        ("💬", "Doubt Solver",        "Socratic tutor — guides you to answers, not spoon-feed"),
        ("📝", "Mock Exam",           "Full exam simulation with integrity monitoring"),
        ("🔄", "Smart Rescheduler",   "Auto-adjusts plan when you score below 70%"),
        ("🌅", "Daily Briefing",      "Personalized 150-word morning briefing every day"),
    ]

    cols = st.columns(4)
    for i, (icon, title, desc) in enumerate(features):
        with cols[i % 4]:
            st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-radius:12px; padding:1.2rem;
            margin-bottom:1rem; border:1px solid rgba(255,255,255,0.08);
            border-top:3px solid {COLORS["primary"]};'>
  <span style='font-size:1.8rem;'>{icon}</span>
  <h4 style='margin:0.5rem 0 0.3rem;'>{title}</h4>
  <p style='margin:0; font-size:0.85rem; color:{COLORS["text_muted"]};'>{desc}</p>
</div>
""", unsafe_allow_html=True)

    st.divider()

    st.subheader("🚀 Student Setup — Get Started")
    st.caption("Fill in your details below so StudyMind AI can craft your personalized study plan.")

    tab_quick, tab_chat = st.tabs(["⚡ 1-Minute Quick Form", "💬 Conversational AI Interview"])

    with tab_quick:
        with st.form("onboarding_form"):
            c1, c2 = st.columns(2)
            with c1:
                name         = st.text_input("Your Name *", placeholder="e.g. Priya")
                subject      = st.text_input("Subject / Course *", placeholder="e.g. Computer Networks")
                exam_date    = st.date_input("Exam Date *", min_value=date.today())
                current_lvl  = st.selectbox("Your Current Level",
                                            ["beginner", "intermediate", "advanced"])
            with c2:
                daily_hours  = st.slider("Daily Study Hours", 1.0, 12.0, 4.0, 0.5)
                pref_times   = st.multiselect(
                    "Preferred Study Times",
                    ["early_morning", "morning", "afternoon", "evening", "night"],
                    default=["morning", "evening"]
                )
                blocked_days = st.multiselect(
                    "Blocked Days (can't study)",
                    ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"],
                    default=["sunday"]
                )
                learning_style = st.selectbox(
                    "Learning Style",
                    ["visual", "reading/writing", "auditory", "kinesthetic", "mixed"]
                )
                known_topics = st.text_input("Topics you already know (optional)",
                                             placeholder="e.g. OSI Model, Subnetting")

            submit = st.form_submit_button("✅ Start Studying Now!", type="primary", width="stretch")

        if submit and name and subject:
            days_left = (exam_date - date.today()).days
            profile = {
                "student_name":   name,
                "subject":        subject,
                "exam_date":      str(exam_date),
                "daily_hours":    daily_hours,
                "preferred_times": pref_times,
                "blocked_days":   blocked_days,
                "current_level":  current_lvl,
                "known_topics":   [t.strip() for t in known_topics.split(",") if t.strip()],
                "learning_style": learning_style,
            }
            st.session_state["student_profile"] = profile
            save_persistent_state(st.session_state)

            if days_left < 7:
                st.warning(
                    f"⚠️ That's very tight — only **{days_left} days** until your exam! "
                    "We'll prioritize ruthlessly. Ready for an intense plan?"
                )

            st.success(f"✅ Welcome, {name}! Your profile is set up.")
            st.balloons()
            st.rerun()

        elif submit:
            st.error("Please fill in at least your Name and Subject.")

    with tab_chat:
        st.markdown("""
        **💬 AI Interview Mode (Feature 9)**  
        *StudyMind AI asks one question at a time to build your profile conversationally.*
        """)
        # Initialize onboarding question step
        if "onboard_step" not in st.session_state:
            st.session_state["onboard_step"] = 0
            st.session_state["onboard_data"] = {}

        questions = [
            ("student_name", "👋 Hi! I'm StudyMind AI, your personal academic coach. What is your name?"),
            ("subject", "Great! What subject or course are you preparing for? (e.g. Computer Networks)"),
            ("exam_date", "When is your exam date? (YYYY-MM-DD format, e.g. 2026-12-01)"),
            ("daily_hours", "How many hours per day can you realistically dedicate to studying? (e.g. 4)"),
            ("preferred_times", "What are your preferred study times? (e.g. morning, evening, night)"),
            ("current_level", "How would you rate your current preparation level? (beginner, intermediate, or advanced)"),
        ]

        step = st.session_state["onboard_step"]
        if step < len(questions):
            field, q_text = questions[step]
            st.info(f"🧠 **StudyMind AI:** {q_text}")
            user_ans = st.text_input(f"Your Answer for Step {step+1}:", key=f"onboard_ans_{step}")
            if st.button("Submit Answer ➡️", key=f"onboard_btn_{step}") and user_ans.strip():
                st.session_state["onboard_data"][field] = user_ans.strip()
                st.session_state["onboard_step"] += 1
                st.rerun()
        else:
            data = st.session_state["onboard_data"]
            st.success("🎉 All questions answered! Here is your profile summary:")
            st.json(data)
            if st.button("🚀 Confirm & Go to Dashboard", type="primary"):
                profile = {
                    "student_name":   data.get("student_name", "Student"),
                    "subject":        data.get("subject", "General"),
                    "exam_date":      data.get("exam_date", str(date.today() + timedelta(days=21))),
                    "daily_hours":    float(data.get("daily_hours", 4.0)),
                    "preferred_times": [t.strip() for t in data.get("preferred_times", "morning, evening").split(",")],
                    "blocked_days":   ["sunday"],
                    "current_level":  data.get("current_level", "intermediate"),
                    "known_topics":   [],
                    "learning_style": "visual",
                }
                st.session_state["student_profile"] = profile
                save_persistent_state(st.session_state)
                st.rerun()

else:
    # ── DASHBOARD ──────────────────────────────────────────────────────────────
    student = st.session_state["student_profile"]
    student_name = student.get("student_name", "Student")

    try:
        exam_dt   = datetime.strptime(student["exam_date"], "%Y-%m-%d").date()
        days_left = (exam_dt - date.today()).days
    except Exception:
        days_left = 0

    quiz_results = st.session_state.get("quiz_results", [])
    mastery_pct  = round(sum(r.get("score_pct", 0) for r in quiz_results) / len(quiz_results)) if quiz_results else 0

    # Header
    st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["primary"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["primary"]};
            border-radius:16px; padding:1.6rem 2rem; margin-bottom:1.5rem;'>
  <h1 style='margin:0 0 0.4rem 0; font-size:1.85rem; color:#FFFFFF; font-weight:800;'>
    Good {"morning" if datetime.now().hour < 12 else "afternoon" if datetime.now().hour < 17 else "evening"}, {student_name}! 👋
  </h1>
  <p style='margin:0; color:{COLORS["text_muted"]}; font-size:0.95rem;'>
    📚 {student.get("subject","—")} · 📅 {days_left} days to exam · 🎯 {mastery_pct}% overall mastery
  </p>
</div>
""", unsafe_allow_html=True)

    # Progress overview
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📅 Days to Exam",  days_left, delta=None)
    c2.metric("🎯 Mastery",       f"{mastery_pct}%")
    c3.metric("📝 Quizzes Taken", len(quiz_results))
    schedule = st.session_state.get("schedule", {})
    c4.metric("📆 Schedule",      "✅ Ready" if schedule else "⚠️ Pending")

    st.divider()

    # Action cards
    st.subheader("🎯 What would you like to do today?")

    r1c1, r1c2, r1c3 = st.columns(3)

    with r1c1:
        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-radius:12px; padding:1.5rem;
            border-top:3px solid {COLORS["primary"]}; text-align:center;'>
  <span style='font-size:2.5rem;'>📚</span>
  <h3 style='margin:0.5rem 0 0.3rem;'>Parse Syllabus</h3>
  <p style='color:{COLORS["text_muted"]}; font-size:0.9rem;'>
    Upload PDF or paste text to build your topic tree
  </p>
</div>
""", unsafe_allow_html=True)
        if st.button("→ Open Syllabus Parser", key="btn_syllabus", width="stretch"):
            st.switch_page("pages/1_📚_Syllabus_Parser.py")

    with r1c2:
        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-radius:12px; padding:1.5rem;
            border-top:3px solid {COLORS["info"]}; text-align:center;'>
  <span style='font-size:2.5rem;'>📅</span>
  <h3 style='margin:0.5rem 0 0.3rem;'>Study Schedule</h3>
  <p style='color:{COLORS["text_muted"]}; font-size:0.9rem;'>
    Generate your personalized day-by-day plan
  </p>
</div>
""", unsafe_allow_html=True)
        if st.button("→ Build Schedule", key="btn_schedule", width="stretch"):
            st.switch_page("pages/2_📅_Schedule_Generator.py")

    with r1c3:
        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-radius:12px; padding:1.5rem;
            border-top:3px solid {COLORS["success"]}; text-align:center;'>
  <span style='font-size:2.5rem;'>🎯</span>
  <h3 style='margin:0.5rem 0 0.3rem;'>Take a Quiz</h3>
  <p style='color:{COLORS["text_muted"]}; font-size:0.9rem;'>
    Scenario-based MCQs to test real understanding
  </p>
</div>
""", unsafe_allow_html=True)
        if st.button("→ Start Quiz", key="btn_quiz", width="stretch"):
            st.switch_page("pages/3_🎯_Quiz.py")

    r2c1, r2c2, r2c3 = st.columns(3)

    with r2c1:
        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-radius:12px; padding:1.5rem;
            border-top:3px solid {COLORS["warning"]}; text-align:center;'>
  <span style='font-size:2.5rem;'>📊</span>
  <h3 style='margin:0.5rem 0 0.3rem;'>Weak Spots</h3>
  <p style='color:{COLORS["text_muted"]}; font-size:0.9rem;'>
    Find exactly where you're struggling
  </p>
</div>
""", unsafe_allow_html=True)
        if st.button("→ Analyze", key="btn_analyze", width="stretch"):
            st.switch_page("pages/4_📊_Weak_Spot_Analyzer.py")

    with r2c2:
        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-radius:12px; padding:1.5rem;
            border-top:3px solid {COLORS["primary"]}; text-align:center;'>
  <span style='font-size:2.5rem;'>💬</span>
  <h3 style='margin:0.5rem 0 0.3rem;'>Ask a Doubt</h3>
  <p style='color:{COLORS["text_muted"]}; font-size:0.9rem;'>
    Socratic tutor — real understanding, not answers
  </p>
</div>
""", unsafe_allow_html=True)
        if st.button("→ Open Chatbot", key="btn_chat", width="stretch"):
            st.switch_page("pages/5_💬_Doubt_Solver.py")

    with r2c3:
        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-radius:12px; padding:1.5rem;
            border-top:3px solid {COLORS["danger"]}; text-align:center;'>
  <span style='font-size:2.5rem;'>📝</span>
  <h3 style='margin:0.5rem 0 0.3rem;'>Mock Exam</h3>
  <p style='color:{COLORS["text_muted"]}; font-size:0.9rem;'>
    Full simulation with integrity monitoring
  </p>
</div>
""", unsafe_allow_html=True)
        if st.button("→ Start Mock", key="btn_mock", width="stretch"):
            st.switch_page("pages/6_📝_Mock_Exam.py")

    r3c1, r3c2, r3c3 = st.columns(3)

    with r3c1:
        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-radius:12px; padding:1.5rem;
            border-top:3px solid {COLORS["warning"]}; text-align:center;'>
  <span style='font-size:2.5rem;'>🌅</span>
  <h3 style='margin:0.5rem 0 0.3rem;'>Daily Briefing</h3>
  <p style='color:{COLORS["text_muted"]}; font-size:0.9rem;'>
    150-word morning plan & motivation
  </p>
</div>
""", unsafe_allow_html=True)
        if st.button("→ Read Briefing", key="btn_briefing", width="stretch"):
            st.switch_page("pages/7_🌅_Daily_Briefing.py")

    with r3c2:
        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-radius:12px; padding:1.5rem;
            border-top:3px solid {COLORS["primary"]}; text-align:center;'>
  <span style='font-size:2.5rem;'>🃏</span>
  <h3 style='margin:0.5rem 0 0.3rem;'>Flashcards</h3>
  <p style='color:{COLORS["text_muted"]}; font-size:0.9rem;'>
    Feynman analogies & spaced repetition
  </p>
</div>
""", unsafe_allow_html=True)
        if st.button("→ Practice Cards", key="btn_flash", width="stretch"):
            st.switch_page("pages/8_🃏_Flashcards.py")

    with r3c3:
        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-radius:12px; padding:1.5rem;
            border-top:3px solid {COLORS["success"]}; text-align:center;'>
  <span style='font-size:2.5rem;'>⏱️</span>
  <h3 style='margin:0.5rem 0 0.3rem;'>Focus Timer</h3>
  <p style='color:{COLORS["text_muted"]}; font-size:0.9rem;'>
    Pomodoro session linked to schedule
  </p>
</div>
""", unsafe_allow_html=True)
        if st.button("→ Start Pomodoro", key="btn_focus", width="stretch"):
            st.switch_page("pages/9_⏱️_Focus_Timer.py")

    # ── Weak Topics, Adaptive Rescheduling & Upcoming Revisions ───────────
    from core.weak_topic_manager import extract_topic_performance, identify_weak_topics
    mock_eval = st.session_state.get("mock_evaluation")
    schedule = st.session_state.get("schedule", {})
    daily_blocks = schedule.get("daily_blocks", [])

    weak_topics = identify_weak_topics(quiz_results, mock_eval, threshold=70.0)

    # Find upcoming revision blocks in schedule
    from datetime import date as _dt_date
    today_str = _dt_date.today().strftime("%Y-%m-%d")
    upcoming_revisions = []
    for d in daily_blocks:
        if d.get("date", "") >= today_str:
            for b in d.get("blocks", []):
                if b.get("is_revision"):
                    rev_item = dict(b)
                    rev_item["date"] = d.get("date")
                    upcoming_revisions.append(rev_item)

    st.divider()
    dash_col_title, dash_col_action = st.columns([3, 1])
    with dash_col_title:
        st.subheader("🔄 Weak Topics & Adaptive Spaced Revisions")
    with dash_col_action:
        if st.button("📊 Open Rescheduler ↗", width="stretch", key="dash_btn_weak"):
            st.switch_page("pages/4_📊_Weak_Spot_Analyzer.py")

    # Metrics row for weak topics, exam scores, and schedule updates
    d_m1, d_m2, d_m3, d_m4 = st.columns(4)

    # 1. Weak Topics Count
    d_m1.metric(
        "⚠️ Weak Topics (<70%)",
        len(weak_topics),
        f"{len(weak_topics)} needing revision" if weak_topics else "All clear!",
        delta_color="inverse" if weak_topics else "normal",
    )

    # 2. Latest Exam / Quiz Score
    latest_score_str = "—"
    if quiz_results:
        latest_score_str = f"{quiz_results[-1].get('score_pct', 0)}%"
    d_m2.metric("📝 Latest Quiz Score", latest_score_str, f"{len(quiz_results)} attempts total")

    # 3. Mock Exam Readiness
    mock_readiness_str = "Not Taken"
    if mock_eval and isinstance(mock_eval, dict):
        mock_readiness_str = f"{mock_eval.get('overall_grade','—')} ({mock_eval.get('readiness_pct', 0)}%)"
    d_m3.metric("🎯 Mock Readiness", mock_readiness_str)

    # 4. Upcoming Revisions in Plan
    d_m4.metric("🔄 Scheduled Revisions", len(upcoming_revisions), "Auto-slotted in calendar")

    # Detailed cards for weak topics and upcoming revisions
    if weak_topics or upcoming_revisions:
        c_weak_col, c_rev_col = st.columns(2)

        with c_weak_col:
            st.markdown(f"<h5 style='color:{COLORS['warning']}; margin-bottom:0.5rem;'>🎯 Identified Weak Topics (<70%)</h5>", unsafe_allow_html=True)
            if weak_topics:
                for wt in weak_topics[:3]:
                    urg_icon = "🔴" if wt.get("urgency") == "critical" else "🟠"
                    st.markdown(f"{urg_icon} **{wt.get('topic_title','')}** — **{wt.get('recent_accuracy', 0)}%** ({wt.get('repeated_mistakes_count', 0)} mistakes)")
                    if wt.get("missed_concepts"):
                        st.caption("Focus: " + ", ".join([str(c) for c in wt["missed_concepts"][:2]]))
            else:
                st.success("🎉 All tested topics are currently >= 70% mastery!")

        with c_rev_col:
            st.markdown(f"<h5 style='color:{COLORS['primary']}; margin-bottom:0.5rem;'>📅 Next Spaced Revision Sessions</h5>", unsafe_allow_html=True)
            if upcoming_revisions:
                for rev in upcoming_revisions[:3]:
                    st.markdown(
                        f"• **{rev.get('date')}** ({rev.get('start_time','09:00')}, {rev.get('duration_minutes',45)}m): "
                        f"**Round {rev.get('revision_round', 1)}** — {rev.get('topic_title')}"
                    )
            else:
                st.info("No upcoming revisions in schedule. Take a quiz or mock exam to trigger automatic adaptive revisions!")

    # Schedule Recalculation Badge
    resched_summary = schedule.get("reschedule_summary")
    if resched_summary:
        st.markdown(
            f"""<div style='background:{COLORS["card_bg"]}; border:1px solid {COLORS["success"]}44; border-radius:8px; padding:0.6rem 1rem; margin-top:0.6rem;'>
  <small style='color:{COLORS["success"]};'>✅ <b>Schedule Auto-Adjusted:</b> Recalculated at {resched_summary.get("recalculated_at", "recently")} · {resched_summary.get("revisions_added", 0)} revision session(s) active · In-app & Google Calendar synchronized without overlaps.</small>
</div>""",
            unsafe_allow_html=True
        )

    # ── Google Calendar Quick Sync Card ──────────────────────────────────────────
    try:
        import google_calendar as gcal
        student_key = student.get("student_name", "Student")
        is_gcal_conn = gcal.is_connected(student_key)
        ics_data = gcal.export_schedule_to_ics(schedule, student_name=student_key)

        st.markdown("<div style='margin-top:0.8rem;'></div>", unsafe_allow_html=True)
        gc_col1, gc_col2, gc_col3 = st.columns([2.5, 1, 1.2])
        with gc_col1:
            if is_gcal_conn:
                g_email = gcal.get_connected_account_email(student_key)
                email_display = f"**{g_email}**" if g_email and "@" in g_email else "Google Account"
                st.markdown(f"📅 **Google Calendar:** Connected as {email_display} · <small style='color:{COLORS['success']}'>🔔 10-min reminders active</small>", unsafe_allow_html=True)
            else:
                st.markdown(f"📅 **Google Calendar:** <small style='color:{COLORS['text_muted']}'>Sync your study schedule &amp; reminders</small>", unsafe_allow_html=True)

        with gc_col2:
            if is_gcal_conn:
                if st.button("⚡ Sync Calendar", key="dash_gcal_sync", width="stretch"):
                    with st.spinner("Syncing schedule with Google Calendar..."):
                        try:
                            sync_r = gcal.sync_schedule_to_calendar(schedule, student_key, student_key)
                            st.session_state["gcal_event_map"] = sync_r
                            save_persistent_state(st.session_state)
                            st.success(f"Synced {sync_r['created'] + sync_r['updated']} sessions!")
                        except Exception as e:
                            st.error(f"Sync error: {e}")
            else:
                if st.button("🔗 Connect", key="dash_gcal_conn", width="stretch", type="primary"):
                    st.switch_page("pages/2_📅_Schedule_Generator.py")

        with gc_col3:
            st.download_button(
                label="📥 Export .ics",
                data=ics_data,
                file_name=f"studymind_schedule_{date.today().strftime('%Y%m%d')}.ics",
                mime="text/calendar",
                width="stretch",
                key="dash_dl_ics"
            )
    except Exception as gcal_dash_err:
        pass

    # Quick mastery trend (if quiz data)
    if quiz_results:
        st.divider()
        col_hdr, col_btn = st.columns([2, 1])
        with col_hdr:
            st.subheader("📈 Topic Mastery Overview")
        with col_btn:
            if st.button("📊 Open Full Progress Analytics ↗", width="stretch"):
                st.switch_page("pages/10_📈_Student_Progress.py")
        import plotly.graph_objects as go

        fig = go.Figure()
        topics_names = [r.get("topic_title","")[:20] for r in quiz_results]
        scores       = [r.get("score_pct", 0) for r in quiz_results]
        bar_colors   = [
            COLORS["success"] if s >= 70 else COLORS["warning"] if s >= 50 else COLORS["danger"]
            for s in scores
        ]

        fig.add_trace(go.Bar(
            x=topics_names, y=scores,
            marker_color=bar_colors,
            text=[f"{s}%" for s in scores],
            textposition="outside",
        ))
        fig.add_hline(y=70, line_dash="dash", line_color="white",
                      annotation_text="70% threshold", annotation_position="right")
        fig.update_layout(
            height=320,
            xaxis_title="Topic", yaxis_title="Score (%)",
            yaxis_range=[0, 110],
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig, width="stretch")

    # ── Database & Backup Controls ────────────────────────────────────────────────
    st.divider()
    with st.expander("🗄️ Database Management & Backups", expanded=False):
        col_db_info, col_db_actions = st.columns([2, 1])
        with col_db_info:
            try:
                import storage
                v = storage.verify_migration()
                st.markdown(f"**Database Status:** `SQLite (WAL mode)` · **Integrity:** `{'✅ Healthy (' + v.get('database_integrity', 'ok') + ')' if v.get('is_healthy') else '⚠️ Check'}`")
                st.caption(f"Tables: {', '.join([f'{k}: {cnt}' for k, cnt in v.get('table_row_counts', {}).items() if cnt > 0])}")
            except Exception as d_err:
                st.caption(f"Database status error: {d_err}")

        with col_db_actions:
            if st.button("💾 Create Backup Now", width="stretch"):
                try:
                    import storage
                    res = storage.create_backup(backup_type="manual")
                    if res.get("success"):
                        st.success(f"Backup created: {res.get('filename')} ({res.get('file_size_bytes')} bytes)")
                    else:
                        st.error(f"Backup failed: {res.get('error')}")
                except Exception as b_err:
                    st.error(f"Error creating backup: {b_err}")

        # List existing backups
        try:
            import storage
            b_list = storage.list_backups()
            if b_list:
                st.markdown("<small><b>Recent Backups:</b></small>", unsafe_allow_html=True)
                for bk in b_list[:3]:
                    valid_str = "✅ Valid" if bk.get("valid") else "⚠️ Corrupted"
                    st.caption(f"• `{bk.get('filename')}` ({bk.get('size_bytes')} bytes) · {bk.get('modified')[:19]} · {valid_str}")
        except Exception:
            pass

    # Reset button
    st.divider()
    if st.button("🔄 Reset Profile (Start Over)", type="secondary"):
        # Disconnect Google Calendar if connected
        try:
            import google_calendar as gcal
            s_key = student.get("student_name", "Student")
            if gcal.is_connected(s_key):
                gcal.delete_token(s_key)
        except Exception:
            pass
        clear_persistent_state()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

