"""
StudyMind AI — Page 6: Mock Exam Evaluator
"""
import streamlit as st
import time
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from gemini_client import call_gemini_json
from prompts import quiz_generator_prompt, mock_exam_evaluator_prompt
from mcp_tools import generate_mock_exam
from ui_components import render_sidebar_header
from config import COLORS, DIFFICULTY_LABELS

st.set_page_config(page_title="Mock Exam — StudyMind AI", page_icon="📝", layout="wide", initial_sidebar_state="expanded")
render_sidebar_header()

st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["danger"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["danger"]};
            padding:1.5rem 2rem; border-radius:12px; margin-bottom:1.5rem;'>
  <h1 style='margin:0; color:{COLORS["danger"]}'>📝 Mock Exam</h1>
  <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}'>
    Full timed exam simulation — get honest feedback + readiness score.
  </p>
</div>
""", unsafe_allow_html=True)

student = st.session_state.get("student_profile", {})
student_name = student.get("student_name", "Student")
topic_tree   = st.session_state.get("topic_tree", {})
topics       = topic_tree.get("topics", [])

# ── Setup ──────────────────────────────────────────────────────────────────────
if "mock_exam" not in st.session_state:
    st.subheader("⚙️ Exam Setup")

    with st.form("mock_exam_setup"):
        c1, c2 = st.columns(2)
        with c1:
            if topics:
                selected_topics = st.multiselect(
                    "Topics to include",
                    [t["title"] for t in topics],
                    default=[t["title"] for t in topics[:3]]
                )
            else:
                selected_topics = [st.text_input("Topic", placeholder="e.g. Data Structures")]

            total_questions = st.slider("Total Questions", 5, 30, 10)

        with c2:
            st.markdown("""
