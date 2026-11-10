"""
StudyMind AI — Page 5: Socratic Doubt Solver Chatbot
ChatGPT-style UI layout with embedded history, session controls, and live streaming
Powered by modern google.genai and FastMCP syllabus search
"""
import streamlit as st
from pathlib import Path
import sys
import time
import re
import traceback

sys.path.insert(0, str(Path(__file__).parent.parent))
from gemini_client import call_gemini_stream, call_gemini_text
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

# ── Greeting detection helper ──────────────────────────────────────────────────
GREETING_PATTERN = re.compile(
    r"^(hi+|hey+|hello+|namaste+|howdy|good\s*(morning|afternoon|evening)|sup|what\'?s\s*up|hii+)\b",
    re.IGNORECASE,
)

def is_conversational_greeting(text: str) -> bool:
    """Checks if user input is a brief social greeting rather than a subject doubt."""
    clean = re.sub(r"[^\w\s]", "", text.strip()).lower()
    words = clean.split()
    if len(words) <= 3 and GREETING_PATTERN.match(clean):
        return True
    return clean in (
        "hi", "hii", "hiii", "hello", "hey", "heyy", "sup", "yo",
        "good morning", "good evening", "good afternoon", "namaste",
        "thanks", "thank you", "thx"
    )

# ── In-Chat Controls & Collapsible History ─────────────────────────────────────
ctrl_col1, ctrl_col2 = st.columns([4, 1])
with ctrl_col1:
    msg_count = len([m for m in st.session_state["chat_history"] if m.get("role") == "user"])
    st.caption(f"🧠 Socratic Guidance Active · {msg_count} question{'s' if msg_count != 1 else ''} asked in this session")
with ctrl_col2:
    if st.button("🗑️ Clear Chat", width="stretch"):
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

    if topic_tree and topic_tree.get("topics"):
        st.caption(f"📚 Connected Syllabus: **{topic_tree.get('subject','')}** ({len(topic_tree.get('topics',[]))} topics indexed for RAG context)")
    else:
        st.caption("📚 No syllabus uploaded yet. Upload one in the Syllabus Parser page for context-grounded answers.")

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
            if st.button(prompt_text, key=f"preset_{prompt_text[:12]}", width="stretch"):
                st.session_state["chat_history"].append({"role": "user", "content": prompt_text})
                st.rerun()

# ── Full-width Chat Messages Display ──────────────────────────────────────────
for msg in st.session_state["chat_history"]:
    with st.chat_message(msg["role"], avatar="🧠" if msg["role"] == "assistant" else "🎓"):
        st.markdown(msg["content"])

# ── Full-width Centered Chat Input ─────────────────────────────────────────────
user_input = st.chat_input(f"Ask your doubt here, {student_name}...")

