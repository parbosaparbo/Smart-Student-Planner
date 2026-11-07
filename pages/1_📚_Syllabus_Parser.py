"""
StudyMind AI — Page 1: Syllabus Parser
"""
import streamlit as st
import json
try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from gemini_client import call_gemini_json
from prompts import syllabus_parser_prompt
from storage import save_persistent_state
from config import COLORS, DIFFICULTY_LABELS

st.set_page_config(page_title="Syllabus Parser — StudyMind AI", page_icon="📚", layout="wide")

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style='background:linear-gradient(135deg,{COLORS["primary"]}22,{COLORS["card_bg"]});
            border-left:4px solid {COLORS["primary"]};
            padding:1.5rem 2rem; border-radius:12px; margin-bottom:1.5rem;'>
  <h1 style='margin:0; color:{COLORS["primary"]}'>📚 Syllabus Parser</h1>
  <p style='margin:0.3rem 0 0; color:{COLORS["text_muted"]}'>
    Upload a PDF or paste raw text — get a full structured topic tree in seconds.
  </p>
</div>
""", unsafe_allow_html=True)

# ── Input ──────────────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("Upload Syllabus")
    input_method = st.radio("Choose input method", ["📄 Upload PDF", "✏️ Paste Text"], horizontal=True)

    raw_text = ""
    if input_method == "📄 Upload PDF":
        uploaded = st.file_uploader("Upload your syllabus PDF", type=["pdf"])
        if uploaded:
            if fitz is None:
                st.error("⚠️ PyMuPDF is not installed in the currently active Python. Please launch via `run.bat` or install it with: `pip install pymupdf`")
            else:
                with st.spinner("Extracting text from PDF..."):
                    doc = fitz.open(stream=uploaded.read(), filetype="pdf")
                    raw_text = "\n".join(page.get_text() for page in doc)
                st.success(f"✅ Extracted {len(raw_text)} characters from {len(doc)} pages")
                with st.expander("Preview extracted text"):
                    st.text(raw_text[:2000] + ("..." if len(raw_text) > 2000 else ""))
    else:
        if st.button("💡 Load Sample 7th Sem Syllabus"):
            try:
                sample_path = Path(__file__).parent.parent / "sample_syllabus.md"
                with open(sample_path, "r", encoding="utf-8") as f:
                    st.session_state["pasted_sample"] = f.read()
                st.rerun()
            except Exception as e:
                st.error(f"Could not load sample: {e}")
        sample_val = st.session_state.get("pasted_sample", "")
        raw_text = st.text_area(
            "Paste syllabus text here",
            value=sample_val,
            height=300,
            placeholder="Paste your syllabus content here...\n\nUnit 1: Data Structures\n  - Arrays, Linked Lists\n  - Trees and Graphs\n..."
        )

    parse_btn = st.button("🔍 Parse Syllabus", type="primary", disabled=not raw_text.strip(), use_container_width=True)

with col2:
    st.subheader("How it works")
    st.markdown("""
    1. **Upload** your PDF syllabus or paste raw text
    2. **AI extracts** topics, subtopics, difficulty, and estimated hours
    3. **Review** the structured topic tree
    4. **Save** to use in Schedule Generator

    > 💡 **Tip:** The more detailed your syllabus, the better the topic tree. 
    > Include unit names, topics, and subtopics for best results.

    **What gets extracted:**
    - 🎯 Topic priority (exam importance)
    - ⚡ Difficulty level (Bloom's taxonomy)
    - ⏱️ Estimated study hours
    - 🔗 Topic prerequisites
    - 📌 Key concepts per subtopic
    """)

# ── Parse ──────────────────────────────────────────────────────────────────────
if parse_btn and raw_text.strip():
    with st.spinner("🧠 StudyMind AI is parsing your syllabus..."):
        try:
            prompt = syllabus_parser_prompt(raw_text)
            result = call_gemini_json(prompt, temperature=0.3)

            # Save to session state
            st.session_state["topic_tree"] = result
            st.session_state["subject"]    = result.get("subject", "")
            save_persistent_state(st.session_state)

            st.success("✅ Syllabus parsed successfully!")

        except ValueError as e:
            st.error(f"❌ Parsing failed: {e}")
            st.stop()

# ── Display Result ─────────────────────────────────────────────────────────────
if "topic_tree" in st.session_state:
    result = st.session_state["topic_tree"]

    # Summary metrics
    topics = result.get("topics", [])
    total_hours = result.get("total_estimated_hours", 0)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Subject", result.get("subject", "—"))
    m2.metric("Total Topics", len(topics))
    m3.metric("Est. Hours", f"{total_hours}h")
    m4.metric("Exam Type", result.get("exam_type", "—").title())

    st.divider()
    st.subheader("📋 Topic Tree")

    # Topic cards
    for i, topic in enumerate(topics):
        difficulty = topic.get("difficulty", 1)
        priority   = topic.get("priority", 1)
        diff_label = DIFFICULTY_LABELS.get(difficulty, "Unknown")
        diff_color = [COLORS["success"], COLORS["info"], COLORS["warning"], COLORS["warning"], COLORS["danger"]][difficulty - 1]

        with st.expander(
            f"**{topic.get('id','').upper()}** · {topic.get('title','Untitled')} "
            f"| {topic.get('estimated_hours',0)}h | Priority {priority}/5",
            expanded=(i < 3)
        ):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Difficulty:** :{diff_color}[{diff_label} ({difficulty}/5)]")
            c2.markdown(f"**Priority:** {'⭐' * priority}")
            c3.markdown(f"**Prerequisites:** {', '.join(topic.get('prerequisites', [])) or 'None'}")

            subtopics = topic.get("subtopics", [])
            if subtopics:
                st.markdown("**Subtopics:**")
                for sub in subtopics:
                    concepts = ", ".join(sub.get("key_concepts", []))
                    st.markdown(
                        f"- **{sub.get('title','')}** ({sub.get('estimated_hours',0)}h)"
                        + (f" — *{concepts}*" if concepts else "")
                    )

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            "⬇️ Download Topic Tree (JSON)",
            data=json.dumps(result, indent=2),
            file_name=f"{result.get('subject','syllabus').replace(' ','_')}_topic_tree.json",
            mime="application/json",
            use_container_width=True,
        )
    with col_b:
        if st.button("➡️ Go to Schedule Generator", use_container_width=True):
            st.switch_page("pages/2_📅_Schedule_Generator.py")
