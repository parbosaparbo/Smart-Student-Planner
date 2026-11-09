"""
StudyMind AI — Page 3: AI Quiz Generator
Powered entirely via FastMCP Architecture (generate_quiz tool).
"""
import streamlit as st
import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from mcp_client import mcp_client
from ui_components import render_sidebar_header
from storage import save_persistent_state
from config import COLORS, DIFFICULTY_LABELS

st.set_page_config(page_title="Quiz — StudyMind AI", page_icon="🎯", layout="wide", initial_sidebar_state="expanded")
render_sidebar_header()

st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["success"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["success"]};
            padding:1.5rem 2rem; border-radius:12px; margin-bottom:1.5rem;'>
  <h1 style='margin:0; color:{COLORS["success"]}'>🎯 AI Quiz Generator</h1>
  <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}'>
    Scenario-based, active recall questions powered by FastMCP and Gemini with instant caching.
  </p>
</div>
""", unsafe_allow_html=True)

# ── Topic Selection ────────────────────────────────────────────────────────────
topic_tree = st.session_state.get("topic_tree", {})
topics     = topic_tree.get("topics", [])
selected_topic = None

col1, col2 = st.columns([2, 1])

with col1:
    if topics:
        topic_options = {f"{t['id']} — {t['title']}": t for t in topics}
        selected_key  = st.selectbox("Select Topic", list(topic_options.keys()))
        selected_topic = topic_options[selected_key]
        topic_id    = selected_topic["id"]
        topic_title = selected_topic["title"]
    else:
        topic_id    = st.text_input("Topic ID (e.g. t1)", value="t1")
        topic_title = st.text_input("Topic Title", placeholder="e.g. Data Structures — Arrays")

with col2:
    question_count = st.slider("Question Count", min_value=3, max_value=10, value=5, help="Select number of scenario questions (3 to 10)")
    difficulty = st.slider("Difficulty Level", 1, 5, 3,
                           help="\n".join(f"{k}={v}" for k,v in DIFFICULTY_LABELS.items()))

generate_btn = st.button("⚡ Generate Quiz via FastMCP", type="primary", width="stretch",
                          disabled=not (topic_id and topic_title))

if generate_btn:
    # Build syllabus context from topic tree subtopics
    syllabus_ctx = ""
    if isinstance(selected_topic, dict):
        subtopics = selected_topic.get("subtopics", [])
        if subtopics:
            sub_strs = []
            for s in subtopics:
                title = s.get("title", "")
                concepts = ", ".join(s.get("key_concepts", []))
                sub_strs.append(f"{title}: {concepts}" if concepts else title)
            syllabus_ctx = f"Subject: {topic_tree.get('subject', '')} | Subtopics: " + "; ".join(sub_strs)

    with st.spinner(f"🧠 FastMCP: Generating {question_count} scenario questions on {topic_title}..."):
        try:
            t0 = time.time()
            # Invoke generate_quiz entirely through FastMCP Client
            quiz = mcp_client.call_tool(
                "generate_quiz",
                {
                    "topic": topic_title,
                    "topic_id": topic_id,
                    "topic_title": topic_title,
                    "difficulty": difficulty,
                    "question_count": question_count,
                    "num_questions": question_count,
                    "syllabus_context": syllabus_ctx,
                }
            )
            elapsed = round(time.time() - t0, 3)
            st.session_state["current_quiz"]    = quiz
            st.session_state["quiz_answers"]    = {}
            st.session_state["quiz_submitted"]  = False
            st.session_state["quiz_start_time"] = time.time()
            save_persistent_state(st.session_state)
            cached_str = " (cached)" if quiz.get("cached") else ""
            st.toast(f"⚡ FastMCP Quiz ready in {elapsed}s{cached_str}!", icon="🎯")
            st.rerun()
        except Exception as e:
            st.error(f"❌ FastMCP Quiz generation failed: {e}")

# ── Display Quiz ───────────────────────────────────────────────────────────────
if "current_quiz" in st.session_state and not st.session_state.get("quiz_submitted", False):
    quiz      = st.session_state["current_quiz"]
    questions = quiz.get("questions", [])
    elapsed   = int(time.time() - st.session_state.get("quiz_start_time", time.time()))
    total_sec = quiz.get("time_limit_seconds", len(questions) * 75)

    st.divider()
    st.subheader(f"📝 {quiz.get('topic_title','Quiz')} — {len(questions)} Questions")

    time_left = max(0, total_sec - elapsed)
    prog_val = min(max(elapsed / total_sec, 0.0), 1.0) if total_sec > 0 else 1.0
    st.progress(prog_val, text=f"⏱️ Time: {elapsed//60}:{elapsed%60:02d} / {total_sec//60}:{total_sec%60:02d}")

    with st.form("quiz_form"):
        answers = {}
        for i, q in enumerate(questions):
            st.markdown(f"""