if user_input:
    # Append user question
    st.session_state["chat_history"].append({"role": "user", "content": user_input})

    with st.chat_message("user", avatar="🎓"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="🧠"):
        response = None
        t0 = time.time()
        rag_context = ""
        retrieved_chunks = []
        rag_ms = 0.0

        is_greeting = is_conversational_greeting(user_input)

        if is_greeting:
            # Fast-path for simple greetings (e.g. "hii", "hello"): skip heavy RAG retrieval
            rag_context = (
                f"NOTE: The student sent a conversational greeting ('{user_input}'). "
                f"Respond warmly and enthusiastically as {student_name}'s Socratic study coach. "
                "Ask which concept, chapter, or problem they want to conquer today."
            )
        else:
            # Context-Aware RAG retrieval via MCP tool
            rag_start = time.time()
            try:
                with st.spinner("Consulting syllabus index & formulating Socratic guidance..."):
                    if topic_tree and topic_tree.get("topics"):
                        retrieved_chunks = search_syllabus(user_input, topic_tree)
                        if retrieved_chunks:
                            context_snippets = []
                            for c in retrieved_chunks[:3]:
                                sub_tag = f" > {c.get('subtopic_title')}" if c.get('subtopic_title') else ""
                                text_snippet = c.get('text', '')[:300]
                                context_snippets.append(f"• [{c.get('topic_title')}{sub_tag}]:\n  {text_snippet}")
                            rag_context = "RELEVANT SYLLABUS CONTEXT:\n" + "\n\n".join(context_snippets)
                        else:
                            rag_context = (
                                f"NOTE: The student's query did not match any topics in their uploaded syllabus "
                                f"({topic_tree.get('subject','')}). Provide Socratic guidance based on general domain knowledge "
                                "and ask if they'd like bonus off-syllabus assistance."
                            )
                    else:
                        rag_context = (
                            "NOTE: No syllabus has been uploaded yet. Provide Socratic guidance using general academic knowledge. "
                            "Encourage the student to upload their course syllabus in the Syllabus Parser page for curriculum-tailored help."
                        )
            except Exception as e:
                print(f"[CHATBOT RAG ERROR] {type(e).__name__}: {e}")
                traceback.print_exc()
                rag_context = "NOTE: Answer using general academic knowledge."

            rag_ms = round((time.time() - rag_start) * 1000, 2)
            print(f"[RAG CHATBOT] Query: '{user_input[:40]}...' retrieved {len(retrieved_chunks)} chunks in {rag_ms}ms")

        prompt = doubt_solver_prompt(
            question=user_input,
            student_name=student_name,
            chat_history=st.session_state["chat_history"][:-1],
            syllabus_context=rag_context,
        )

        # ── Step 2: Generate response via Gemini (Streaming with Non-Streaming Fallback) ──
        try:
            # Try live streaming typewriter response
            stream = call_gemini_stream(prompt, temperature=0.7)
            response = st.write_stream(stream)
        except Exception as stream_err:
            print(f"[CHATBOT STREAMING FAILED] {type(stream_err).__name__}: {stream_err}")
            # Non-streaming fallback
            try:
                with st.spinner("Streaming interrupted — fetching direct response..."):
                    response = call_gemini_text(prompt, temperature=0.7)
                if response:
                    st.markdown(response)
            except Exception as text_err:
                print(f"[CHATBOT TEXT FALLBACK FAILED] {type(text_err).__name__}: {text_err}")
                err_str = str(text_err)

                if "API_KEY_INVALID" in err_str or "API Key" in err_str:
                    response = (
                        "⚠️ **Gemini API Key Error** — Your API key appears to be invalid or unconfigured. "
                        "Please verify your key in the sidebar or update `GEMINI_API_KEY` in `.env`. "
                        "Keys can be generated at [Google AI Studio](https://aistudio.google.com/)."
                    )
                elif "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                    response = "⚠️ **Rate Limit Reached** — The Gemini API quota was temporarily exhausted. Please wait 30 seconds and ask again."
                elif "DEADLINE_EXCEEDED" in err_str or "504" in err_str or "timeout" in err_str.lower():
                    response = "⚠️ **Request Timed Out (504)** — Google's server experienced a temporary spike. Please re-send your question in a moment."
                elif "UNAVAILABLE" in err_str or "503" in err_str:
                    response = "⚠️ **Model Temporarily Unavailable (503)** — The AI model is currently under high demand. Please try again shortly."
                else:
                    response = (
                        f"⚠️ **Could not complete response**: `{type(text_err).__name__}`. "
                        "Please check your network connection or enter a valid API key."
                    )
                st.warning(response)

        # Guard against blank responses
        if not response or (isinstance(response, str) and not response.strip()):
            response = "⚠️ I could not generate an answer due to an unexpected empty response. Please try rephrasing your question."
            st.warning(response)

        # ── Step 3: Show retrieved syllabus context preview (if any matches found) ──
        if retrieved_chunks and not is_greeting:
            with st.expander(f"📚 Connected Syllabus Context (Retrieved in {rag_ms}ms)"):
                for c in retrieved_chunks[:3]:
                    sub_tag = f" — {c.get('subtopic_title')}" if c.get('subtopic_title') else ""
                    st.caption(f"**{c.get('topic_title')}{sub_tag}** (Relevance score: {c.get('score', 0)})")
                    st.text(c.get('text', '')[:250] + "...")

        total_ms = round((time.time() - t0) * 1000, 2)
        print(f"[CHATBOT] Total response: {total_ms}ms (RAG: {rag_ms}ms, Generation: {total_ms - rag_ms}ms)")

    # Save assistant response to chat history
    st.session_state["chat_history"].append({"role": "assistant", "content": response})
