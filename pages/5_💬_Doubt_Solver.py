"""
StudyMind AI — Page 5: Socratic Doubt Solver Chatbot
"""
import streamlit as st
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from gemini_client import call_gemini_text
from prompts import doubt_solver_prompt
from mcp_tools import search_syllabus
from config import COLORS

st.set_page_config(page_title="Doubt Solver — StudyMind AI", page_icon="💬", layout="wide")

st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["primary"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["primary"]};
            padding:1.5rem 2rem; border-radius:12px; margin-bottom:1.5rem;'>
  <h1 style='margin:0; color:{COLORS["primary"]}'>💬 Doubt Solver</h1>
  <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}'>
    Ask anything — I'll guide you to the answer, Socratic style. 
    No spoon-feeding. Real understanding only.
  </p>
</div>
""", unsafe_allow_html=True)

student = st.session_state.get("student_profile", {})
student_name = student.get("student_name", "Student")

# ── Chat init ──────────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("⚙️ Chat Settings")
    if st.button("🗑️ Clear Chat History"):
        st.session_state["chat_history"] = []
        st.rerun()

    st.divider()
    topic_tree = st.session_state.get("topic_tree", {})
    if topic_tree:
        st.subheader("📚 Your Syllabus Topics")
        for t in topic_tree.get("topics", []):
            st.markdown(f"• {t.get('title','')}")
    else:
        st.info("No syllabus loaded. Upload one in Syllabus Parser.")

# ── Chat display ───────────────────────────────────────────────────────────────
for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"], avatar="🧠" if msg["role"] == "assistant" else "🎓"):
        st.markdown(msg["content"])

# ── Input ──────────────────────────────────────────────────────────────────────
user_input = st.chat_input(f"Ask your doubt here, {student_name}...")

if user_input:
    st.session_state["chat_history"].append({"role": "user", "content": user_input})

    with st.chat_message("user", avatar="🎓"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="🧠"):
        with st.spinner("Consulting syllabus & preparing Socratic guidance..."):
            topic_tree = st.session_state.get("topic_tree", {})
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
                syllabus_context=rag_context
            )
            response = call_gemini_text(prompt, temperature=0.8)
        st.markdown(response)

    st.session_state["chat_history"].append({"role": "assistant", "content": response})