<div style='background:{COLORS["card_bg"]}; border-radius:12px; padding:1.2rem;
            margin-bottom:1rem; border:1px solid {COLORS["primary"]}33;'>
  <p style='margin:0; font-weight:600;'>Q{i+1}. {q.get('question','')}</p>
  <small style='color:{COLORS["text_muted"]};'>Subtopic: {q.get('subtopic_tag','')} · 
  Difficulty: {q.get('difficulty',3)}/5</small>
</div>
""", unsafe_allow_html=True)
            opts = q.get("options", {})
            choice = st.radio(
                f"Your answer for Q{i+1}:",
                list(opts.keys()),
                format_func=lambda k, opts=opts: f"{k}: {opts[k]}",
                key=f"q_{q.get('id','')}_radio",
                index=None,
                label_visibility="collapsed"
            )
            answers[q.get("id", f"q{i+1}")] = choice

        submit_quiz = st.form_submit_button("✅ Submit Quiz", type="primary", width="stretch")

    if submit_quiz:
        st.session_state["quiz_answers"]   = answers
        st.session_state["quiz_submitted"] = True
        st.session_state["quiz_time_taken"] = int(time.time() - st.session_state.get("quiz_start_time", time.time()))
        st.rerun()

# ── Quiz Results ───────────────────────────────────────────────────────────────
if st.session_state.get("quiz_submitted", False):
    quiz      = st.session_state["current_quiz"]
    questions = quiz.get("questions", [])
    answers   = st.session_state["quiz_answers"]

    correct_count = sum(
        1 for q in questions
        if answers.get(q.get("id","")) == q.get("correct_answer","")
    )
    score_pct = round(correct_count / len(questions) * 100) if questions else 0
    time_taken = st.session_state.get("quiz_time_taken", 0)

    st.divider()
    st.subheader("🏆 Quiz Results")

    # Score display
    color = COLORS["success"] if score_pct >= 70 else COLORS["warning"] if score_pct >= 50 else COLORS["danger"]
    st.markdown(f"""
<div style='text-align:center; padding:2rem; background:{COLORS["card_bg"]};
            border-radius:16px; border:2px solid {color};'>
  <h1 style='color:{color}; margin:0;'>{score_pct}%</h1>
  <p style='margin:0.5rem 0; font-size:1.2rem;'>{correct_count}/{len(questions)} correct</p>
  <p style='color:{COLORS["text_muted"]}; margin:0;'>Time: {time_taken//60}m {time_taken%60}s</p>
</div>
""", unsafe_allow_html=True)

    if score_pct < 70:
        st.warning(f"⚠️ Score below 70% — triggering auto-reschedule recommendation for **{quiz.get('topic_title','')}**")

    # Store quiz result for weak spot analysis
    quiz_result = {
        "topic_id":    quiz.get("topic_id",""),
        "topic_title": quiz.get("topic_title",""),
        "score_pct":   score_pct,
        "correct":     correct_count,
        "total":       len(questions),
        "time_taken":  time_taken,
        "answers":     answers,
        "questions":   questions,
    }
    if "quiz_results" not in st.session_state:
        st.session_state["quiz_results"] = []
    # Update or append
    existing_ids = [r.get("topic_id") for r in st.session_state["quiz_results"]]
    if quiz_result["topic_id"] in existing_ids:
        idx = existing_ids.index(quiz_result["topic_id"])
        st.session_state["quiz_results"][idx] = quiz_result
    else:
        st.session_state["quiz_results"].append(quiz_result)

    st.divider()
    st.subheader("📋 Answer Review")

    for i, q in enumerate(questions):
        qid     = q.get("id", f"q{i+1}")
        correct = q.get("correct_answer", "")
        given   = answers.get(qid, None)
        is_ok   = given == correct
        opts    = q.get("options", {})
        icon    = "✅" if is_ok else "❌"

        with st.expander(f"{icon} Q{i+1}: {q.get('question','')[:80]}..."):
            for k, v in opts.items():
                prefix = ""
                if k == correct: prefix = "✅ "
                elif k == given and not is_ok: prefix = "❌ "
                st.markdown(f"{prefix}**{k}:** {v}")

            st.info(f"💡 **Explanation:** {q.get('explanation','')}")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔄 Retake Quiz", width="stretch"):
            st.session_state["quiz_submitted"] = False
            st.session_state["quiz_answers"]   = {}
            st.rerun()
    with col_b:
        if st.button("📊 Analyze Weak Spots", width="stretch"):
            st.switch_page("pages/4_📊_Weak_Spot_Analyzer.py")