**Mock Exam Rules:**
- Timed (90 seconds per question)
- No hints, no explanations during exam
- Full performance report after submission
- Integrity monitoring enabled
- Results saved for weak spot analysis
            """)

        start_btn = st.form_submit_button("🚀 Start Mock Exam", type="primary", width="stretch")

    if start_btn and selected_topics:
        # Build topic objects list
        chosen_topic_objs = []
        for t_title in selected_topics:
            t_match = next((t for t in topics if t.get("title") == t_title), None)
            chosen_topic_objs.append({
                "id": t_match.get("id", f"t{len(chosen_topic_objs)+1}") if t_match else f"t{len(chosen_topic_objs)+1}",
                "title": t_title,
            })

        with st.spinner(f"⚡ Assembling {total_questions} syllabus-grounded questions via MCP..."):
            t0 = time.time()
            mock_res = generate_mock_exam(
                selected_topics=chosen_topic_objs,
                total_questions=total_questions,
                difficulty=3,
            )
            all_questions = mock_res.get("questions", [])
            elapsed = round(time.time() - t0, 3)

        if all_questions:
            st.session_state["mock_exam"] = {
                "questions":  all_questions[:total_questions],
                "start_time": time.time(),
                "execution_time_seconds": elapsed,
            }
            st.session_state["mock_answers"]   = {}
            st.session_state["mock_submitted"] = False
            st.toast(f"⚡ Exam ready in {elapsed}s!", icon="📝")
            st.rerun()
        else:
            st.error("Failed to generate exam questions. Please try again.")

# ── Running Exam ───────────────────────────────────────────────────────────────
elif not st.session_state.get("mock_submitted", False):
    exam      = st.session_state["mock_exam"]
    questions = exam["questions"]
    elapsed   = int(time.time() - exam["start_time"])
    total_sec = len(questions) * 90

    # Timer bar
    remaining = max(0, total_sec - elapsed)
    progress_val = min(max(elapsed / total_sec, 0.0), 1.0) if total_sec > 0 else 1.0
    st.progress(progress_val,
                text=f"⏱️ {remaining//60}:{remaining%60:02d} remaining — {len(questions)} questions")

    if elapsed >= total_sec:
        st.warning("⏰ Time's up! Auto-submitting...")
        st.session_state["mock_submitted"] = True
        st.session_state["mock_time_taken"] = elapsed
        st.rerun()

    with st.form("mock_exam_form"):
        for i, q in enumerate(questions):
            opts = q.get("options", {})
            st.markdown(f"**Q{i+1}.** {q.get('question','')}")
            st.caption(f"Topic: {q.get('topic_title','')}")
            answer = st.radio(
                f"Q{i+1}",
                list(opts.keys()),
                format_func=lambda k, opts=opts: f"{k}: {opts[k]}",
                key=f"mock_q{i}",
                index=None,
                label_visibility="collapsed"
            )
            st.session_state["mock_answers"][q.get("id", f"q{i}")] = answer
            st.divider()

        submitted = st.form_submit_button("📤 Submit Exam", type="primary", width="stretch")

    if submitted:
        st.session_state["mock_submitted"] = True
        st.session_state["mock_time_taken"] = int(time.time() - exam["start_time"])
        st.rerun()

# ── Evaluation ─────────────────────────────────────────────────────────────────
elif st.session_state.get("mock_submitted", False) and "mock_evaluation" not in st.session_state:
    exam        = st.session_state["mock_exam"]
    questions   = exam["questions"]
    answers     = st.session_state.get("mock_answers", {})
    time_taken  = st.session_state.get("mock_time_taken", 0)

    with st.spinner("🧠 Evaluating your exam performance..."):
        try:
            prompt = mock_exam_evaluator_prompt(
                answers=list(answers.items()),
                questions=questions,
                student_name=student_name,
                time_taken_seconds=time_taken
            )
            evaluation = call_gemini_json(prompt, temperature=0.3)
            st.session_state["mock_evaluation"] = evaluation
            st.rerun()
        except ValueError as e:
            st.error(f"❌ Evaluation failed: {e}")

# ── Show Evaluation ────────────────────────────────────────────────────────────
if "mock_evaluation" in st.session_state:
    ev = st.session_state["mock_evaluation"]

    grade   = ev.get("overall_grade", "F")
    readiness = ev.get("exam_readiness", "at_risk")
    pct     = ev.get("readiness_pct", 0)

    grade_color = {
        "A": COLORS["success"], "B": COLORS["info"],
        "C": COLORS["warning"], "D": COLORS["warning"], "F": COLORS["danger"]
    }.get(grade, COLORS["danger"])

    readiness_color = {
        "ready": COLORS["success"], "nearly_ready": COLORS["info"],
        "needs_work": COLORS["warning"], "at_risk": COLORS["danger"]
    }.get(readiness, COLORS["danger"])

    # Hero metrics
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
<div style='text-align:center; padding:1.5rem; background:{COLORS["card_bg"]};
            border-radius:12px; border-top:3px solid {grade_color};'>
  <h1 style='color:{grade_color}; margin:0;'>{grade}</h1>
  <p style='margin:0; color:{COLORS["text_muted"]};'>Overall Grade</p>
</div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
<div style='text-align:center; padding:1.5rem; background:{COLORS["card_bg"]};
            border-radius:12px; border-top:3px solid {readiness_color};'>
  <h2 style='color:{readiness_color}; margin:0;'>{pct}%</h2>
  <p style='margin:0; color:{COLORS["text_muted"]};'>Exam Readiness</p>
</div>""", unsafe_allow_html=True)
    with c3:
        tm = ev.get("time_management", {})
        st.markdown(f"""
<div style='text-align:center; padding:1.5rem; background:{COLORS["card_bg"]};
            border-radius:12px; border-top:3px solid {COLORS["info"]};'>
  <h3 style='color:{COLORS["info"]}; margin:0;'>{tm.get("assessment","—").title()}</h3>
  <p style='margin:0; color:{COLORS["text_muted"]};'>Time Management</p>
</div>""", unsafe_allow_html=True)

    # Integrity flag
    integrity = ev.get("integrity_flag", {})
    if integrity.get("flagged"):
        st.warning(f"⚑ {integrity.get('note','')}")

    # Coach message
    coach = ev.get("final_coach_message", "")
    if coach:
        st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-left:4px solid {COLORS["primary"]};
            padding:1.2rem; border-radius:8px; margin:1rem 0;'>
  🧠 <strong>StudyMind's Assessment:</strong><br><br>{coach}
</div>""", unsafe_allow_html=True)

    # Strengths / Improvements
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("💪 Top Strengths")
        for s in ev.get("top_3_strengths", []):
            st.success(f"✅ {s}")
    with c2:
        st.subheader("⚠️ Top Improvements")
        for s in ev.get("top_3_improvements", []):
            st.warning(f"🔧 {s}")

    # Topic performance
    st.subheader("📊 Topic Performance")
    for tp in ev.get("topic_performance", []):
        v_color = {
            "strong": COLORS["success"], "acceptable": COLORS["info"],
            "weak": COLORS["warning"], "critical": COLORS["danger"]
        }.get(tp.get("verdict",""), COLORS["info"])
        st.markdown(
            f"**{tp.get('topic_id','')}** · {tp.get('score_pct',0)}% · "
            f"**{tp.get('verdict','').upper()}** — {tp.get('priority_action','')}"
        )

    if st.button("🔄 Take Another Mock Exam", width="stretch"):
        for k in ["mock_exam","mock_answers","mock_submitted","mock_time_taken","mock_evaluation"]:
            st.session_state.pop(k, None)
        st.rerun()
