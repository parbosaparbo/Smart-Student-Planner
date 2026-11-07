"""
StudyMind AI — Page 5: Socratic Doubt Solver Chatbot
ChatGPT-style UI layout with embedded history, session controls, and live streaming
"""
import streamlit as st
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from gemini_client import call_gemini_stream
from prompts import doubt_solver_prompt
from mcp_tools import search_syllabus
from ui_components import render_sidebar_header
from config import COLORS

st.set_page_config(
    page_title="Doubt Solver — StudyMind AI",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)
render_sidebar_header()

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["primary"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["primary"]};
            padding:1.4rem 2rem; border-radius:12px; margin-bottom:1.2rem;'>
  <h1 style='margin:0; color:{COLORS["primary"]}; font-size:2rem;'>💬 Socratic Doubt Solver</h1>
  <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}; font-size:0.95rem;'>
    Ask anything — I'll guide you to the answer, Socratic style. No spoon-feeding. Real understanding only.
  </p>
</div>
""", unsafe_allow_html=True)

student = st.session_state.get("student_profile", {})
student_name = student.get("student_name", "Student")
topic_tree = st.session_state.get("topic_tree", {})

# ── Chat history state ─────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# ── In-Chat Controls & Collapsible History (ChatGPT-style embedded UX) ─────────
ctrl_col1, ctrl_col2 = st.columns([4, 1])
with ctrl_col1:
    msg_count = len([m for m in st.session_state["chat_history"] if m.get("role") == "user"])
    st.caption(f"🧠 Socratic Guidance Active · {msg_count} question{'s' if msg_count != 1 else ''} asked in this session")
with ctrl_col2:
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state["chat_history"] = []
        st.rerun()

with st.expander("🕒 Chat History & Saved Doubts", expanded=False):
    user_questions = [m["content"] for m in st.session_state["chat_history"] if m.get("role") == "user"]
    if user_questions:
        st.markdown("**Questions explored in this session:**")
        for idx, q in enumerate(user_questions, 1):
            st.markdown(f"**{idx}.** {q}")
        st.divider()
        clear_hist_col, _ = st.columns([2, 3])
        with clear_hist_col:
            if st.button("🗑️ Reset & Start Fresh Conversation", key="clear_inside_expander"):
                st.session_state["chat_history"] = []
                st.rerun()
    else:
        st.info("No doubts asked yet in this session. Type your question below to begin!")
    
    if topic_tree:
        st.caption(f"📚 Connected Syllabus: **{topic_tree.get('subject','')}** ({len(topic_tree.get('topics',[]))} topics indexed for RAG context)")

# ── Starter suggestions if no messages yet ─────────────────────────────────────
if not st.session_state["chat_history"]:
    st.markdown("<p style='color:#888; font-size:0.9rem; margin-top:1rem;'>💡 <b>Not sure where to start? Try asking:</b></p>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    preset_prompts = [
        "Explain TCP 3-Way Handshake with a real-life analogy",
        "Why do we need Subnet Masks in IP addressing?",
        "How does DNS resolve a domain name step-by-step?"
    ]
    for col, prompt_text in zip([c1, c2, c3], preset_prompts):
        with col:
            if st.button(prompt_text, key=f"preset_{prompt_text[:12]}", use_container_width=True):
                st.session_state["chat_history"].append({"role": "user", "content": prompt_text})
                st.rerun()

# ── Full-width Chat Messages Display ──────────────────────────────────────────
for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"], avatar="🧠" if msg["role"] == "assistant" else "🎓"):
        st.markdown(msg["content"])

# ── Full-width Centered Chat Input ─────────────────────────────────────────────
user_input = st.chat_input(f"Ask your doubt here, {student_name}...")

if user_input:
    st.session_state["chat_history"].append({"role": "user", "content": user_input})

    with st.chat_message("user", avatar="🎓"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="🧠"):
        with st.spinner("Consulting syllabus & preparing Socratic guidance..."):
            rag_context = ""
            if topic_tree:
                matched_topics = search_syllabus(user_input, topic_tree)
                if matched_topics:
                    rag_context = f"RELEVANT SYLLABUS TOPICS MATCHED:\n{matched_topics[:3]}"
                else:
                    rag_context = f"NOTE: The student's query did not match any topics in their uploaded syllabus ({topic_tree.get('subject','')}). Ask if they want bonus off-syllabus help."

            prompt = doubt_solver_prompt(
                question=user_input,
                student_name=student_name,
                chat_history=st.session_state["chat_history"][:-1],
                syllabus_context=rag_context,
            )
        # Live streaming typewriter response
        stream = call_gemini_stream(prompt, temperature=0.8)
        response = st.write_stream(stream)

    st.session_state["chat_history"].append({"role": "assistant", "content": response})
