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
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  /* Dark theme enhancements */
  .block-container {{ max-width: 1200px; padding-top: 1.5rem; }}
  .stButton > button {{
    border-radius: 10px; font-weight: 600;
    transition: all 0.2s ease;
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

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style='text-align:center; padding:1rem 0;'>
      <h2 style='margin:0; color:{COLORS["primary"]};'>{APP_ICON} {APP_TITLE}</h2>
      <p style='margin:0; font-size:0.8rem; color:{COLORS["text_muted"]};'>{APP_SUBTITLE}</p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # API key status
    active_key = get_api_key()
    if active_key:
        st.success("✅ Gemini API Active")
        with st.expander("🔑 Change API Key"):
            new_key = st.text_input("Enter new Gemini API Key", type="password", key="sidebar_key_change")
            if st.button("Update Key"):
                st.session_state["gemini_api_key"] = new_key.strip()
                st.rerun()
    else:
        st.warning("🔑 Gemini API Key Needed")
        user_key = st.text_input("Paste Gemini API Key", type="password", placeholder="AIzaSy...", key="sidebar_key_input")
        if user_key:
            st.session_state["gemini_api_key"] = user_key.strip()
            st.rerun()
        st.caption("Or add `GEMINI_API_KEY` to `.env` file.")

    st.divider()

    # Student status
    student = st.session_state.get("student_profile", {})
    if student:
        exam_date = student.get("exam_date", "")
        try:
            days_left = (datetime.strptime(exam_date, "%Y-%m-%d").date() - date.today()).days
        except Exception:
            days_left = "?"

        st.markdown(f"""
<div style='background:{COLORS["primary"]}22; border-radius:10px; padding:1rem;'>
  <p style='margin:0; font-size:1.1rem; font-weight:600;'>👋 {student.get("student_name","Student")}</p>
  <p style='margin:0.3rem 0 0; font-size:0.85rem; color:{COLORS["text_muted"]};'>
    📚 {student.get("subject","—")}<br>
    📅 {days_left} days to exam<br>
    ⏱️ {student.get("daily_hours","?")}h/day
  </p>
</div>
""", unsafe_allow_html=True)

        quiz_results = st.session_state.get("quiz_results", [])
        if quiz_results:
            mastery = round(sum(r.get("score_pct", 0) for r in quiz_results) / len(quiz_results))
            mastery_color = (COLORS["success"] if mastery >= 70
                             else COLORS["warning"] if mastery >= 50
                             else COLORS["danger"])
            st.markdown(f"""
<div style='margin-top:0.5rem; text-align:center;'>
  <span style='color:{mastery_color}; font-size:1.5rem; font-weight:700;'>{mastery}%</span>
  <br><small style='color:{COLORS["text_muted"]};'>Overall Mastery</small>
</div>
""", unsafe_allow_html=True)
    else:
        st.info("👆 Complete onboarding below to get started.")

    st.divider()

    # Quick navigation
    st.markdown("**🧭 Quick Navigation**")
    nav_items = [
        ("📚 Syllabus Parser",    "pages/1_📚_Syllabus_Parser.py"),
        ("📅 Schedule Generator", "pages/2_📅_Schedule_Generator.py"),
        ("🎯 Quiz",               "pages/3_🎯_Quiz.py"),
        ("📊 Weak Spot Analyzer", "pages/4_📊_Weak_Spot_Analyzer.py"),
        ("💬 Doubt Solver",       "pages/5_💬_Doubt_Solver.py"),
        ("📝 Mock Exam",          "pages/6_📝_Mock_Exam.py"),
        ("🌅 Daily Briefing",     "pages/7_🌅_Daily_Briefing.py"),
        ("🃏 Flashcards",         "pages/8_🃏_Flashcards.py"),
    ]
    for label, page in nav_items:
        if st.button(label, use_container_width=True):
            st.switch_page(page)

# ── Main content ───────────────────────────────────────────────────────────────
if not st.session_state.get("student_profile"):
    # ── ONBOARDING ─────────────────────────────────────────────────────────────
    st.markdown(f"""
<div style='text-align:center; padding:3rem 2rem;'>
  <h1 style='font-size:3rem; margin:0;'>{APP_ICON}</h1>
  <h1 style='color:{COLORS["primary"]}; margin:0.5rem 0;'>{APP_TITLE}</h1>
  <p style='font-size:1.2rem; color:{COLORS["text_muted"]};'>{APP_SUBTITLE}</p>
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

    demo_col1, demo_col2 = st.columns([2, 1])
    with demo_col1:
        st.subheader("🚀 Student Setup — Get Started")
        st.caption("Fill in your details, or load a complete 7th Semester sample setup in 1 click.")
    with demo_col2:
        if st.button("✨ Load 7th Sem Demo Setup", use_container_width=True):
            from demo_data import get_demo_state
            demo = get_demo_state()
            for k, v in demo.items():
                st.session_state[k] = v
            save_persistent_state(st.session_state)
            st.success("✅ 7th Sem Demo Setup loaded!")
            st.rerun()

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

            submit = st.form_submit_button("✅ Start Studying Now!", type="primary", use_container_width=True)

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
<div style='background:linear-gradient(135deg,{COLORS["primary"]}33,{COLORS["card_bg"]});
            border-radius:16px; padding:2rem; margin-bottom:1.5rem;'>
  <h1 style='margin:0; font-size:2rem;'>Good {"morning" if datetime.now().hour < 12 else "afternoon" if datetime.now().hour < 17 else "evening"}, {student_name}! 👋</h1>
  <p style='margin:0.5rem 0 0; color:{COLORS["text_muted"]};'>
    📚 {student.get("subject","—")} · 📅 {days_left} days to exam · 🎯 {mastery_pct}% mastery
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
        if st.button("→ Open Syllabus Parser", key="btn_syllabus", use_container_width=True):
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
        if st.button("→ Build Schedule", key="btn_schedule", use_container_width=True):
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
        if st.button("→ Start Quiz", key="btn_quiz", use_container_width=True):
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
        if st.button("→ Analyze", key="btn_analyze", use_container_width=True):
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
        if st.button("→ Open Chatbot", key="btn_chat", use_container_width=True):
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
        if st.button("→ Start Mock", key="btn_mock", use_container_width=True):
            st.switch_page("pages/6_📝_Mock_Exam.py")

    # Quick mastery trend (if quiz data)
    if quiz_results:
        st.divider()
        st.subheader("📈 Topic Mastery Overview")
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
        st.plotly_chart(fig, use_container_width=True)

    # Reset button
    st.divider()
    if st.button("🔄 Reset Profile (Start Over)", type="secondary"):
        clear_persistent_state()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

