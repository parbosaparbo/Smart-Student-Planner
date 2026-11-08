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




    /* Fix sidebar navigation link alignment */
    section[data-testid="stSidebar"] .stSidebarNav li a {{
        display: flex !important;
        align-items: center !important;
        gap: 10px !important;
    }}
    section[data-testid="stSidebar"] .stSidebarNav li a span {{
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

